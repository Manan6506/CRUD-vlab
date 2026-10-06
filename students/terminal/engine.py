"""Executes a parsed `Command` against the `students` table.

The engine is the only place where a terminal command touches the database, and
it does so exclusively through the ORM. It also:

* renders the equivalent SQL and ORM text for whichever mode was *not* used, so
  the console can show both forms of every command, and
* writes each executed command to `OperationLog`, using the same tags the
  form-based simulator uses — so work done in the terminal counts towards the
  Exercises just as work done through the forms does.
"""

from django.core.exceptions import ValidationError
from django.db import IntegrityError

from ..models import OperationLog, Student
from .parsers import READABLE, TABLE, Command, ParseError, parse_orm, parse_sql
from .result import Result, error

SQL = 'sql'
ORM = 'orm'

HELP_SQL = """Supported statements (the table is 'students'):

  SELECT * FROM students;
  SELECT name, email FROM students WHERE name LIKE '%asha%';
  SELECT COUNT(*) FROM students;
  SELECT * FROM students ORDER BY name DESC LIMIT 2;

  INSERT INTO students (name, email, phone) VALUES ('Asha Patil', 'asha@x.com', '9876543210');

  UPDATE students SET phone = '9000000000' WHERE id = 1;

  DELETE FROM students WHERE id = 5;

Operators in WHERE:  =  !=  <  >  <=  >=  LIKE
Other commands:      help    describe    clear"""

HELP_ORM = """Supported expressions (the model is 'Student'):

  Student.objects.all()
  Student.objects.filter(name__icontains='asha')
  Student.objects.exclude(phone='')
  Student.objects.get(pk=1)
  Student.objects.count()
  Student.objects.all().order_by('-name')[:2]

  Student.objects.create(name='Asha Patil', email='asha@x.com', phone='9876543210')

  Student.objects.filter(pk=1).update(phone='9000000000')

  Student.objects.filter(pk=5).delete()

Lookups:         exact iexact contains icontains startswith endswith gt gte lt lte
Other commands:  help    describe    clear"""


# ---------------------------------------------------------------------------
# Rendering the two equivalent forms of a command
# ---------------------------------------------------------------------------

def _quote(value):
    if isinstance(value, int):
        return str(value)
    return "'{}'".format(str(value).replace("'", "''"))


_SUFFIX_TO_SQL = {
    'icontains': ('LIKE', '%{}%'), 'contains': ('LIKE', '%{}%'),
    'istartswith': ('LIKE', '{}%'), 'startswith': ('LIKE', '{}%'),
    'iendswith': ('LIKE', '%{}'), 'endswith': ('LIKE', '%{}'),
    'iexact': ('=', '{}'), 'exact': ('=', '{}'),
    'gt': ('>', '{}'), 'gte': ('>=', '{}'), 'lt': ('<', '{}'), 'lte': ('<=', '{}'),
}


def _where_sql(command):
    """Build the SQL WHERE clause that matches the command's lookups."""
    parts = []
    for key, value in command.filters.items():
        if '__' in key:
            column, suffix = key.rsplit('__', 1)
            operator, template = _SUFFIX_TO_SQL.get(suffix, ('=', '{}'))
            # Only the LIKE templates rewrite the value (they add % wildcards).
            # Everything else passes it through unchanged, so that an integer
            # stays an integer and is not rendered as a quoted string.
            rendered = template.format(value) if '%' in template else value
            parts.append(f'{column} {operator} {_quote(rendered)}')
        else:
            parts.append(f'{key} = {_quote(value)}')
    for key, value in command.excludes.items():
        parts.append(f'{key} != {_quote(value)}')
    return ' AND '.join(parts)


def _as_sql(command):
    """Render the command as a SQL statement."""
    where = _where_sql(command)
    suffix = f'\nWHERE {where}' if where else ''

    if command.action in ('select', 'get'):
        columns = ', '.join(command.columns or READABLE)
        statement = f'SELECT {columns} FROM {TABLE}{suffix}'
        if command.order_by:
            direction = 'DESC' if command.order_by.startswith('-') else 'ASC'
            statement += f'\nORDER BY {command.order_by.lstrip("-")} {direction}'
        if command.limit and command.action != 'get':
            statement += f'\nLIMIT {command.limit}'
        return statement + ';'

    if command.action == 'count':
        return f'SELECT COUNT(*) FROM {TABLE}{suffix};'

    if command.action == 'insert':
        columns = ', '.join(command.values)
        values = ', '.join(_quote(value) for value in command.values.values())
        return f'INSERT INTO {TABLE} ({columns})\nVALUES ({values});'

    if command.action == 'update':
        assignments = ', '.join(
            f'{column} = {_quote(value)}' for column, value in command.values.items()
        )
        return f'UPDATE {TABLE}\nSET {assignments}{suffix};'

    if command.action == 'delete':
        return f'DELETE FROM {TABLE}{suffix};'
    return ''


def _kwargs_text(mapping):
    return ', '.join(f'{key}={_quote(value)}' for key, value in mapping.items())


def _as_orm(command):
    """Render the command as a Django ORM expression."""
    base = 'Student.objects'

    if command.action == 'insert':
        return f'{base}.create({_kwargs_text(command.values)})'

    if command.action == 'get':
        return f'{base}.get({_kwargs_text(command.filters)})'

    chain = base
    if command.filters:
        chain += f'.filter({_kwargs_text(command.filters)})'
    if command.excludes:
        chain += f'.exclude({_kwargs_text(command.excludes)})'
    if not command.filters and not command.excludes:
        chain += '.all()'

    if command.action == 'count':
        return chain + '.count()'
    if command.action == 'delete':
        return chain + '.delete()'
    if command.action == 'update':
        return chain + f'.update({_kwargs_text(command.values)})'

    if command.order_by:
        chain += f".order_by('{command.order_by}')"
    if command.limit:
        chain += f'[:{command.limit}]'
    return chain


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def _queryset(command):
    queryset = Student.objects.all()
    if command.filters:
        queryset = queryset.filter(**command.filters)
    if command.excludes:
        queryset = queryset.exclude(**command.excludes)
    if command.order_by:
        queryset = queryset.order_by(command.order_by)
    return queryset


def _rows(queryset, columns):
    """Materialise a queryset into plain lists for the console to render."""
    return [
        [_display(getattr(student, column)) for column in columns]
        for student in queryset
    ]


def _display(value):
    if hasattr(value, 'strftime'):
        return value.strftime('%Y-%m-%d %H:%M')
    return value


def _describe():
    return Result(
        kind='describe',
        message=f'Table "{TABLE}"',
        columns=['Column', 'Type', 'Constraints'],
        rows=[
            ['id', 'INTEGER', 'PRIMARY KEY, AUTOINCREMENT'],
            ['name', 'VARCHAR(100)', 'NOT NULL'],
            ['email', 'VARCHAR(254)', 'NOT NULL, UNIQUE'],
            ['phone', 'VARCHAR(16)', 'NOT NULL, 7-15 digits'],
            ['created_at', 'DATETIME', 'set on insert'],
            ['updated_at', 'DATETIME', 'set on every save'],
        ],
    )


def _validation_message(exc):
    """Flatten a Django ValidationError into one readable line."""
    if hasattr(exc, 'message_dict'):
        return '; '.join(
            f'{field}: {" ".join(messages)}'
            for field, messages in exc.message_dict.items()
        )
    return '; '.join(exc.messages)


def _run(command, mode):
    """Carry out a parsed command and return a `Result`."""
    if command.action == 'help':
        return Result(kind='help', message=HELP_SQL if mode == SQL else HELP_ORM)
    if command.action == 'clear':
        return Result(kind='clear')
    if command.action == 'describe':
        return _describe()

    sql_text, orm_text = _as_sql(command), _as_orm(command)

    # -- READ ---------------------------------------------------------------
    if command.action == 'count':
        total = _queryset(command).count()
        return Result(
            kind='table', columns=['COUNT(*)'], rows=[[total]],
            sql=sql_text, orm=orm_text, rows_affected=total,
            operation=OperationLog.READ,
            tag='read_filtered' if command.has_condition else 'read_all',
            note=f'COUNT(*) returned {total}',
            message=f'1 row returned',
        )

    if command.action in ('select', 'get'):
        queryset = _queryset(command)
        if command.action == 'get':
            found = list(queryset[:2])
            if not found:
                return error(
                    'Student matching query does not exist. '
                    '(get() raises DoesNotExist when nothing matches.)'
                )
            if len(found) > 1:
                return error(
                    'get() returned more than one Student. '
                    'Use filter() when a query can match several rows.'
                )
            rows = _rows(found, command.columns or READABLE)
        else:
            if command.limit:
                queryset = queryset[:command.limit]
            rows = _rows(queryset, command.columns)

        single = command.action == 'get' or 'id' in command.filters
        return Result(
            kind='table', columns=command.columns or READABLE, rows=rows,
            sql=sql_text, orm=orm_text, rows_affected=len(rows),
            operation=OperationLog.READ,
            tag='read_one' if single else (
                'read_filtered' if command.has_condition else 'read_all'),
            note=('Lookup by primary key' if single else
                  ('Filtered query' if command.has_condition else 'No filter')),
            message=f'{len(rows)} row{"" if len(rows) == 1 else "s"} returned',
        )

    # -- CREATE -------------------------------------------------------------
    if command.action == 'insert':
        student = Student(**command.values)
        try:
            student.full_clean()      # runs the model's field validators
            student.save()
        except ValidationError as exc:
            _log_rejection(OperationLog.CREATE, 'create_rejected', sql_text,
                           orm_text, _validation_message(exc))
            return error(_validation_message(exc))
        except IntegrityError as exc:
            _log_rejection(OperationLog.CREATE, 'create_rejected', sql_text,
                           orm_text, str(exc))
            return error(f'Insert refused by the database: {exc}')

        return Result(
            kind='message', sql=sql_text, orm=orm_text, rows_affected=1,
            operation=OperationLog.CREATE, tag='create',
            note=f'Database assigned id = {student.id}',
            message=f'1 row inserted. The database assigned id = {student.id}.',
        )

    # -- UPDATE -------------------------------------------------------------
    if command.action == 'update':
        queryset = _queryset(command)
        targets = list(queryset)
        if not targets:
            return Result(kind='message', sql=sql_text, orm=orm_text,
                          message='0 rows updated — no row matched.')
        for student in targets:
            for column, value in command.values.items():
                setattr(student, column, value)
            try:
                student.full_clean()
            except ValidationError as exc:
                _log_rejection(OperationLog.UPDATE, 'update_rejected', sql_text,
                               orm_text, _validation_message(exc))
                return error(_validation_message(exc))
            student.save()

        return Result(
            kind='message', sql=sql_text, orm=orm_text, rows_affected=len(targets),
            operation=OperationLog.UPDATE, tag='update',
            note='Columns changed: ' + ', '.join(command.values),
            message=f'{len(targets)} row{"" if len(targets) == 1 else "s"} updated. '
                    'Primary keys unchanged.',
        )

    # -- DELETE -------------------------------------------------------------
    if command.action == 'delete':
        if not command.has_condition:
            return error(
                'Refusing to delete every row. Add a WHERE clause, for example '
                'DELETE FROM students WHERE id = 5. (Use Reset to start over.)'
            )
        queryset = _queryset(command)
        ids = list(queryset.values_list('id', flat=True))
        if not ids:
            return Result(kind='message', sql=sql_text, orm=orm_text,
                          message='0 rows deleted — no row matched.')
        queryset.delete()
        return Result(
            kind='message', sql=sql_text, orm=orm_text, rows_affected=len(ids),
            operation=OperationLog.DELETE, tag='delete',
            note=f'Removed id(s) {", ".join(map(str, ids))}; not reused',
            message=f'{len(ids)} row{"" if len(ids) == 1 else "s"} deleted. '
                    f'id {", ".join(map(str, ids))} will not be reused.',
        )

    return error(f'Nothing to do for action {command.action!r}.')


def _log_rejection(operation, tag, sql_text, orm_text, note):
    OperationLog.record(
        operation, tag, sql=f'-- refused before execution\n{sql_text}',
        orm=orm_text, http='POST /simulation/terminal/', rows_affected=0,
        status=OperationLog.REJECTED, note=note[:200],
    )


def execute(text, mode=SQL):
    """Parse and run one line typed into the terminal.

    Returns a `Result`. Never raises for bad input — a parse failure comes back
    as a `Result` of kind ``error`` so the console can print it like a shell
    would.
    """
    parser = parse_sql if mode == SQL else parse_orm
    try:
        command = parser(text)
    except ParseError as exc:
        return error(str(exc))

    result = _run(command, mode)

    # Record successful statements so terminal work counts towards the exercises.
    if result.tag and not result.failed:
        OperationLog.record(
            result.operation, result.tag, sql=result.sql, orm=result.orm,
            http='POST /simulation/terminal/', rows_affected=result.rows_affected,
            note=result.note,
        )
    return result
