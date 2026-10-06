"""The dataset the simulator starts from, and the reset routine."""

from django.core.management.color import no_style
from django.db import connection

from .models import OperationLog, Student

SAMPLES = [
    ('Asha Patil', 'asha.patil@example.com', '+919876543210'),
    ('Ravi Kumar', 'ravi.kumar@example.com', '9123456780'),
    ('Meera Nair', 'meera.nair@example.com', '+919812345678'),
    ('Jatin Shah', 'jatin.shah@example.com', '9988776655'),
]


def load_samples():
    """Insert the sample rows that are missing. Returns how many were created."""
    created = 0
    for name, email, phone in SAMPLES:
        _, was_created = Student.objects.get_or_create(
            email=email, defaults={'name': name, 'phone': phone}
        )
        created += int(was_created)
    return created


def _reset_pk_sequence():
    """Rewind the primary-key counter so a reset starts again from id = 1."""
    statements = connection.ops.sequence_reset_by_name_sql(
        no_style(),
        [{'table': Student._meta.db_table, 'column': Student._meta.pk.column}],
    )
    if statements:
        with connection.cursor() as cursor:
            for sql in statements:
                cursor.execute(sql)


def reset_experiment():
    """Return the table to its initial state: rows 1-4, empty statement log."""
    Student.objects.all().delete()
    OperationLog.objects.all().delete()
    _reset_pk_sequence()
    for name, email, phone in SAMPLES:
        Student.objects.create(name=name, email=email, phone=phone)
    return Student.objects.count()
