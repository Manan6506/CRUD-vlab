"""The Exercises section: tasks the student performs on the simulator.

Each exercise is checked automatically. The simulator records every statement
it runs in `OperationLog` with a short `tag` (``read_filtered``, ``update``,
``create_rejected`` …); an exercise is complete once a matching entry exists.

Exercises are defined here in code rather than in the database because they are
part of the experiment's design, not data an instructor would edit per run.
"""

from dataclasses import dataclass
from typing import Callable

from students.models import OperationLog


@dataclass(frozen=True)
class Exercise:
    """One task, and the rule that decides whether it has been done."""

    number: int
    operation: str          # CREATE / READ / UPDATE / DELETE — for the badge
    title: str
    instruction: str
    expected: str           # what the student should observe
    #: Given every logged statement, has this task been completed?
    rule: Callable[[list], bool]


def _has_tag(tag):
    """Build a rule that passes once any logged statement carries `tag`."""
    return lambda logs: any(log.tag == tag for log in logs)


EXERCISES = [
    Exercise(
        number=1,
        operation='READ',
        title='Select every row',
        instruction='On the Simulation page, leave the filter box empty and press '
                    '<strong>Run SELECT</strong>.',
        expected='All four rows are returned and the statement log shows a SELECT '
                 'with no WHERE clause.',
        rule=_has_tag('read_all'),
    ),
    Exercise(
        number=2,
        operation='READ',
        title='Filter rows with a WHERE clause',
        instruction='Type part of a name (for example <code>meera</code>) into the '
                    'filter box and press <strong>Run SELECT</strong>.',
        expected='Only the matching row is returned, and the logged SQL now contains '
                 'a <code>WHERE … LIKE</code> clause.',
        rule=_has_tag('read_filtered'),
    ),
    Exercise(
        number=3,
        operation='READ',
        title='Retrieve a single row by primary key',
        instruction='Press <strong>SELECT</strong> on any row of the table.',
        expected='One row is returned by <code>WHERE id = …</code>. This is the fastest '
                 'kind of lookup, because the primary key is indexed.',
        rule=_has_tag('read_one'),
    ),
    Exercise(
        number=4,
        operation='CREATE',
        title='Insert a new row',
        instruction='Choose <strong>CREATE</strong> and insert a student with a name, a '
                    'new email address and a valid phone number.',
        expected='The insert succeeds and the database — not you — assigns the next '
                 '<code>id</code>.',
        rule=_has_tag('create'),
    ),
    Exercise(
        number=5,
        operation='CREATE',
        title='Trigger the UNIQUE constraint',
        instruction='Try to insert a second student using an email address that already '
                    'exists in the table.',
        expected='The insert is refused. No row is added, and the statement log records '
                 'the attempt as <strong>REJECTED</strong>.',
        rule=_has_tag('create_rejected'),
    ),
    Exercise(
        number=6,
        operation='UPDATE',
        title='Update an existing row',
        instruction='Press <strong>UPDATE</strong> on the row you created and change its '
                    'phone number.',
        expected='One row is affected and the <code>id</code> is unchanged — an UPDATE '
                 'rewrites columns, it does not create a new row.',
        rule=_has_tag('update'),
    ),
    Exercise(
        number=7,
        operation='DELETE',
        title='Delete a row',
        instruction='Press <strong>DELETE</strong> on the row you created and confirm.',
        expected='The row count drops by one. Insert another row afterwards and note '
                 'that the deleted id is <em>not</em> reused.',
        rule=_has_tag('delete'),
    ),
]


def evaluate(logs=None):
    """Return ``[(exercise, completed), …]`` for the statements logged so far."""
    if logs is None:
        logs = list(OperationLog.objects.all())
    return [(exercise, exercise.rule(logs)) for exercise in EXERCISES]


def progress(logs=None):
    """Return ``(completed_count, total)`` across all exercises."""
    results = evaluate(logs)
    return sum(1 for _, done in results if done), len(results)
