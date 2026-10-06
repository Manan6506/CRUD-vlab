"""The REST API for the `Student` table.

One `ModelViewSet` provides all five endpoints — list, create, retrieve,
update and destroy — which the router in `studentproject/urls.py` maps to URLs.
Visit ``/api/students/`` in a browser to use DRF's browsable API.
"""

from rest_framework import viewsets

from .models import Student
from .serializers import StudentSerializer


class StudentViewSet(viewsets.ModelViewSet):
    """CRUD over `Student`, as JSON.

    This is the same four operations the simulator performs through HTML forms,
    exposed over HTTP verbs instead:

    ===========================  ========  ====================================
    URL                          Method    Operation
    ===========================  ========  ====================================
    ``/api/students/``           GET       READ (many)
    ``/api/students/``           POST      CREATE
    ``/api/students/<id>/``      GET       READ (one)
    ``/api/students/<id>/``      PUT       UPDATE
    ``/api/students/<id>/``      DELETE    DELETE
    ===========================  ========  ====================================
    """

    queryset = Student.objects.all()
    serializer_class = StudentSerializer
