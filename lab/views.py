"""Views for the twelve sections of the virtual lab.

Most sections are static: they render a template with content taken from
`lab/content.py`. Three do real work:

* `pretest` / `posttest` — build a form from the questions in the database,
  score the submission and store the attempt;
* `exercises`            — checks the simulator's statement log to decide which
                           tasks the student has completed;
* `feedback`             — validates and stores a feedback form.
"""

from django.contrib import messages
from django.shortcuts import redirect, render

from . import content, exercises
from .forms import FeedbackForm, QuizForm
from .models import Feedback, Question, QuizAnswer, QuizAttempt


# ---------------------------------------------------------------------------
# Static sections
# ---------------------------------------------------------------------------

def aim(request):
    """Home page of the experiment."""
    return render(request, 'lab/aim.html')


def introduction(request):
    return render(request, 'lab/introduction.html')


def theory(request):
    return render(request, 'lab/theory.html', {
        'mapping': content.CRUD_MAPPING,
        'schema': content.SCHEMA,
        'flow': content.REQUEST_FLOW,
    })


def case_study(request):
    return render(request, 'lab/case_study.html')


def procedure(request):
    return render(request, 'lab/procedure.html', {'steps': content.PROCEDURE_STEPS})


def references(request):
    return render(request, 'lab/references.html', {'references': content.REFERENCES})


def contributors(request):
    return render(request, 'lab/contributors.html', {
        'contributors': content.CONTRIBUTORS,
        'institution': content.INSTITUTION,
    })


# ---------------------------------------------------------------------------
# Pretest and Posttest
# ---------------------------------------------------------------------------

def _run_quiz(request, stage, template):
    """Shared logic for both tests.

    GET  — render an empty form built from this stage's questions.
    POST — validate, score, store the attempt, and show per-question feedback.
    """
    questions = list(
        Question.objects.filter(stage=stage).prefetch_related('choices')
    )

    if request.method == 'POST':
        form = QuizForm(request.POST, questions=questions)
        if form.is_valid():
            attempt = _score_and_store(form, stage)
            return render(request, template, {
                'form': form,
                'questions': questions,
                'attempt': attempt,
                'results': attempt.answers.select_related('question', 'choice'),
                'stage_label': dict(Question.STAGE_CHOICES)[stage],
            })
    else:
        form = QuizForm(questions=questions)

    return render(request, template, {
        'form': form,
        'questions': questions,
        'stage_label': dict(Question.STAGE_CHOICES)[stage],
        'previous_best': QuizAttempt.objects.filter(stage=stage).order_by('-score').first(),
    })


def _score_and_store(form, stage):
    """Mark a validated submission and save it as a `QuizAttempt`."""
    selections = list(form.answered_choices())
    score = sum(1 for _question, choice in selections if choice.is_correct)

    attempt = QuizAttempt.objects.create(stage=stage, score=score, total=len(selections))
    QuizAnswer.objects.bulk_create([
        QuizAnswer(
            attempt=attempt,
            question=question,
            choice=choice,
            is_correct=choice.is_correct,
        )
        for question, choice in selections
    ])
    return attempt


def pretest(request):
    return _run_quiz(request, Question.PRETEST, 'lab/pretest.html')


def posttest(request):
    return _run_quiz(request, Question.POSTTEST, 'lab/posttest.html')


# ---------------------------------------------------------------------------
# Exercises
# ---------------------------------------------------------------------------

def exercise_list(request):
    """Show every task, marking the ones the statement log proves were done."""
    results = exercises.evaluate()
    completed = sum(1 for _exercise, done in results if done)
    return render(request, 'lab/exercises.html', {
        'results': results,
        'completed': completed,
        'total': len(results),
        'all_done': completed == len(results),
    })


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

def feedback(request):
    """Collect feedback on the experiment, validated by `FeedbackForm`."""
    if request.method == 'POST':
        form = FeedbackForm(request.POST)
        if form.is_valid():
            entry = form.save()
            messages.success(
                request,
                f'Thank you, {entry.name}. Your feedback has been recorded.',
            )
            # Redirect after a successful POST so a refresh does not resubmit.
            return redirect('lab:feedback')
        messages.error(request, 'Your feedback was not saved — please correct the errors below.')
    else:
        form = FeedbackForm()

    return render(request, 'lab/feedback.html', {
        'form': form,
        'responses_so_far': Feedback.objects.count(),
    })
