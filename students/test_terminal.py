"""Unit tests for the simulated terminal.

Covers the two parsers, the engine that executes a parsed command, the safety
rules that keep the terminal confined to the `students` table, and the JSON
endpoint the console calls.
"""

import json

from django.test import TestCase
from django.urls import reverse

from .models import OperationLog, Student
from .terminal import execute
from .terminal.engine import ORM, SQL
from .terminal.parsers import ParseError, parse_orm, parse_sql


class SqlParserTests(TestCase):
    def test_select_all(self):
        command = parse_sql('SELECT * FROM students')
        self.assertEqual(command.action, 'select')
        self.assertEqual(command.filters, {})

    def test_select_with_where(self):
        command = parse_sql("SELECT * FROM students WHERE id = 2")
        self.assertEqual(command.filters, {'id': 2})

    def test_like_becomes_icontains(self):
        command = parse_sql("SELECT * FROM students WHERE name LIKE '%asha%'")
        self.assertEqual(command.filters, {'name__icontains': 'asha'})

    def test_like_prefix_becomes_istartswith(self):
        command = parse_sql("SELECT * FROM students WHERE name LIKE 'asha%'")
        self.assertEqual(command.filters, {'name__istartswith': 'asha'})

    def test_not_equal_becomes_exclude(self):
        command = parse_sql("SELECT * FROM students WHERE id != 2")
        self.assertEqual(command.excludes, {'id': 2})

    def test_comparison_operators(self):
        self.assertEqual(parse_sql('SELECT * FROM students WHERE id > 2').filters,
                         {'id__gt': 2})

    def test_order_by_and_limit(self):
        command = parse_sql('SELECT * FROM students ORDER BY name DESC LIMIT 3')
        self.assertEqual(command.order_by, '-name')
        self.assertEqual(command.limit, 3)

    def test_count(self):
        self.assertEqual(parse_sql('SELECT COUNT(*) FROM students').action, 'count')

    def test_insert(self):
        command = parse_sql(
            "INSERT INTO students (name, email, phone) VALUES ('A B', 'a@b.com', '9000000000')"
        )
        self.assertEqual(command.action, 'insert')
        self.assertEqual(command.values['email'], 'a@b.com')

    def test_insert_requires_every_column(self):
        with self.assertRaises(ParseError):
            parse_sql("INSERT INTO students (name) VALUES ('A B')")

    def test_update(self):
        command = parse_sql("UPDATE students SET phone = '9111111111' WHERE id = 1")
        self.assertEqual(command.action, 'update')
        self.assertEqual(command.values, {'phone': '9111111111'})
        self.assertEqual(command.filters, {'id': 1})

    def test_delete(self):
        command = parse_sql('DELETE FROM students WHERE id = 3')
        self.assertEqual(command.action, 'delete')

    def test_trailing_semicolon_is_optional(self):
        self.assertEqual(parse_sql('SELECT * FROM students;').action, 'select')

    def test_case_insensitive(self):
        self.assertEqual(parse_sql('select * from students').action, 'select')

    # -- safety -------------------------------------------------------------

    def test_schema_changing_statements_are_refused(self):
        for statement in ('DROP TABLE students', 'ALTER TABLE students ADD x INT',
                          'CREATE TABLE t (a INT)', 'PRAGMA table_info(students)',
                          'ATTACH DATABASE \'x\' AS y', 'TRUNCATE TABLE students'):
            with self.subTest(statement=statement):
                with self.assertRaises(ParseError):
                    parse_sql(statement)

    def test_other_tables_are_refused(self):
        with self.assertRaises(ParseError):
            parse_sql('SELECT * FROM auth_user')

    def test_unknown_column_is_refused(self):
        with self.assertRaises(ParseError):
            parse_sql('SELECT password FROM students')

    def test_writing_the_primary_key_is_refused(self):
        with self.assertRaises(ParseError):
            parse_sql('UPDATE students SET id = 99 WHERE id = 1')


class OrmParserTests(TestCase):
    def test_all(self):
        self.assertEqual(parse_orm('Student.objects.all()').action, 'select')

    def test_filter(self):
        command = parse_orm("Student.objects.filter(name__icontains='asha')")
        self.assertEqual(command.filters, {'name__icontains': 'asha'})

    def test_pk_maps_to_id(self):
        self.assertEqual(parse_orm('Student.objects.get(pk=1)').filters, {'id': 1})

    def test_exclude(self):
        self.assertEqual(parse_orm("Student.objects.exclude(phone='')").excludes,
                         {'phone': ''})

    def test_create(self):
        command = parse_orm(
            "Student.objects.create(name='A B', email='a@b.com', phone='9000000000')")
        self.assertEqual(command.action, 'insert')

    def test_chained_update(self):
        command = parse_orm("Student.objects.filter(pk=1).update(phone='9111111111')")
        self.assertEqual(command.action, 'update')
        self.assertEqual(command.filters, {'id': 1})

    def test_chained_delete(self):
        self.assertEqual(parse_orm('Student.objects.filter(pk=1).delete()').action, 'delete')

    def test_count(self):
        self.assertEqual(parse_orm('Student.objects.count()').action, 'count')

    def test_order_by_and_slice(self):
        command = parse_orm("Student.objects.all().order_by('-name')[:2]")
        self.assertEqual(command.order_by, '-name')
        self.assertEqual(command.limit, 2)

    # -- safety -------------------------------------------------------------

    def test_other_models_are_refused(self):
        with self.assertRaises(ParseError):
            parse_orm('User.objects.all()')

    def test_arbitrary_python_is_refused(self):
        for text in ('import os', '__import__("os").system("ls")',
                     'Student.objects.raw("SELECT 1")',
                     'Student.objects.all().delete.__globals__'):
            with self.subTest(text=text):
                with self.assertRaises(ParseError):
                    parse_orm(text)

    def test_unsupported_method_is_refused(self):
        with self.assertRaises(ParseError):
            parse_orm('Student.objects.raw()')

    def test_unknown_lookup_is_refused(self):
        with self.assertRaises(ParseError):
            parse_orm("Student.objects.filter(name__regex='.*')")


class TerminalEngineTests(TestCase):
    """Running commands actually changes the table."""

    def setUp(self):
        self.student = Student.objects.create(
            name='Asha Patil', email='asha@example.com', phone='9876543210')

    def test_select_returns_rows(self):
        result = execute('SELECT * FROM students', SQL)
        self.assertEqual(result.kind, 'table')
        self.assertEqual(result.rows_affected, 1)

    def test_insert_creates_a_row(self):
        result = execute(
            "INSERT INTO students (name, email, phone) "
            "VALUES ('Ravi Kumar', 'ravi@example.com', '9123456780')", SQL)
        self.assertEqual(result.kind, 'message')
        self.assertEqual(Student.objects.count(), 2)

    def test_insert_runs_the_model_validators(self):
        result = execute(
            "INSERT INTO students (name, email, phone) "
            "VALUES ('Bad Phone', 'bad@example.com', 'xyz')", SQL)
        self.assertTrue(result.failed)
        self.assertEqual(Student.objects.count(), 1)

    def test_insert_respects_the_unique_constraint(self):
        result = execute(
            "INSERT INTO students (name, email, phone) "
            "VALUES ('Duplicate', 'asha@example.com', '9000000000')", SQL)
        self.assertTrue(result.failed)
        self.assertEqual(Student.objects.count(), 1)

    def test_update_changes_the_row(self):
        execute("UPDATE students SET phone = '9111111111' WHERE id = %d"
                % self.student.pk, SQL)
        self.student.refresh_from_db()
        self.assertEqual(self.student.phone, '9111111111')

    def test_delete_removes_the_row(self):
        execute(f'DELETE FROM students WHERE id = {self.student.pk}', SQL)
        self.assertEqual(Student.objects.count(), 0)

    def test_delete_without_a_where_clause_is_refused(self):
        result = execute('DELETE FROM students', SQL)
        self.assertTrue(result.failed)
        self.assertEqual(Student.objects.count(), 1)

    def test_get_with_no_match_explains_itself(self):
        result = execute('Student.objects.get(pk=999)', ORM)
        self.assertTrue(result.failed)
        self.assertIn('does not exist', result.message)

    def test_get_with_several_matches_explains_itself(self):
        Student.objects.create(name='Asha Two', email='two@example.com', phone='9000000000')
        result = execute("Student.objects.get(name__icontains='asha')", ORM)
        self.assertTrue(result.failed)
        self.assertIn('more than one', result.message)

    def test_both_modes_produce_the_same_effect(self):
        execute("INSERT INTO students (name, email, phone) "
                "VALUES ('Via SQL', 'sql@example.com', '9000000001')", SQL)
        execute("Student.objects.create(name='Via ORM', email='orm@example.com', "
                "phone='9000000002')", ORM)
        self.assertEqual(Student.objects.count(), 3)

    def test_integers_are_not_quoted_in_the_rendered_sql(self):
        """`WHERE id > 2` must not render as `WHERE id > '2'`."""
        result = execute('SELECT * FROM students WHERE id > 2', SQL)
        self.assertIn('id > 2', result.sql)
        self.assertNotIn("id > '2'", result.sql)

    def test_like_patterns_keep_their_wildcards(self):
        result = execute("SELECT * FROM students WHERE name LIKE '%asha%'", SQL)
        self.assertIn("LIKE '%asha%'", result.sql)

    def test_each_result_carries_both_equivalent_forms(self):
        result = execute("SELECT * FROM students WHERE id = 1", SQL)
        self.assertIn('SELECT', result.sql)
        self.assertIn('Student.objects', result.orm)

    def test_help_and_describe_do_not_touch_the_table(self):
        for command in ('help', 'describe', 'clear'):
            with self.subTest(command=command):
                result = execute(command, SQL)
                self.assertFalse(result.failed)
        self.assertEqual(OperationLog.objects.count(), 0)


class TerminalLoggingTests(TestCase):
    """Terminal work counts towards the exercises."""

    def setUp(self):
        Student.objects.create(name='Asha Patil', email='asha@example.com',
                               phone='9876543210')

    def test_select_is_logged_with_a_tag(self):
        execute('SELECT * FROM students', SQL)
        self.assertEqual(OperationLog.objects.get().tag, 'read_all')

    def test_filtered_select_is_logged_as_filtered(self):
        execute("SELECT * FROM students WHERE name LIKE '%asha%'", SQL)
        self.assertEqual(OperationLog.objects.get().tag, 'read_filtered')

    def test_insert_is_logged(self):
        execute("Student.objects.create(name='Ravi Kumar', email='ravi@example.com', "
                "phone='9123456780')", ORM)
        self.assertEqual(OperationLog.objects.get().tag, 'create')

    def test_refused_insert_is_logged_as_rejected(self):
        execute("INSERT INTO students (name, email, phone) "
                "VALUES ('Dup', 'asha@example.com', '9000000000')", SQL)
        log = OperationLog.objects.get()
        self.assertEqual(log.tag, 'create_rejected')
        self.assertEqual(log.status, OperationLog.REJECTED)

    def test_a_parse_error_is_not_logged(self):
        execute('SELECT * FROM nowhere', SQL)
        self.assertEqual(OperationLog.objects.count(), 0)

    def test_terminal_work_completes_an_exercise(self):
        from lab import exercises
        execute("SELECT * FROM students WHERE name LIKE '%asha%'", SQL)
        done = {e.number for e, complete in exercises.evaluate() if complete}
        self.assertIn(2, done)   # exercise 2 is the filtered SELECT


class TerminalEndpointTests(TestCase):
    """The JSON endpoint the browser console talks to."""

    def setUp(self):
        Student.objects.create(name='Asha Patil', email='asha@example.com',
                               phone='9876543210')
        self.url = reverse('students:terminal_run')

    def post(self, command, mode='sql'):
        return self.client.post(
            self.url, json.dumps({'command': command, 'mode': mode}),
            content_type='application/json')

    def test_page_renders(self):
        response = self.client.get(reverse('students:terminal'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Simulation — Terminal')

    def test_select_returns_json_rows(self):
        data = self.post('SELECT * FROM students').json()
        self.assertEqual(data['kind'], 'table')
        self.assertEqual(len(data['rows']), 1)

    def test_response_includes_the_live_row_count(self):
        self.assertEqual(self.post('SELECT * FROM students').json()['row_count'], 1)

    def test_errors_come_back_as_json_not_a_500(self):
        response = self.post('DROP TABLE students')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['kind'], 'error')

    def test_orm_mode_is_honoured(self):
        data = self.post('Student.objects.count()', mode='orm').json()
        self.assertEqual(data['kind'], 'table')

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_malformed_body_is_rejected(self):
        response = self.client.post(self.url, 'not json',
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)
