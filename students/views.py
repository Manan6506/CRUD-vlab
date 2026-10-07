"""Views for the CRUD simulator.

Each view performs one of the four operations on the `students` table and
records what it did in `OperationLog`, together with the SQL statement the
operation corresponds to. The log is what the Simulation section displays and
what the Exercises section checks against.
"""

import json

from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import terminal, trace
from .forms import StudentForm
from .models import OperationLog, Student
from .sample_data import reset_experiment

TABLE = 'students'


def quote(value):
    """Render a Python value as a SQL literal, **for display only**.

    The real query never interpolates values like this — the ORM sends the
    statement and its parameters separately. See the Theory section.
    """
    if value is None:
        return 'NULL'
    return "'{}'".format(str(value).replace("'", "''"))


@require_POST
def reset(request):
    """Restore the table to its initial four rows and clear the log."""
    count = reset_experiment()
    messages.success(request, f'Reset. Table restored to {count} rows; statement log cleared.')
    return redirect('students:simulator')


# ---------------------------------------------------------------------------
# READ
# ---------------------------------------------------------------------------

def simulator(request):
    """READ (many) — the simulator: live table state plus a SELECT runner."""
    query = request.GET.get('q', '').strip()
    students = Student.objects.all()

    if query:
        students = students.filter(
            Q(name__icontains=query)
            | Q(email__icontains=query)
            | Q(phone__icontains=query)
        )
        pattern = quote(f'%{query}%')
        sql = (
            f'SELECT id, name, email, phone FROM {TABLE}\n'
            f'WHERE name LIKE {pattern}\n'
            f'   OR email LIKE {pattern}\n'
            f'   OR phone LIKE {pattern}\n'
            f'ORDER BY id;'
        )
        orm = (
            'Student.objects.filter(\n'
            f'    Q(name__icontains={quote(query)})\n'
            f'    | Q(email__icontains={quote(query)})\n'
            f'    | Q(phone__icontains={quote(query)})\n'
            ')'
        )
        tag, note = 'read_filtered', f'Filtered on {quote(query)}'
    else:
        sql = f'SELECT id, name, email, phone FROM {TABLE}\nORDER BY id;'
        orm = 'Student.objects.all()'
        tag, note = 'read_all', 'No filter — every row returned'

    rows = list(students)

    # Only log when the SELECT was deliberately run, not on every page load.
    if 'q' in request.GET:
        OperationLog.record(
            OperationLog.READ, tag, sql=sql, orm=orm,
            http=f'GET {request.get_full_path()}',
            rows_affected=len(rows), note=note,
        )

    return render(request, 'students/simulator.html', {
        'students': rows,
        'query': query,
        'sql': sql,
        'orm': orm,
        'ran_select': 'q' in request.GET,
        'log': OperationLog.objects.all()[:8],
        'log_total': OperationLog.objects.count(),
        'trace': trace.for_read(single=False),
        'trace_title': 'SELECT · what a read touches',
    })


def student_detail(request, pk):
    """READ (one) — select a single row by primary key."""
    student = get_object_or_404(Student, pk=pk)
    sql = f'SELECT id, name, email, phone FROM {TABLE}\nWHERE id = {pk};'
    orm = f'Student.objects.get(pk={pk})'
    OperationLog.record(
        OperationLog.READ, 'read_one', sql=sql, orm=orm, http=f'GET /simulation/{pk}/',
        rows_affected=1, note=f'Lookup by primary key id = {pk}',
    )
    return render(request, 'students/student_detail.html', {
        'student': student, 'sql': sql, 'orm': orm,
        'http': f'GET /simulation/{pk}/',
        'trace': trace.for_read(single=True),
        'trace_title': f'SELECT … WHERE id = {pk}',
    })


# ---------------------------------------------------------------------------
# CREATE
# ---------------------------------------------------------------------------

def student_create(request):
    """CREATE — insert a row. The database assigns the primary key."""
    if request.method == 'POST':
        form = StudentForm(request.POST)
        if form.is_valid():
            student = form.save()
            sql = (
                f'INSERT INTO {TABLE} (name, email, phone)\n'
                f'VALUES ({quote(student.name)}, {quote(student.email)}, {quote(student.phone)});'
            )
            orm = (
                'Student.objects.create(\n'
                f'    name={quote(student.name)},\n'
                f'    email={quote(student.email)},\n'
                f'    phone={quote(student.phone)},\n'
                ')'
            )
            OperationLog.record(
                OperationLog.CREATE, 'create', sql=sql, orm=orm, http='POST /simulation/add/',
                rows_affected=1, note=f'Database assigned id = {student.id}',
            )
            messages.success(
                request,
                f'INSERT succeeded. 1 row added; the database assigned id = {student.id}.',
            )
            return redirect('students:simulator')

        # The row was refused. Log the rejection too — the Exercises section
        # asks the student to trigger a constraint violation deliberately.
        OperationLog.record(
            OperationLog.CREATE, 'create_rejected',
            sql=_attempted_insert_sql(form),
            orm='form.is_valid()  # -> False, no SQL was sent',
            http='POST /simulation/add/',
            rows_affected=0,
            status=OperationLog.REJECTED,
            note=_first_error(form),
        )
        messages.error(request, 'INSERT rejected — the row violates a constraint. See below.')
    else:
        form = StudentForm()

    return render(request, 'students/student_form.html', {
        'form': form,
        'operation': 'CREATE',
        'title': 'Insert a row',
        'lead': 'Supply the three data columns. You do not supply <code>id</code> — '
                'the database generates it.',
        'submit_label': 'Run INSERT',
        'sql': f'INSERT INTO {TABLE} (name, email, phone)\n'
               "VALUES ('<name>', '<email>', '<phone>');",
        'orm': "Student.objects.create(name='<name>', email='<email>', phone='<phone>')",
        'http': 'POST /simulation/add/',
        'trace': trace.for_create(),
        'trace_title': 'INSERT · what submitting this form touches',
    })


# ---------------------------------------------------------------------------
# UPDATE
# ---------------------------------------------------------------------------

def student_update(request, pk):
    """UPDATE — change columns of an existing row, identified by primary key."""
    student = get_object_or_404(Student, pk=pk)
    before = {f: getattr(student, f) for f in ('name', 'email', 'phone')}

    if request.method == 'POST':
        form = StudentForm(request.POST, instance=student)
        if form.is_valid():
            student = form.save()
            changed = [f for f in before if before[f] != getattr(student, f)]
            columns = changed or ['name', 'email', 'phone']
            assignments = ',\n    '.join(f'{f} = {quote(getattr(student, f))}' for f in columns)

            sql = f'UPDATE {TABLE}\nSET {assignments}\nWHERE id = {student.id};'
            orm = (
                f'obj = Student.objects.get(pk={student.id})\n'
                + '\n'.join(f'obj.{f} = {quote(getattr(student, f))}' for f in columns)
                + '\nobj.save()'
            )
            OperationLog.record(
                OperationLog.UPDATE, 'update', sql=sql, orm=orm,
                http=f'POST /simulation/{student.id}/edit/', rows_affected=1,
                note=('Columns changed: ' + ', '.join(changed)) if changed
                     else 'No column values changed',
            )
            messages.success(
                request,
                f'UPDATE succeeded. 1 row affected; id {student.id} unchanged'
                + (f' (changed: {", ".join(changed)}).' if changed else '.'),
            )
            return redirect('students:simulator')

        OperationLog.record(
            OperationLog.UPDATE, 'update_rejected',
            sql=f'UPDATE {TABLE} SET ... WHERE id = {student.id};',
            orm='form.is_valid()  # -> False, no SQL was sent',
            http=f'POST /simulation/{student.id}/edit/',
            rows_affected=0, status=OperationLog.REJECTED, note=_first_error(form),
        )
        messages.error(request, 'UPDATE rejected — the new values violate a constraint.')
    else:
        form = StudentForm(instance=student)

    return render(request, 'students/student_form.html', {
        'form': form,
        'student': student,
        'operation': 'UPDATE',
        'title': f'Update row id = {student.id}',
        'lead': 'The row is located by its primary key. Changing a value here rewrites '
                'that column in place — no new row is created.',
        'submit_label': 'Run UPDATE',
        'sql': f'UPDATE {TABLE}\nSET name = ..., email = ..., phone = ...\n'
               f'WHERE id = {student.id};',
        'orm': f'obj = Student.objects.get(pk={student.id})\nobj.phone = ...\nobj.save()',
        'http': f'POST /simulation/{student.id}/edit/',
        'trace': trace.for_update(student.id),
        'trace_title': f'UPDATE · what saving row {student.id} touches',
    })


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------

def student_delete(request, pk):
    """DELETE — remove a row, identified by primary key."""
    student = get_object_or_404(Student, pk=pk)
    sql = f'DELETE FROM {TABLE}\nWHERE id = {student.id};'
    orm = f'Student.objects.get(pk={student.id}).delete()'

    if request.method == 'POST':
        deleted_id, name = student.id, student.name
        student.delete()
        OperationLog.record(
            OperationLog.DELETE, 'delete', sql=sql, orm=orm,
            http=f'POST /simulation/{deleted_id}/delete/', rows_affected=1,
            note=f'Removed {name!r}; id {deleted_id} is not reused',
        )
        messages.success(
            request,
            f'DELETE succeeded. 1 row removed. Note that id {deleted_id} will not be reused.',
        )
        return redirect('students:simulator')

    return render(request, 'students/student_confirm_delete.html', {
        'student': student, 'sql': sql, 'orm': orm,
        'operation': 'DELETE', 'http': f'POST /simulation/{student.id}/delete/',
        'trace': trace.for_delete(student.id),
        'trace_title': f'DELETE · what removing row {student.id} touches',
    })


# ---------------------------------------------------------------------------
# Small helpers used when an operation is refused
# ---------------------------------------------------------------------------

def _first_error(form):
    """A one-line summary of why a form was rejected, for the statement log."""
    for field, errors in form.errors.items():
        label = 'form' if field == '__all__' else field
        return f'{label}: {errors[0]}'
    return 'Rejected'


def _attempted_insert_sql(form):
    """The INSERT that *would* have run, shown next to the rejection."""
    data = form.data
    return (
        f'-- refused before execution\n'
        f'INSERT INTO {TABLE} (name, email, phone)\n'
        f'VALUES ({quote(data.get("name", ""))}, '
        f'{quote(data.get("email", ""))}, {quote(data.get("phone", ""))});'
    )


# ---------------------------------------------------------------------------
# The simulated terminal
# ---------------------------------------------------------------------------

def terminal_console(request):
    """Render the terminal page. The console itself runs in the browser."""
    mode = 'orm' if request.GET.get('mode') == 'orm' else terminal.engine.SQL
    return render(request, 'students/terminal.html', {
        'mode': mode,
        'log_total': OperationLog.objects.count(),
        'trace': trace.for_terminal(writes=True, mode=mode),
        'trace_title': 'what a typed command touches',
    })


@require_POST
def terminal_run(request):
    """Execute one typed command and return the result as JSON.

    The command is parsed, never evaluated — see `students/terminal/` for why.
    """
    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'kind': 'error', 'message': 'Malformed request.'}, status=400)

    command = str(payload.get('command', ''))[:500]
    mode = terminal.engine.ORM if payload.get('mode') == 'orm' else terminal.engine.SQL

    result = terminal.execute(command, mode)
    data = result.as_dict()
    data['row_count'] = Student.objects.count()

    # The files this command passed through, so the console can print the route.
    # The lab's own statement-log write is left out: including it would label
    # the database 'changed' even for a SELECT, which is the opposite of the
    # point. The full panel below the console still shows it.
    writes = bool(result.tag and not result.failed
                  and result.operation != OperationLog.READ)
    steps = trace.for_terminal(writes=writes, mode=mode)
    data['files'] = [] if result.failed else [
        {'file': step.file, 'effect': step.effect, 'changed': step.changed}
        for step in steps if step.role != 'Statement log'
    ]
    return JsonResponse(data)
