"""Admin configuration for the `students` app.

Django's admin is generated from the models, but almost every useful feature is
opt-in. This module turns on the ones that matter for running the experiment:
column layout, search, filters, grouped edit forms, read-only computed columns
and a custom bulk action.
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import OperationLog, Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    """The table the experiment manipulates."""

    list_display = ('id', 'name', 'email', 'phone', 'created_at')
    list_display_links = ('name',)
    search_fields = ('name', 'email', 'phone')
    list_filter = ('created_at',)
    ordering = ('id',)
    list_per_page = 25
    date_hierarchy = 'created_at'

    # Group the edit form instead of showing one flat list of fields.
    fieldsets = (
        ('Identity', {
            'fields': ('name', 'email'),
            'description': 'Email is UNIQUE — saving a duplicate will be refused.',
        }),
        ('Contact', {
            'fields': ('phone',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    readonly_fields = ('created_at', 'updated_at')


class RejectedFilter(admin.SimpleListFilter):
    """A custom filter: show only succeeded or only refused statements.

    `status` is already a plain field, but writing the filter by hand shows how
    to build one for anything that is not a simple column.
    """

    title = 'outcome'
    parameter_name = 'outcome'

    def lookups(self, request, model_admin):
        return [('ok', 'Succeeded'), ('rejected', 'Rejected by a constraint')]

    def queryset(self, request, queryset):
        if self.value() == 'ok':
            return queryset.filter(status=OperationLog.OK)
        if self.value() == 'rejected':
            return queryset.filter(status=OperationLog.REJECTED)
        return queryset


@admin.register(OperationLog)
class OperationLogAdmin(admin.ModelAdmin):
    """Read-only audit of every statement the simulator ran."""

    list_display = ('at', 'operation', 'outcome', 'rows_affected', 'tag', 'note')
    list_filter = ('operation', RejectedFilter, 'at')
    search_fields = ('sql', 'note', 'http')
    ordering = ('-at',)
    list_per_page = 50

    # The log is a record of what happened; it should not be edited by hand.
    readonly_fields = ('operation', 'tag', 'status', 'sql', 'orm',
                       'http', 'rows_affected', 'note', 'at')

    def has_add_permission(self, request):
        return False

    @admin.display(description='Outcome', ordering='status')
    def outcome(self, obj):
        """Colour-code the status column so refusals stand out."""
        colour = '#c23434' if obj.rejected else '#1f8b4c'
        return format_html(
            '<b style="color:{}">{}</b>', colour, obj.get_status_display()
        )

    @admin.action(description='Delete selected log entries (clear history)')
    def clear_entries(self, request, queryset):
        deleted, _ = queryset.delete()
        self.message_user(request, f'{deleted} log entries removed.')

    actions = ['clear_entries']
