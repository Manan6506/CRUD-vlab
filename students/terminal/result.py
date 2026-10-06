"""The structured outcome of running one terminal command."""

from dataclasses import dataclass, field


@dataclass
class Result:
    """What a command produced, in a form the console can render.

    `kind` tells the front end how to display it:

    ``table``    a result set — `columns` and `rows` are populated
    ``message``  a one-line confirmation, e.g. "1 row inserted"
    ``error``    the command failed; `message` explains why
    ``help``     the built-in help text
    ``describe`` the table's schema
    ``clear``    instruction to clear the screen
    """

    kind: str
    message: str = ''
    columns: list = field(default_factory=list)
    rows: list = field(default_factory=list)

    #: The two equivalent forms of the command, shown side by side.
    sql: str = ''
    orm: str = ''

    rows_affected: int = 0
    #: Fields used to write the statement log; empty when nothing was executed.
    operation: str = ''
    tag: str = ''
    note: str = ''

    @property
    def failed(self):
        return self.kind == 'error'

    def as_dict(self):
        """Serialise for the JSON response the console consumes."""
        return {
            'kind': self.kind,
            'message': self.message,
            'columns': self.columns,
            'rows': self.rows,
            'sql': self.sql,
            'orm': self.orm,
            'rows_affected': self.rows_affected,
            'operation': self.operation,
        }


def error(message):
    """Shorthand for a failed command."""
    return Result(kind='error', message=message)
