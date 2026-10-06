"""Reusable field validators for the Student model.

A *validator* is any callable that raises `ValidationError` for a bad value.
Attaching one to a model field means the rule is enforced everywhere — model
forms, the admin, the REST API and `full_clean()` — from a single definition.
"""

import re

from django.core.exceptions import ValidationError

PHONE_PATTERN = re.compile(r'^\+?\d{7,15}$')


def validate_phone(value):
    """Accept 7–15 digits, optionally prefixed with '+'.

    Written as an explicit function rather than a `RegexValidator` so the error
    message can explain *which* rule was broken.
    """
    digits = value.lstrip('+')

    if not digits.isdigit():
        raise ValidationError(
            'Phone number may contain only digits, with an optional leading "+". '
            'Remove any spaces, dashes or brackets.'
        )
    if not PHONE_PATTERN.match(value):
        raise ValidationError(
            f'Phone number must be 7 to 15 digits long (you entered {len(digits)}).'
        )


def validate_not_numeric(value):
    """Reject a name that is only digits, e.g. '12345'."""
    if value.strip().isdigit():
        raise ValidationError('A name cannot be made up only of digits.')
