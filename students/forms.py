"""The form used to create and update a `Student`.

This form is the experiment's worked example of **custom field validation**.
Django runs validation in three stages, and one of each is shown here:

1. **Field validators** — `validate_phone` on the model field (see
   `students/validators.py`), run for every field value.
2. **`clean_<field>()`** — one method per field, for rules that concern a
   single field and may also normalise its value.
3. **`clean()`** — runs last, for rules that compare two or more fields.
"""

from django import forms

from .models import Student


class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = ['name', 'email', 'phone']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g. Asha Patil', 'autofocus': True}),
            'email': forms.EmailInput(attrs={'placeholder': 'e.g. asha@example.com'}),
            'phone': forms.TextInput(attrs={'placeholder': 'e.g. +919876543210'}),
        }
        help_texts = {
            'email': 'Must be unique — no two students may share an email address.',
            'phone': '7 to 15 digits, optionally starting with "+".',
        }

    # -- stage 2: one method per field -------------------------------------

    def clean_name(self):
        """Trim the name and require a sensible minimum length."""
        name = self.cleaned_data['name'].strip()
        if len(name) < 2:
            raise forms.ValidationError('Enter the full name (at least 2 characters).')
        return name

    def clean_email(self):
        """Normalise the email to lowercase so uniqueness is case-insensitive.

        Without this, 'ASHA@x.com' and 'asha@x.com' would be two different rows
        even though the UNIQUE constraint is meant to prevent exactly that.
        """
        return self.cleaned_data['email'].strip().lower()

    def clean_phone(self):
        """Strip the common separators people type before validating."""
        phone = self.cleaned_data['phone']
        for separator in (' ', '-', '(', ')'):
            phone = phone.replace(separator, '')
        return phone

    # -- stage 3: rules that span more than one field ----------------------

    def clean(self):
        """Cross-field rule: the name must not be reused as the email prefix.

        A contrived rule, but it demonstrates where a check belongs when it
        needs two cleaned values at once — `clean()` runs after every
        `clean_<field>()`, so both are already normalised here.
        """
        cleaned = super().clean()
        name = cleaned.get('name', '')
        email = cleaned.get('email', '')

        if name and email and '@' in email:
            local_part = email.split('@')[0]
            if local_part.isdigit():
                self.add_error(
                    'email',
                    'The part before "@" cannot be only digits — use a readable address.',
                )
        return cleaned
