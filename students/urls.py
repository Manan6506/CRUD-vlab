"""URL mapping for the CRUD simulator.

Mounted by the project URLconf under ``/simulation/``, so the full path for
`create` is ``/simulation/add/``. Every pattern is **named**, which is what lets
templates write ``{% url 'students:create' %}`` instead of hard-coding paths —
change a path here and every link follows automatically.
"""

from django.urls import path

from . import views

app_name = 'students'

urlpatterns = [
    # READ (many) — the simulator itself
    path('', views.simulator, name='simulator'),

    # CREATE
    path('add/', views.student_create, name='create'),

    # READ (one). <int:pk> is a *path converter*: it matches digits only and
    # passes the value to the view as an int named `pk`.
    path('<int:pk>/', views.student_detail, name='detail'),

    # UPDATE
    path('<int:pk>/edit/', views.student_update, name='update'),

    # DELETE
    path('<int:pk>/delete/', views.student_delete, name='delete'),

    # The simulated terminal: a page, and the endpoint its console calls
    path('terminal/', views.terminal_console, name='terminal'),
    path('terminal/run/', views.terminal_run, name='terminal_run'),

    # Restore the initial dataset
    path('reset/', views.reset, name='reset'),
]
