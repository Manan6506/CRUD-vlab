"""Project-level URL mapping.

This module is the single entry point Django consults for every request. It
delegates to each app's own ``urls.py`` with `include()`, which keeps app URLs
self-contained and lets the whole simulator be remounted at a different prefix
by changing one line here.

    /                 -> lab app        (the twelve sections of the experiment)
    /simulation/      -> students app   (the CRUD simulator)
    /api/             -> REST framework (JSON API over the same model)
    /admin/           -> Django admin
"""

from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from students.api import StudentViewSet

# The router generates the five REST URLs for the viewset automatically:
#   /api/students/        list, create
#   /api/students/<pk>/   retrieve, update, partial_update, destroy
router = DefaultRouter()
router.register(r'students', StudentViewSet, basename='student')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('simulation/', include('students.urls')),
    path('', include('lab.urls')),
]
