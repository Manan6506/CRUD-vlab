"""Database models for the virtual lab itself.

Two features are stored here:

* the Pretest / Posttest quizzes (`Question`, `Choice`, `QuizAttempt`,
  `QuizAnswer`), and
* the feedback students leave about the experiment (`Feedback`).

The data the student *manipulates* during the experiment lives in the
`students` app; this app only stores data *about* the experiment.
"""

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Question(models.Model):
    """One multiple-choice question belonging to either the pre- or post-test."""

    PRETEST = 'PRE'
    POSTTEST = 'POST'
    STAGE_CHOICES = [
        (PRETEST, 'Pretest'),
        (POSTTEST, 'Posttest'),
    ]

    stage = models.CharField(
        max_length=4,
        choices=STAGE_CHOICES,
        help_text='Which test this question appears in.',
    )
    order = models.PositiveIntegerField(
        default=1,
        help_text='Position of the question within its test.',
    )
    text = models.CharField(max_length=300)
    explanation = models.TextField(
        blank=True,
        help_text='Shown after submission to explain the correct answer.',
    )

    class Meta:
        ordering = ['stage', 'order']
        # A test cannot have two questions in the same position.
        constraints = [
            models.UniqueConstraint(fields=['stage', 'order'], name='unique_question_order'),
        ]

    def __str__(self):
        return f'[{self.get_stage_display()} Q{self.order}] {self.text[:50]}'

    @property
    def correct_choice(self):
        return self.choices.filter(is_correct=True).first()


class Choice(models.Model):
    """One selectable answer for a `Question`. Exactly one should be correct."""

    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=200)
    is_correct = models.BooleanField(default=False)

    class Meta:
        ordering = ['id']

    def __str__(self):
        """Return the answer text only.

        IMPORTANT: this string is what `ModelChoiceField` renders as the label
        of each radio button in the quiz, so it must never reveal whether the
        choice is the correct one. Correctness is shown in the admin through
        the `is_correct` column instead.
        """
        return self.text


class QuizAttempt(models.Model):
    """One completed submission of a test.

    Attempts are anonymous — no login is required to run the experiment — but
    every attempt is stored so an instructor can review them in the admin.
    """

    stage = models.CharField(max_length=4, choices=Question.STAGE_CHOICES)
    score = models.PositiveIntegerField(help_text='Number of questions answered correctly.')
    total = models.PositiveIntegerField(help_text='Number of questions in the test.')
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f'{self.get_stage_display()} — {self.score}/{self.total}'

    @property
    def percentage(self):
        """Score as a whole-number percentage, guarding against an empty test."""
        if not self.total:
            return 0
        return round(100 * self.score / self.total)

    @property
    def passed(self):
        return self.percentage >= 60


class QuizAnswer(models.Model):
    """The choice a student selected for one question of an attempt."""

    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    choice = models.ForeignKey(Choice, on_delete=models.CASCADE)
    is_correct = models.BooleanField()

    class Meta:
        ordering = ['question__order']

    def __str__(self):
        return f'Q{self.question.order}: {"correct" if self.is_correct else "incorrect"}'


class Feedback(models.Model):
    """Feedback submitted from the Feedback section of the lab."""

    name = models.CharField(max_length=100)
    email = models.EmailField(blank=True, help_text='Optional.')
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text='1 (poor) to 5 (excellent).',
    )
    comments = models.TextField()
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-submitted_at']
        verbose_name_plural = 'feedback'

    def __str__(self):
        return f'{self.name} — {self.rating}/5'
