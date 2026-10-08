"""Template context shared by every page of the lab.

Registered in ``settings.TEMPLATES`` so the navigation rail, the pager and the
progress meter are not rebuilt by hand in each view that renders them.
"""

from django.urls import reverse

from students.models import Student

from . import content, exercises, navigation


def _resolve(entry):
    """Turn a configured link into {label, url}.

    An entry gives either `url_name` (a named pattern, resolved here) or a
    literal `url`. Resolving names means a changed path updates every link.
    """
    url = reverse(entry['url_name']) if 'url_name' in entry else entry['url']
    return {'label': entry['label'], 'url': url}


def _active_slug(request):
    """Work out which rail entry to highlight, from the matched URL.

    Deriving it from `resolver_match` rather than from each view's context
    means a view cannot forget to say where it is, and the simulator's
    sub-pages (add / edit / delete / terminal) stay under Simulation.
    """
    match = request.resolver_match
    if match is None:
        return None

    if match.app_name == 'students':
        return 'simulation'

    current = f'{match.namespace}:{match.url_name}'
    for entry in navigation.SECTIONS:
        if entry[2] == current:
            return entry[0]
    return None


def lab_nav(request):
    """Rail, pager, live row count and exercise progress."""
    active = _active_slug(request)
    previous, following = navigation.neighbours(active)
    done, total = exercises.progress()

    return {
        'breadcrumb': [_resolve(entry) for entry in content.BREADCRUMB],
        'footer_columns': [
            {'heading': column['heading'],
             'links': [_resolve(link) for link in column['links']]}
            for column in content.FOOTER_COLUMNS
        ],
        'footer_note': content.FOOTER_NOTE,
        'experiment_title': content.EXPERIMENT_TITLE,
        'institution_name': content.INSTITUTION_NAME,
        'institution_subtitle': content.INSTITUTION_SUBTITLE,
        'institution_line_1': content.INSTITUTION_LINE_1,
        'institution_line_2': content.INSTITUTION_LINE_2,
        'institution_url': content.INSTITUTION_URL,
        'nav_groups': navigation.grouped(active),
        'nav_sections': navigation.build(active),
        'nav_previous': previous,
        'nav_next': following,
        'nav_active': active,
        'nav_active_label': navigation.label_for(active),
        'row_count': Student.objects.count(),
        'done_count': done,
        'done_total': total,
        'done_percent': round(100 * done / total) if total else 0,
    }
