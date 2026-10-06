"""REST framework serializers for the `Student` model.

A *serializer* does for JSON what a `Form` does for HTML: it converts incoming
data to validated Python objects, and model instances back out to primitive
types ready to be rendered as JSON.

`ModelSerializer` reads the field list and the validators straight off the
model, so the rules defined in `students/validators.py` apply to the API as
well as to the HTML form — without being written twice.
"""

from rest_framework import serializers

from .models import Student


class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = ['id', 'name', 'email', 'phone', 'created_at', 'updated_at']
        # `id` is assigned by the database; the timestamps are maintained by
        # the model. None of them may be set through the API.
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_email(self, value):
        """Mirror of `StudentForm.clean_email` — normalise before storing.

        DRF names this hook `validate_<field>` where a Django form would say
        `clean_<field>`; the role is identical.
        """
        return value.strip().lower()

    def validate_name(self, value):
        name = value.strip()
        if len(name) < 2:
            raise serializers.ValidationError('Enter the full name (at least 2 characters).')
        return name
