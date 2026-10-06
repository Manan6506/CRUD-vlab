from django.db import models
from django.urls import reverse

from .validators import validate_not_numeric, validate_phone


class Student(models.Model):
    """The table under test in this experiment: students(id, name, email, phone).

    Validators are attached to the fields rather than to the form, so the same
    rules are enforced by the HTML form, the REST API and the admin alike.
    """

    id = models.AutoField(primary_key=True)
    name = models.CharField(
        max_length=100,
        validators=[validate_not_numeric],
    )
    email = models.EmailField(
        unique=True,
        error_messages={'unique': 'A student with this email already exists — '
                                  'the UNIQUE constraint refused the row.'},
    )
    phone = models.CharField(max_length=16, validators=[validate_phone])

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f'{self.id} - {self.name}'

    def get_absolute_url(self):
        """Canonical URL for one row, built from the named URL pattern."""
        return reverse('students:detail', args=[self.pk])


class OperationLog(models.Model):
    """One entry in the statement log: an operation attempted on the table.

    Every attempt is recorded, including ones the database refused, so that the
    Exercises section can check what the student has actually done. Two fields
    make that possible:

    * `status`  — whether the statement succeeded or was rejected (shown to the
      student as a badge in the statement log).
    * `tag`     — a short machine-readable marker, e.g. ``read_filtered``, that
      the exercise checkers match on. Matching on a tag rather than on the
      English text of `note` keeps the checkers stable if the wording changes.
    """

    CREATE = 'CREATE'
    READ = 'READ'
    UPDATE = 'UPDATE'
    DELETE = 'DELETE'
    OPERATIONS = [
        (CREATE, 'Create'),
        (READ, 'Read'),
        (UPDATE, 'Update'),
        (DELETE, 'Delete'),
    ]

    OK = 'OK'
    REJECTED = 'REJECTED'
    STATUSES = [
        (OK, 'Succeeded'),
        (REJECTED, 'Rejected by a constraint'),
    ]

    operation = models.CharField(max_length=10, choices=OPERATIONS)
    tag = models.CharField(
        max_length=32,
        blank=True,
        help_text='Machine-readable marker used to auto-check exercises.',
    )
    status = models.CharField(max_length=10, choices=STATUSES, default=OK)
    sql = models.TextField(help_text='Equivalent SQL for the operation performed.')
    orm = models.TextField(help_text='The Django ORM call the view made.')
    http = models.CharField(max_length=120, help_text='HTTP method and path.')
    rows_affected = models.IntegerField(default=0)
    note = models.CharField(max_length=200, blank=True)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-at', '-id']

    def __str__(self):
        return f'{self.operation} @ {self.at:%H:%M:%S}'

    @property
    def rejected(self):
        return self.status == self.REJECTED

    @classmethod
    def record(cls, operation, tag, sql, orm, http,
               rows_affected=0, note='', status=OK):
        return cls.objects.create(
            operation=operation,
            tag=tag,
            status=status,
            sql=sql,
            orm=orm,
            http=http,
            rows_affected=rows_affected,
            note=note,
        )
