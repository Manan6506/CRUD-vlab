"""Parsers that turn typed text into a `Command`.

Two grammars are accepted — a subset of SQL and a subset of the Django ORM —
and both produce the *same* `Command` object. That is what lets the engine
execute either one through the ORM, and display both equivalent forms.

Neither parser evaluates anything. Input is matched against explicit patterns
and every column name is checked against a whitelist, so a command can only
ever touch the `students` table.
"""

import re
from dataclasses import dataclass, field

TABLE = 'students'

#: Columns that may be read.
READABLE = ['id', 'name', 'email', 'phone', 'created_at', 'updated_at']
#: Columns that may be written. `id` is assigned by the database.
WRITABLE = ['name', 'email', 'phone']


class ParseError(Exception):
    """Raised with a student-facing explanation of what was wrong."""


@dataclass
class Command:
    """A parsed command, independent of which grammar produced it."""

    action: str                              # select | count | insert | update | delete
                                             # | help | describe | clear | history
    filters: dict = field(default_factory=dict)   # ORM lookups to include
    excludes: dict = field(default_factory=dict)  # ORM lookups to exclude
    values: dict = field(default_factory=dict)    # column -> value, for write actions
    columns: list = field(default_factory=list)   # projected columns for a select
    order_by: str = ''
    limit: int = 0
    where_text: str = ''                     # the WHERE clause as written, for display

    @property
    def has_condition(self):
        return bool(self.filters or self.excludes)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_STRING = re.compile(r"""^(['"])(.*)\1$""", re.DOTALL)


def _literal(raw, *, context):
    """Convert a quoted string or a bare integer into a Python value."""
    raw = raw.strip()
    match = _STRING.match(raw)
    if match:
        return match.group(2)
    if re.fullmatch(r'-?\d+', raw):
        return int(raw)
    raise ParseError(
        f"{context}: {raw!r} is not a valid value. "
        "Text must be quoted, for example 'Asha Patil'."
    )


def _check_column(name, allowed, *, context):
    name = name.strip().lower()
    if name not in allowed:
        raise ParseError(
            f"{context}: there is no column {name!r} you can use here. "
            f"Available: {', '.join(allowed)}."
        )
    return name


def _like_to_lookup(column, pattern):
    """Translate a SQL LIKE pattern into the matching ORM lookup."""
    starts, ends = pattern.startswith('%'), pattern.endswith('%')
    body = pattern.strip('%')
    if starts and ends:
        return f'{column}__icontains', body
    if ends:
        return f'{column}__istartswith', body
    if starts:
        return f'{column}__iendswith', body
    return f'{column}__iexact', body


_COMPARISONS = {'<': 'lt', '>': 'gt', '<=': 'lte', '>=': 'gte'}


def _parse_where(clause, command):
    """Fill `command.filters` / `command.excludes` from a SQL WHERE clause.

    Supports conditions joined by AND, using = != <> < > <= >= and LIKE.
    """
    command.where_text = clause.strip()

    for condition in re.split(r'\s+AND\s+', clause.strip(), flags=re.IGNORECASE):
        condition = condition.strip()
        if not condition:
            continue

        match = re.match(
            r'^(\w+)\s*(=|!=|<>|<=|>=|<|>|LIKE)\s*(.+)$', condition, re.IGNORECASE
        )
        if not match:
            raise ParseError(
                f"Could not read the condition {condition!r}. "
                "Write it as  column = value,  for example  id = 2  or  name LIKE '%a%'."
            )

        column, operator, raw_value = match.groups()
        column = _check_column(column, READABLE, context='WHERE')
        operator = operator.upper()
        value = _literal(raw_value, context='WHERE')

        if operator == 'LIKE':
            if not isinstance(value, str):
                raise ParseError('LIKE needs a quoted pattern, for example LIKE \'%asha%\'.')
            lookup, body = _like_to_lookup(column, value)
            command.filters[lookup] = body
        elif operator == '=':
            command.filters[column] = value
        elif operator in ('!=', '<>'):
            command.excludes[column] = value
        else:
            command.filters[f'{column}__{_COMPARISONS[operator]}'] = value

    return command


# ---------------------------------------------------------------------------
# Meta commands, shared by both modes
# ---------------------------------------------------------------------------

def _meta(text):
    """Recognise the non-query commands available in either mode."""
    word = text.strip().rstrip(';').lower()
    if word in ('help', '?', r'\?', r'\h'):
        return Command(action='help')
    if word in ('clear', 'cls', r'\c'):
        return Command(action='clear')
    if word in (r'\d', r'\dt', r'\d students', 'describe', 'describe students',
                'schema', '.schema'):
        return Command(action='describe')
    return None


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------

_FORBIDDEN = re.compile(
    r'\b(DROP|ALTER|CREATE|TRUNCATE|ATTACH|DETACH|PRAGMA|VACUUM|GRANT|REVOKE|'
    r'REPLACE|REINDEX|ANALYZE)\b',
    re.IGNORECASE,
)


def parse_sql(text):
    """Parse the supported subset of SQL into a `Command`."""
    meta = _meta(text)
    if meta:
        return meta

    statement = text.strip().rstrip(';').strip()
    if not statement:
        raise ParseError('Type a statement, or `help` to see what is available.')

    if _FORBIDDEN.search(statement):
        raise ParseError(
            'Only SELECT, INSERT, UPDATE and DELETE are available in this terminal. '
            'Statements that change the schema are not part of this experiment.'
        )

    head = statement.split(None, 1)[0].upper()
    if head == 'SELECT':
        return _parse_select(statement)
    if head == 'INSERT':
        return _parse_insert(statement)
    if head == 'UPDATE':
        return _parse_update(statement)
    if head == 'DELETE':
        return _parse_delete(statement)

    raise ParseError(
        f'Unrecognised statement {head!r}. Expected SELECT, INSERT, UPDATE or DELETE. '
        'Type `help` for examples.'
    )


def _require_table(name):
    if name.strip().lower() != TABLE:
        raise ParseError(
            f'This experiment has one table, {TABLE!r}. There is no table {name!r}.'
        )


def _parse_select(statement):
    match = re.match(
        r'^SELECT\s+(?P<cols>.+?)\s+FROM\s+(?P<table>\w+)'
        r'(?:\s+WHERE\s+(?P<where>.+?))?'
        r'(?:\s+ORDER\s+BY\s+(?P<order>\w+(?:\s+(?:ASC|DESC))?))?'
        r'(?:\s+LIMIT\s+(?P<limit>\d+))?$',
        statement, re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise ParseError(
            'Could not read that SELECT. Expected: '
            "SELECT * FROM students [WHERE …] [ORDER BY col] [LIMIT n]"
        )

    _require_table(match.group('table'))
    raw_columns = match.group('cols').strip()

    command = Command(action='select')

    if re.fullmatch(r'COUNT\s*\(\s*\*?\s*\)', raw_columns, re.IGNORECASE):
        command.action = 'count'
    elif raw_columns == '*':
        command.columns = list(READABLE)
    else:
        command.columns = [
            _check_column(name, READABLE, context='SELECT')
            for name in raw_columns.split(',')
        ]

    if match.group('where'):
        _parse_where(match.group('where'), command)

    if match.group('order'):
        parts = match.group('order').split()
        column = _check_column(parts[0], READABLE, context='ORDER BY')
        descending = len(parts) > 1 and parts[1].upper() == 'DESC'
        command.order_by = f'-{column}' if descending else column

    if match.group('limit'):
        command.limit = int(match.group('limit'))

    return command


def _split_list(text):
    """Split a comma-separated list, ignoring commas inside quotes."""
    parts, current, quote = [], '', None
    for character in text:
        if quote:
            current += character
            if character == quote:
                quote = None
        elif character in '\'"':
            quote = character
            current += character
        elif character == ',':
            parts.append(current)
            current = ''
        else:
            current += character
    parts.append(current)
    return [part.strip() for part in parts if part.strip()]


def _parse_insert(statement):
    match = re.match(
        r'^INSERT\s+INTO\s+(?P<table>\w+)\s*\((?P<cols>[^)]*)\)\s*'
        r'VALUES\s*\((?P<vals>.+)\)$',
        statement, re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise ParseError(
            'Could not read that INSERT. Expected: '
            "INSERT INTO students (name, email, phone) VALUES ('…', '…', '…')"
        )

    _require_table(match.group('table'))
    columns = [
        _check_column(name, WRITABLE, context='INSERT')
        for name in _split_list(match.group('cols'))
    ]
    values = [_literal(raw, context='VALUES') for raw in _split_list(match.group('vals'))]

    if len(columns) != len(values):
        raise ParseError(
            f'{len(columns)} column(s) listed but {len(values)} value(s) supplied.'
        )

    missing = [name for name in WRITABLE if name not in columns]
    if missing:
        raise ParseError(
            f'Missing required column(s): {", ".join(missing)}. '
            'All of name, email and phone must be supplied.'
        )

    return Command(action='insert', values=dict(zip(columns, values)))


def _parse_update(statement):
    match = re.match(
        r'^UPDATE\s+(?P<table>\w+)\s+SET\s+(?P<sets>.+?)'
        r'(?:\s+WHERE\s+(?P<where>.+))?$',
        statement, re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise ParseError(
            'Could not read that UPDATE. Expected: '
            "UPDATE students SET phone = '…' WHERE id = 1"
        )

    _require_table(match.group('table'))
    command = Command(action='update')

    for assignment in _split_list(match.group('sets')):
        pair = re.match(r'^(\w+)\s*=\s*(.+)$', assignment, re.DOTALL)
        if not pair:
            raise ParseError(
                f'Could not read the assignment {assignment!r}. '
                "Expected  column = value."
            )
        column = _check_column(pair.group(1), WRITABLE, context='SET')
        command.values[column] = _literal(pair.group(2), context='SET')

    if match.group('where'):
        _parse_where(match.group('where'), command)
    return command


def _parse_delete(statement):
    match = re.match(
        r'^DELETE\s+FROM\s+(?P<table>\w+)(?:\s+WHERE\s+(?P<where>.+))?$',
        statement, re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise ParseError(
            'Could not read that DELETE. Expected:  DELETE FROM students WHERE id = 1'
        )

    _require_table(match.group('table'))
    command = Command(action='delete')
    if match.group('where'):
        _parse_where(match.group('where'), command)
    return command


# ---------------------------------------------------------------------------
# Django ORM
# ---------------------------------------------------------------------------

_LOOKUP_SUFFIXES = [
    'exact', 'iexact', 'contains', 'icontains', 'startswith', 'istartswith',
    'endswith', 'iendswith', 'gt', 'gte', 'lt', 'lte', 'in', 'isnull',
]


def _check_lookup(key, *, context):
    """Validate an ORM lookup such as ``name__icontains`` or ``pk``."""
    key = key.strip()
    if key == 'pk':
        return 'id'

    if '__' in key:
        column, suffix = key.rsplit('__', 1)
        if suffix not in _LOOKUP_SUFFIXES:
            raise ParseError(
                f'{context}: {suffix!r} is not a lookup this terminal supports. '
                f'Try one of: {", ".join(_LOOKUP_SUFFIXES[:8])}.'
            )
        column = 'id' if column == 'pk' else column
        _check_column(column, READABLE, context=context)
        return f'{column}__{suffix}'

    return _check_column(key, READABLE, context=context)


def _parse_kwargs(text, *, context, allowed_lookups=True):
    """Parse ``name='x', pk=2`` into a dict, without evaluating anything."""
    result = {}
    for part in _split_list(text):
        pair = re.match(r'^(\w+)\s*=\s*(.+)$', part, re.DOTALL)
        if not pair:
            raise ParseError(
                f'{context}: could not read {part!r}. Expected  name=value.'
            )
        key, raw_value = pair.groups()
        key = (
            _check_lookup(key, context=context) if allowed_lookups
            else _check_column(key, WRITABLE, context=context)
        )
        result[key] = _literal(raw_value, context=context)
    return result


def parse_orm(text):
    """Parse the supported subset of Django ORM expressions into a `Command`."""
    meta = _meta(text)
    if meta:
        return meta

    expression = text.strip().rstrip(';').strip()
    if not expression:
        raise ParseError('Type an expression, or `help` to see what is available.')

    if not expression.startswith('Student.objects'):
        raise ParseError(
            'Expressions must start with  Student.objects  — this terminal exposes '
            'only the Student model. Type `help` for examples.'
        )

    rest = expression[len('Student.objects'):]
    command = Command(action='select')
    saw_queryset_call = False

    # Walk the chained calls left to right: .filter(...).order_by(...).count()
    pattern = re.compile(r'^\.(\w+)\(([^()]*)\)')
    while rest:
        slice_match = re.match(r'^\[\s*:\s*(\d+)\s*\]$', rest)
        if slice_match:
            command.limit = int(slice_match.group(1))
            rest = ''
            break

        match = pattern.match(rest)
        if not match:
            raise ParseError(
                f'Could not read {rest!r}. Chain calls like '
                "Student.objects.filter(name__icontains='a').count()"
            )

        method, arguments = match.group(1), match.group(2).strip()
        rest = rest[match.end():]

        if method == 'all':
            saw_queryset_call = True
        elif method in ('filter', 'exclude'):
            saw_queryset_call = True
            parsed = _parse_kwargs(arguments, context=method)
            (command.excludes if method == 'exclude' else command.filters).update(parsed)
            command.where_text = arguments
        elif method == 'get':
            saw_queryset_call = True
            command.filters.update(_parse_kwargs(arguments, context='get'))
            command.where_text = arguments
            command.limit = 2          # so the engine can detect "more than one"
            command.action = 'get'
        elif method == 'create':
            command.action = 'insert'
            command.values = _parse_kwargs(arguments, context='create',
                                           allowed_lookups=False)
        elif method == 'count':
            command.action = 'count'
        elif method == 'delete':
            command.action = 'delete'
        elif method == 'update':
            command.action = 'update'
            command.values = _parse_kwargs(arguments, context='update',
                                           allowed_lookups=False)
        elif method == 'order_by':
            field_name = _literal(arguments, context='order_by')
            descending = isinstance(field_name, str) and field_name.startswith('-')
            column = _check_column(str(field_name).lstrip('-'), READABLE,
                                   context='order_by')
            command.order_by = f'-{column}' if descending else column
        elif method == 'first':
            command.limit = 1
        else:
            raise ParseError(
                f'{method}() is not available in this terminal. Supported: all, filter, '
                'exclude, get, create, update, delete, count, order_by, first.'
            )

    if command.action == 'select' and not saw_queryset_call and not command.limit:
        raise ParseError(
            'Incomplete expression. Try  Student.objects.all()  or '
            "Student.objects.filter(name__icontains='a')."
        )

    if command.action == 'select' and command.columns == []:
        command.columns = list(READABLE)
    return command
