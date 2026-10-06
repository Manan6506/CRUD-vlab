"""Forms for the virtual lab.

These two forms are the lab's demonstration of Django form handling:

* `QuizForm` builds its fields **dynamically** from the questions in the
  database, so adding a question in the admin changes the form with no code
  change.
* `FeedbackForm` is a `ModelForm` with **custom field validation** — a
  `clean_<field>()` method per field, plus a form-wide `clean()` that validates
  one field against another.
"""

from django import forms

from .models import Choice, Feedback, Question


class QuizForm(forms.Form):
    """A multiple-choice test built at runtime from a list of `Question` rows.

    Django forms normally declare their fields as class attributes. A quiz has
    a different number of questions depending on which test is being taken, so
    the fields are instead added to `self.fields` inside `__init__`.
    """

    def __init__(self, *args, questions=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.questions = list(questions or [])

        for question in self.questions:
            self.fields[self.field_name(question)] = forms.ModelChoiceField(
                queryset=question.choices.all(),
                widget=forms.RadioSelect,
                empty_label=None,
                label=question.text,
                # Each question must be answered; see clean() for the message.
                required=True,
                error_messages={'required': 'Select an answer for this question.'},
            )

    @staticmethod
    def field_name(question):
        """The form field name used for a question, e.g. 'question_3'."""
        return f'question_{question.pk}'

    def clean(self):
        """Form-wide validation: refuse a partially completed test.

        Each field is already `required`, so Django reports the individual
        blanks. This adds one summary message so the student sees at the top of
        the form how many questions are still unanswered.
        """
        cleaned = super().clean()
        unanswered = [q for q in self.questions if not cleaned.get(self.field_name(q))]
        if unanswered and len(unanswered) < len(self.questions):
            raise forms.ValidationError(
                f'{len(unanswered)} of {len(self.questions)} questions are unanswered. '
                'Answer every question before submitting.'
            )
        return cleaned

    def answered_choices(self):
        """Yield (question, selected_choice) pairs for a valid, submitted form."""
        for question in self.questions:
            yield question, self.cleaned_data[self.field_name(question)]


class FeedbackForm(forms.ModelForm):
    """Feedback on the experiment, with per-field validation rules.

    Demonstrates the three validation hooks Django offers, in the order it runs
    them: field validators, `clean_<field>()`, then the form-wide `clean()`.
    """

    MIN_COMMENT_LENGTH = 15

    RATING_CHOICES = [
        (5, '5 — Excellent'),
        (4, '4 — Good'),
        (3, '3 — Average'),
        (2, '2 — Poor'),
        (1, '1 — Very poor'),
    ]

    rating = forms.TypedChoiceField(
        choices=RATING_CHOICES,
        coerce=int,
        widget=forms.RadioSelect,
        label='How would you rate this experiment?',
    )

    class Meta:
        model = Feedback
        fields = ['name', 'email', 'rating', 'comments']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Your name'}),
            'email': forms.EmailInput(attrs={'placeholder': 'you@college.edu (optional)'}),
            'comments': forms.Textarea(
                attrs={'rows': 5, 'placeholder': 'What worked well? What was confusing?'}
            ),
        }

    def clean_name(self):
        """Names must be non-blank and must not be a single character."""
        name = self.cleaned_data['name'].strip()
        if len(name) < 2:
            raise forms.ValidationError('Enter your full name (at least 2 characters).')
        return name

    def clean_email(self):
        """Email is optional, but store it lowercased when it is supplied."""
        return self.cleaned_data.get('email', '').strip().lower()

    def clean_comments(self):
        """Require a comment long enough to be useful."""
        comments = self.cleaned_data['comments'].strip()
        if len(comments) < self.MIN_COMMENT_LENGTH:
            raise forms.ValidationError(
                f'Please write at least {self.MIN_COMMENT_LENGTH} characters '
                f'(you wrote {len(comments)}).'
            )
        return comments

    def clean(self):
        """Cross-field rule: a low rating must be explained.

        `clean()` runs after every `clean_<field>()`, so it is the right place
        for a rule that depends on more than one field.
        """
        cleaned = super().clean()
        rating = cleaned.get('rating')
        comments = cleaned.get('comments', '')

        if rating is not None and rating <= 2 and len(comments) < 40:
            self.add_error(
                'comments',
                'You rated this experiment poorly — please describe the problem '
                'in at least 40 characters so it can be fixed.',
            )
        return cleaned
