"""``python manage.py seedlab`` — load the dataset the experiment starts from.

Sample students are *demo data*: the student edits and deletes them during the
experiment and resets them afterwards. That makes them unsuitable for a data
migration, which would also populate the test database. They are loaded by this
command instead.

(The quiz questions *are* reference data and are seeded by a migration, so they
need no command.)
"""

from django.core.management.base import BaseCommand

from students.models import Student
from students.sample_data import load_samples, reset_experiment


class Command(BaseCommand):
    help = 'Load the sample students the experiment starts from.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete every row first and restart ids from 1, '
                 'discarding any rows added during the experiment.',
        )

    def handle(self, *args, **options):
        if options['reset']:
            total = reset_experiment()
            self.stdout.write(self.style.SUCCESS(
                f'Experiment reset: {total} rows, ids restarting from 1, log cleared.'
            ))
            return

        created = load_samples()
        total = Student.objects.count()
        if created:
            self.stdout.write(self.style.SUCCESS(
                f'{created} sample row(s) inserted. The table now holds {total}.'
            ))
        else:
            self.stdout.write(
                f'Sample rows are already present. The table holds {total}.'
            )
