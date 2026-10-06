"""Unit tests for the `students` app.

Grouped by what is being tested, so the suite reads as a description of the
app's behaviour:

* `StudentModelTests`      — the model and its validators
* `StudentFormTests`       — custom form validation
* `CrudViewTests`          — the four operations through the HTML views
* `StatementLogTests`      — what gets recorded, including refusals
* `ResetTests`             — restoring the initial dataset
* `StudentApiTests`        — the same operations through the REST API
"""

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .forms import StudentForm
from .models import OperationLog, Student
from .validators import validate_phone


class StudentModelTests(TestCase):
    """The model, its constraints and its field validators."""

    def test_str_includes_id_and_name(self):
        student = Student.objects.create(
            name='Asha Patil', email='asha@example.com', phone='9876543210'
        )
        self.assertEqual(str(student), f'{student.id} - Asha Patil')

    def test_get_absolute_url_uses_named_pattern(self):
        student = Student.objects.create(
            name='Asha Patil', email='asha@example.com', phone='9876543210'
        )
        self.assertEqual(student.get_absolute_url(), f'/simulation/{student.pk}/')

    def test_phone_validator_accepts_valid_numbers(self):
        for number in ('9876543210', '+919876543210', '1234567'):
            with self.subTest(number=number):
                validate_phone(number)  # must not raise

    def test_phone_validator_rejects_invalid_numbers(self):
        for number in ('abc1234567', '12345', '+' + '9' * 20, '98765 43210'):
            with self.subTest(number=number):
                with self.assertRaises(ValidationError):
                    validate_phone(number)

    def test_rows_are_ordered_by_primary_key(self):
        Student.objects.create(name='B', email='b@example.com', phone='9000000002')
        Student.objects.create(name='A', email='a@example.com', phone='9000000001')
        self.assertEqual(
            [s.name for s in Student.objects.all()], ['B', 'A']
        )


class StudentFormTests(TestCase):
    """The three stages of validation the form performs."""

    def valid_data(self, **overrides):
        data = {'name': 'Asha Patil', 'email': 'asha@example.com', 'phone': '9876543210'}
        data.update(overrides)
        return data

    def test_accepts_valid_input(self):
        self.assertTrue(StudentForm(data=self.valid_data()).is_valid())

    def test_clean_name_rejects_single_character(self):
        form = StudentForm(data=self.valid_data(name='A'))
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)

    def test_clean_email_lowercases(self):
        form = StudentForm(data=self.valid_data(email='ASHA@Example.COM'))
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['email'], 'asha@example.com')

    def test_clean_phone_strips_separators(self):
        form = StudentForm(data=self.valid_data(phone='+91 98765-43210'))
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['phone'], '+919876543210')

    def test_cross_field_clean_rejects_numeric_email_prefix(self):
        """The form-wide clean() compares name and email together."""
        form = StudentForm(data=self.valid_data(email='12345@example.com'))
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_duplicate_email_is_refused(self):
        Student.objects.create(name='Asha', email='asha@example.com', phone='9876543210')
        form = StudentForm(data=self.valid_data(name='Someone Else'))
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)


class CrudViewTests(TestCase):
    """The four operations performed through the HTML interface."""

    def setUp(self):
        self.student = Student.objects.create(
            name='Asha Patil', email='asha@example.com', phone='+919876543210'
        )

    # -- READ ---------------------------------------------------------------

    def test_simulator_lists_rows(self):
        response = self.client.get(reverse('students:simulator'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Asha Patil')

    def test_detail_shows_one_row(self):
        response = self.client.get(reverse('students:detail', args=[self.student.pk]))
        self.assertContains(response, 'asha@example.com')

    def test_detail_404s_for_a_missing_row(self):
        response = self.client.get(reverse('students:detail', args=[9999]))
        self.assertEqual(response.status_code, 404)

    def test_filter_builds_a_where_clause(self):
        Student.objects.create(name='Ravi Kumar', email='ravi@example.com', phone='9123456780')
        response = self.client.get(reverse('students:simulator'), {'q': 'ravi'})
        self.assertContains(response, 'Ravi Kumar')
        self.assertNotContains(response, 'Asha Patil')

    # -- CREATE -------------------------------------------------------------

    def test_create_inserts_a_row(self):
        response = self.client.post(reverse('students:create'), {
            'name': 'Ravi Kumar', 'email': 'ravi@example.com', 'phone': '9123456780',
        })
        self.assertRedirects(response, reverse('students:simulator'))
        self.assertTrue(Student.objects.filter(email='ravi@example.com').exists())

    def test_create_is_refused_for_a_duplicate_email(self):
        response = self.client.post(reverse('students:create'), {
            'name': 'Someone Else', 'email': 'asha@example.com', 'phone': '9000000000',
        })
        self.assertEqual(response.status_code, 200)   # redisplayed, not redirected
        self.assertEqual(Student.objects.count(), 1)

    # -- UPDATE -------------------------------------------------------------

    def test_update_preserves_the_primary_key(self):
        original_pk = self.student.pk
        response = self.client.post(reverse('students:update', args=[original_pk]), {
            'name': 'Asha Patil', 'email': 'asha@example.com', 'phone': '+919876543211',
        })
        self.assertRedirects(response, reverse('students:simulator'))
        self.student.refresh_from_db()
        self.assertEqual(self.student.pk, original_pk)
        self.assertEqual(self.student.phone, '+919876543211')

    # -- DELETE -------------------------------------------------------------

    def test_delete_removes_the_row(self):
        response = self.client.post(reverse('students:delete', args=[self.student.pk]))
        self.assertRedirects(response, reverse('students:simulator'))
        self.assertEqual(Student.objects.count(), 0)

    def test_delete_requires_post(self):
        """A GET shows the confirmation page and must not delete anything."""
        response = self.client.get(reverse('students:delete', args=[self.student.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Student.objects.count(), 1)

    def test_deleted_id_is_not_reused(self):
        deleted_id = self.student.pk
        self.client.post(reverse('students:delete', args=[deleted_id]))
        self.client.post(reverse('students:create'), {
            'name': 'New Student', 'email': 'new@example.com', 'phone': '9000000000',
        })
        self.assertGreater(Student.objects.get(email='new@example.com').pk, deleted_id)


class StatementLogTests(TestCase):
    """Every attempt is recorded, with a tag the exercises can match on."""

    def setUp(self):
        self.student = Student.objects.create(
            name='Asha Patil', email='asha@example.com', phone='+919876543210'
        )

    def test_page_load_alone_is_not_logged(self):
        self.client.get(reverse('students:simulator'))
        self.assertEqual(OperationLog.objects.count(), 0)

    def test_running_select_logs_read_all(self):
        self.client.get(reverse('students:simulator'), {'q': ''})
        log = OperationLog.objects.get()
        self.assertEqual(log.tag, 'read_all')
        self.assertEqual(log.rows_affected, 1)

    def test_filtered_select_logs_read_filtered(self):
        self.client.get(reverse('students:simulator'), {'q': 'asha'})
        self.assertEqual(OperationLog.objects.get().tag, 'read_filtered')

    def test_detail_logs_read_one(self):
        self.client.get(reverse('students:detail', args=[self.student.pk]))
        self.assertEqual(OperationLog.objects.get().tag, 'read_one')

    def test_create_logs_the_insert(self):
        self.client.post(reverse('students:create'), {
            'name': 'Ravi Kumar', 'email': 'ravi@example.com', 'phone': '9123456780',
        })
        log = OperationLog.objects.get()
        self.assertEqual(log.tag, 'create')
        self.assertEqual(log.status, OperationLog.OK)
        self.assertIn('INSERT INTO students', log.sql)

    def test_refused_create_is_logged_as_rejected(self):
        self.client.post(reverse('students:create'), {
            'name': 'Someone Else', 'email': 'asha@example.com', 'phone': '9000000000',
        })
        log = OperationLog.objects.get()
        self.assertEqual(log.tag, 'create_rejected')
        self.assertEqual(log.status, OperationLog.REJECTED)
        self.assertEqual(log.rows_affected, 0)
        self.assertTrue(log.rejected)

    def test_update_logs_changed_columns(self):
        self.client.post(reverse('students:update', args=[self.student.pk]), {
            'name': 'Asha Patil', 'email': 'asha@example.com', 'phone': '+919876543211',
        })
        log = OperationLog.objects.get()
        self.assertEqual(log.tag, 'update')
        self.assertIn('phone', log.note)

    def test_delete_logs_the_statement(self):
        self.client.post(reverse('students:delete', args=[self.student.pk]))
        log = OperationLog.objects.get()
        self.assertEqual(log.tag, 'delete')
        self.assertIn('DELETE FROM students', log.sql)


class ResetTests(TestCase):
    """Reset returns the table to a known, reproducible state."""

    def test_reset_restores_four_rows_and_clears_the_log(self):
        Student.objects.create(name='Temp', email='temp@example.com', phone='9000000000')
        self.client.get(reverse('students:simulator'), {'q': ''})
        response = self.client.post(reverse('students:reset'))
        self.assertRedirects(response, reverse('students:simulator'))
        self.assertEqual(Student.objects.count(), 4)
        self.assertEqual(OperationLog.objects.count(), 0)

    def test_reset_restarts_ids_from_one(self):
        for index in range(3):
            Student.objects.create(
                name=f'X{index}', email=f'x{index}@example.com', phone='9000000000'
            )
        Student.objects.all().delete()
        self.client.post(reverse('students:reset'))
        self.assertEqual(list(Student.objects.values_list('id', flat=True)), [1, 2, 3, 4])

    def test_reset_rejects_get(self):
        self.assertEqual(self.client.get(reverse('students:reset')).status_code, 405)


class StudentApiTests(TestCase):
    """The same four operations, performed over the REST API."""

    def setUp(self):
        self.student = Student.objects.create(
            name='Asha Patil', email='asha@example.com', phone='+919876543210'
        )
        self.list_url = '/api/students/'
        self.detail_url = f'/api/students/{self.student.pk}/'

    def test_list_returns_rows_as_json(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['results'][0]['name'], 'Asha Patil')

    def test_retrieve_returns_one_row(self):
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['email'], 'asha@example.com')

    def test_create_adds_a_row(self):
        response = self.client.post(self.list_url, {
            'name': 'Ravi Kumar', 'email': 'ravi@example.com', 'phone': '9123456780',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Student.objects.count(), 2)

    def test_update_changes_a_row(self):
        response = self.client.put(self.detail_url, {
            'name': 'Asha Patil', 'email': 'asha@example.com', 'phone': '+919999999999',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.student.refresh_from_db()
        self.assertEqual(self.student.phone, '+919999999999')

    def test_delete_removes_a_row(self):
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(Student.objects.count(), 0)

    def test_serializer_enforces_the_phone_validator(self):
        """The model's validator applies to the API as well as the form."""
        response = self.client.post(self.list_url, {
            'name': 'Bad Phone', 'email': 'bad@example.com', 'phone': 'not-a-number',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('phone', response.json())

    def test_serializer_enforces_unique_email(self):
        response = self.client.post(self.list_url, {
            'name': 'Duplicate', 'email': 'asha@example.com', 'phone': '9000000000',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('email', response.json())

    def test_id_is_read_only(self):
        """An id supplied by the client is ignored — the database assigns it."""
        response = self.client.post(self.list_url, {
            'id': 999, 'name': 'Ravi Kumar', 'email': 'ravi@example.com', 'phone': '9123456780',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertNotEqual(response.json()['id'], 999)
