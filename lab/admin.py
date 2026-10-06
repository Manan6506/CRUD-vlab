"""Admin configuration for the virtual lab.

Lets an instructor edit quiz questions without touching code, and review
student attempts and feedback.
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import Choice, Feedback, Question, QuizAnswer, QuizAttempt


class ChoiceInline(admin.TabularInline):
    """Edit a question's answers on the same page as the question itself.

    An *inline* is how the admin presents a foreign-key relationship: `Choice`
    rows point at `Question`, so they are edited inside the question's form.
    """

    model = Choice
    extra = 4
    min_num = 2
    fields = ('text', 'is_correct')


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('order', 'stage', 'text', 'answer_count', 'correct_answer')
    list_display_links = ('text',)
    list_filter = ('stage',)
    search_fields = ('text', 'explanation')
    ordering = ('stage', 'order')
    inlines = [ChoiceInline]

    fieldsets = (
        (None, {'fields': ('stage', 'order', 'text')}),
        ('After submission', {
            'fields': ('explanation',),
            'description': 'Shown to the student once they submit the test.',
        }),
    )

    @admin.display(description='Choices')
    def answer_count(self, obj):
        return obj.choices.count()

    @admin.display(description='Correct answer')
    def correct_answer(self, obj):
        choice = obj.correct_choice
        if choice is None:
            return format_html('<b style="color:#c23434">none set</b>')
        return choice.text


class QuizAnswerInline(admin.TabularInline):
    """The individual answers that made up an attempt — read only."""

    model = QuizAnswer
    extra = 0
    can_delete = False
    readonly_fields = ('question', 'choice', 'is_correct')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ('submitted_at', 'stage', 'result', 'percentage_display')
    list_filter = ('stage', 'submitted_at')
    ordering = ('-submitted_at',)
    readonly_fields = ('stage', 'score', 'total', 'submitted_at')
    inlines = [QuizAnswerInline]
    date_hierarchy = 'submitted_at'

    def has_add_permission(self, request):
        return False

    @admin.display(description='Score', ordering='score')
    def result(self, obj):
        return f'{obj.score} / {obj.total}'

    @admin.display(description='Percentage')
    def percentage_display(self, obj):
        colour = '#1f8b4c' if obj.passed else '#b0740b'
        return format_html('<b style="color:{}">{}%</b>', colour, obj.percentage)


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('submitted_at', 'name', 'stars', 'email', 'short_comment')
    list_filter = ('rating', 'submitted_at')
    search_fields = ('name', 'email', 'comments')
    ordering = ('-submitted_at',)
    readonly_fields = ('submitted_at',)

    @admin.display(description='Rating', ordering='rating')
    def stars(self, obj):
        return '★' * obj.rating + '☆' * (5 - obj.rating)

    @admin.display(description='Comment')
    def short_comment(self, obj):
        if len(obj.comments) <= 60:
            return obj.comments
        return obj.comments[:60] + '…'
