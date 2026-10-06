"""Template context shared by every page of the lab.

Registered in ``settings.TEMPLATES`` so the navigation rail, the pager and the
progress meter are not rebuilt by hand in each view that renders them.
"""

from students.models import Student

from . import exercises, navigation


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
