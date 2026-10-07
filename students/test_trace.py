"""Tests for the file trace shown in the Simulation.

The trace is written by hand, so the risk is that it drifts away from the code
it describes. These tests pin it down:

* every file it names must exist in the project;
* every symbol it names must actually appear in that file;
* the only file it ever marks as changed must be the database.
"""

from pathlib import Path

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from . import trace
from .models import Student

ROOT = Path(settings.BASE_DIR)

ALL_TRACES = {
    'create': trace.for_create(),
    'read (many)': trace.for_read(single=False),
    'read (one)': trace.for_read(single=True),
    'update': trace.for_update(1),
    'delete': trace.for_delete(1),
    'terminal (sql)': trace.for_terminal(mode='sql'),
    'terminal (orm)': trace.for_terminal(mode='orm'),
}


class TraceAccuracyTests(TestCase):
    """The trace must describe the code as it actually is."""

    def test_every_named_file_exists(self):
        for name, steps in ALL_TRACES.items():
            for step in steps:
                with self.subTest(trace=name, file=step.file):
                    if step.file == trace.DB_FILE:
                        continue          # created by migrate, not in the repo
                    self.assertTrue(
                        (ROOT / step.file).is_file(),
                        f'{step.file} is named in the {name} trace but does not exist',
                    )

    def test_every_named_symbol_appears_in_its_file(self):
        """Guards against the trace naming a function that has been renamed."""
        for name, steps in ALL_TRACES.items():
            for step in steps:
                if step.file == trace.DB_FILE:
                    continue
                source = (ROOT / step.file).read_text()
                for needle in self.symbols_in(step.symbol):
                    with self.subTest(trace=name, file=step.file, symbol=needle):
                        self.assertIn(
                            needle, source,
                            f'{needle!r} is named in the {name} trace but does not '
                            f'appear in {step.file}',
                        )

    @staticmethod
    def symbols_in(symbol):
        """The identifiers a symbol string claims are defined in its file.

        A symbol may list several names separated by '·', may be a qualified
        name such as ``StudentForm.clean_name()``, and may carry an
        explanatory suffix after 'via' or '→'. Only the bare identifiers are
        checked.
        """
        for piece in symbol.split('·'):
            piece = piece.split(' in ')[0].split(' → ')[0].strip()
            if not piece or piece.startswith('{%') or piece.startswith('table:'):
                continue
            yield piece.replace('()', '').split('.')[-1].split('(')[0].strip()

    def test_only_the_database_is_ever_marked_as_changed(self):
        """The central teaching point: source files are executed, not edited."""
        for name, steps in ALL_TRACES.items():
            for step in steps:
                if step.changed:
                    with self.subTest(trace=name, file=step.file):
                        self.assertEqual(step.file, trace.DB_FILE)

    def test_every_trace_starts_at_the_project_urlconf(self):
        for name, steps in ALL_TRACES.items():
            with self.subTest(trace=name):
                self.assertEqual(steps[0].file, 'studentproject/urls.py')

    def test_every_trace_ends_at_a_template(self):
        for name, steps in ALL_TRACES.items():
            with self.subTest(trace=name):
                self.assertEqual(steps[-1].effect, 'renders')

    def test_every_step_but_the_last_hands_off(self):
        for name, steps in ALL_TRACES.items():
            for step in steps[:-1]:
                with self.subTest(trace=name, file=step.file):
                    self.assertTrue(step.handoff, f'{step.file} explains no handoff')

    def test_a_read_touches_the_database_read_only(self):
        steps = trace.for_read()
        database = [s for s in steps if s.file == trace.DB_FILE]
        self.assertEqual(database[0].effect, 'reads')

    def test_a_write_touches_the_database_as_a_write(self):
        for builder in (trace.for_create, trace.for_update, trace.for_delete):
            with self.subTest(builder=builder.__name__):
                database = [s for s in builder() if s.file == trace.DB_FILE]
                self.assertEqual(database[0].effect, 'writes')

    def test_for_tag_covers_every_tag_the_simulator_logs(self):
        for tag in ('read_all', 'read_filtered', 'read_one', 'create',
                    'create_rejected', 'update', 'delete'):
            with self.subTest(tag=tag):
                self.assertTrue(trace.for_tag(tag), f'no trace for tag {tag!r}')

    def test_for_tag_is_empty_for_an_unknown_tag(self):
        self.assertEqual(trace.for_tag('nonsense'), [])


class TracePageTests(TestCase):
    """The trace is rendered on every page of the Simulation."""

    def setUp(self):
        self.student = Student.objects.create(
            name='Asha Patil', email='asha@example.com', phone='9876543210')

    def pages(self):
        return [
            reverse('students:simulator'),
            reverse('students:terminal'),
            reverse('students:create'),
            reverse('students:detail', args=[self.student.pk]),
            reverse('students:update', args=[self.student.pk]),
            reverse('students:delete', args=[self.student.pk]),
        ]

    def test_every_simulation_page_shows_the_file_trace(self):
        for url in self.pages():
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, 'File trace')
                self.assertContains(response, 'studentproject/urls.py')

    def test_pages_name_the_database_as_the_file_that_changes(self):
        response = self.client.get(reverse('students:create'))
        self.assertContains(response, 'db.sqlite3')
        self.assertContains(response, 'changed')

    def test_the_trace_explains_that_no_source_file_is_modified(self):
        response = self.client.get(reverse('students:simulator'))
        self.assertContains(response, 'No source file is modified')

    def test_the_update_trace_names_the_row(self):
        response = self.client.get(reverse('students:update', args=[self.student.pk]))
        self.assertContains(response, f'row {self.student.pk}')


class TerminalTraceTests(TestCase):
    """The terminal endpoint returns the files a command passed through."""

    def setUp(self):
        Student.objects.create(name='Asha Patil', email='asha@example.com',
                               phone='9876543210')

    def run_command(self, command, mode='sql'):
        import json
        return self.client.post(
            reverse('students:terminal_run'),
            json.dumps({'command': command, 'mode': mode}),
            content_type='application/json').json()

    def test_a_select_returns_its_file_route(self):
        data = self.run_command('SELECT * FROM students')
        files = [entry['file'] for entry in data['files']]
        self.assertIn('students/terminal/parsers.py', files)
        self.assertIn('students/terminal/engine.py', files)
        self.assertIn('db.sqlite3', files)

    def test_a_select_marks_the_database_read_only(self):
        """A read must not be reported as changing the file.

        The lab does append a statement-log row, but that is its own
        bookkeeping and is deliberately kept out of the one-line route.
        """
        data = self.run_command('SELECT * FROM students')
        database = [e for e in data['files'] if e['file'] == 'db.sqlite3']
        self.assertEqual(len(database), 1)
        self.assertFalse(database[0]['changed'])
        self.assertEqual(database[0]['effect'], 'reads')

    def test_the_route_omits_the_statement_log_write(self):
        data = self.run_command('SELECT * FROM students')
        self.assertEqual(len([e for e in data['files'] if e['file'] == 'db.sqlite3']), 1)

    def test_an_insert_marks_the_database_as_changed(self):
        data = self.run_command(
            "INSERT INTO students (name, email, phone) "
            "VALUES ('Ravi Kumar', 'ravi@example.com', '9123456780')")
        database = [e for e in data['files'] if e['file'] == 'db.sqlite3']
        self.assertTrue(any(e['changed'] for e in database))

    def test_no_source_file_is_ever_marked_changed(self):
        data = self.run_command('SELECT * FROM students')
        for entry in data['files']:
            if entry['changed']:
                with self.subTest(file=entry['file']):
                    self.assertEqual(entry['file'], 'db.sqlite3')

    def test_a_failed_command_returns_no_route(self):
        data = self.run_command('DROP TABLE students')
        self.assertEqual(data['kind'], 'error')
        self.assertEqual(data['files'], [])

    def test_orm_mode_names_the_orm_parser(self):
        data = self.run_command('Student.objects.all()', mode='orm')
        self.assertIn('students/terminal/parsers.py',
                      [entry['file'] for entry in data['files']])
