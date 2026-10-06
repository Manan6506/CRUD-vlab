"""Seed the Pretest and Posttest with their questions.

Written as a *data migration* so the quizzes exist as soon as `migrate` has
run — there is no separate setup step for whoever evaluates the project. The
questions remain editable afterwards in the Django admin.
"""

from django.db import migrations

PRETEST = [
    {
        'order': 1,
        'text': 'What does the acronym CRUD stand for?',
        'explanation': 'CRUD names the four operations every persistent store must '
                       'support: Create, Read, Update and Delete.',
        'choices': [
            ('Create, Read, Update, Delete', True),
            ('Copy, Rename, Undo, Deploy', False),
            ('Compile, Run, Upload, Debug', False),
            ('Connect, Request, Use, Disconnect', False),
        ],
    },
    {
        'order': 2,
        'text': 'Which SQL statement adds a new row to a table?',
        'explanation': 'INSERT adds rows. SELECT reads, UPDATE modifies and DELETE '
                       'removes them.',
        'choices': [
            ('INSERT', True),
            ('SELECT', False),
            ('UPDATE', False),
            ('APPEND', False),
        ],
    },
    {
        'order': 3,
        'text': 'What is the purpose of a PRIMARY KEY?',
        'explanation': 'A primary key uniquely identifies each row, so a single row can '
                       'always be addressed unambiguously.',
        'choices': [
            ('To uniquely identify each row in a table', True),
            ('To sort the table alphabetically', False),
            ('To encrypt the contents of a row', False),
            ('To limit how many rows a table may hold', False),
        ],
    },
    {
        'order': 4,
        'text': 'A column is declared UNIQUE. What happens when you insert a second row '
                'with the same value in that column?',
        'explanation': 'The database refuses the statement. The constraint is enforced '
                       'by the database itself, not only by the application.',
        'choices': [
            ('The insert is refused and no row is added', True),
            ('The existing row is silently overwritten', False),
            ('Both rows are stored', False),
            ('The value is automatically renamed', False),
        ],
    },
    {
        'order': 5,
        'text': 'In a Django project, which file decides which view handles an incoming '
                'URL?',
        'explanation': 'urls.py holds the URLconf. Django tries each pattern in order '
                       'and calls the view attached to the first one that matches.',
        'choices': [
            ('urls.py', True),
            ('models.py', False),
            ('settings.py', False),
            ('admin.py', False),
        ],
    },
]

POSTTEST = [
    {
        'order': 1,
        'text': 'In the simulator, who assigns the value of the id column when a row is '
                'inserted?',
        'explanation': 'The form supplies only name, email and phone. The database '
                       'generates the primary key.',
        'choices': [
            ('The database, automatically', True),
            ('The student, by typing it into the form', False),
            ('Django, by counting the existing rows', False),
            ('It stays empty until the row is updated', False),
        ],
    },
    {
        'order': 2,
        'text': 'After deleting the row with id = 5 and inserting a new row, what id does '
                'the new row receive?',
        'explanation': 'Identifiers are not reused. The counter keeps moving forward, so '
                       'a deleted id leaves a permanent gap.',
        'choices': [
            ('The next unused id — 5 is not reused', True),
            ('5, because that id is now free', False),
            ('1, because numbering restarts', False),
            ('The same id as the row above it', False),
        ],
    },
    {
        'order': 3,
        'text': 'Which Django form hook should hold a rule that compares two fields '
                'against each other?',
        'explanation': 'clean() runs after every clean_<field>(), so all individual '
                       'values are already cleaned and available together.',
        'choices': [
            ('clean()', True),
            ('clean_<field>()', False),
            ('__init__()', False),
            ('save()', False),
        ],
    },
    {
        'order': 4,
        'text': 'An UPDATE changes a student’s phone number. What happens to that '
                'row’s primary key?',
        'explanation': 'UPDATE rewrites columns of an existing row. The row keeps its '
                       'identity, so the primary key is unchanged.',
        'choices': [
            ('It stays the same', True),
            ('It is incremented by one', False),
            ('A new row is created with a new key', False),
            ('It is set back to 1', False),
        ],
    },
    {
        'order': 5,
        'text': 'Why does the ORM send values as parameters instead of pasting them into '
                'the SQL string?',
        'explanation': 'Separating the statement from its values means a value can never '
                       'be read as SQL, which is what prevents SQL injection.',
        'choices': [
            ('To prevent SQL injection', True),
            ('To make the statement shorter', False),
            ('Because SQLite cannot parse long strings', False),
            ('To avoid having to validate the form', False),
        ],
    },
]


def seed(apps, schema_editor):
    """Insert the questions and their choices."""
    Question = apps.get_model('lab', 'Question')
    Choice = apps.get_model('lab', 'Choice')

    for stage, bank in (('PRE', PRETEST), ('POST', POSTTEST)):
        for item in bank:
            question = Question.objects.create(
                stage=stage,
                order=item['order'],
                text=item['text'],
                explanation=item['explanation'],
            )
            for text, is_correct in item['choices']:
                Choice.objects.create(question=question, text=text, is_correct=is_correct)


def unseed(apps, schema_editor):
    """Reverse the migration by removing the seeded questions."""
    apps.get_model('lab', 'Question').objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [('lab', '0001_initial')]

    operations = [migrations.RunPython(seed, unseed)]
