"""URL mapping for the virtual lab's sections.

Each section of the experiment is a separate URL, which is what makes the
sidebar work and lets a student link directly to, say, the Theory page.

Patterns are **named** (``name='theory'``) and the whole module is given an
application namespace (``app_name = 'lab'``), so templates refer to a page as
``{% url 'lab:theory' %}``. Nothing hard-codes a path.
"""

from django.urls import path

from . import views

app_name = 'lab'

urlpatterns = [
    path('',              views.aim,           name='aim'),            # home page
    path('introduction/', views.introduction,  name='introduction'),
    path('theory/',       views.theory,        name='theory'),
    path('case-study/',   views.case_study,    name='case_study'),
    path('pretest/',      views.pretest,       name='pretest'),
    # 'simulation/' is served by the students app — see studentproject/urls.py
    path('procedure/',    views.procedure,     name='procedure'),
    path('exercises/',    views.exercise_list, name='exercises'),
    path('posttest/',     views.posttest,      name='posttest'),
    path('references/',   views.references,    name='references'),
    path('contributors/', views.contributors,  name='contributors'),
    path('feedback/',     views.feedback,      name='feedback'),
]
