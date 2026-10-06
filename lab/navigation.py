"""The experiment's sections, used to build the navigation rail.

Defined once here so the rail, the previous/next links, the index grid on the
home page and the tests all agree on the order and grouping of the experiment.
"""

from django.urls import reverse

#: Sections, in order. Each is
#: (slug, label, url name, icon, group, one-line blurb for the index grid).
#:
#: `icon` names a <symbol> in lab/_icons.html. `group` is the heading the
#: section appears under in the rail.
SECTIONS = [
    ('aim', 'Aim', 'lab:aim', 'target', 'Understand',
     'What the experiment sets out to demonstrate.'),
    ('introduction', 'Introduction', 'lab:introduction', 'book', 'Understand',
     'Why every application reduces to four operations.'),
    ('theory', 'Theory', 'lab:theory', 'layers', 'Understand',
     'CRUD mapped to SQL, HTTP and the Django ORM.'),
    ('case-study', 'Case Study', 'lab:case_study', 'case', 'Understand',
     'A college records desk, and four real failures.'),

    ('pretest', 'Pretest', 'lab:pretest', 'check', 'Perform',
     'Five questions before you begin.'),
    ('procedure', 'Procedure', 'lab:procedure', 'list', 'Perform',
     'The steps to follow, in order.'),
    ('simulation', 'Simulation', 'students:simulator', 'play', 'Perform',
     'Run the operations — by form or by terminal.'),
    ('exercises', 'Exercises', 'lab:exercises', 'tasks', 'Perform',
     'Seven tasks, checked automatically.'),
    ('posttest', 'Posttest', 'lab:posttest', 'award', 'Perform',
     'Five questions on what you observed.'),

    ('references', 'References', 'lab:references', 'link', 'More',
     'Documentation and further reading.'),
    ('contributors', 'Contributors', 'lab:contributors', 'users', 'More',
     'Who built this experiment.'),
    ('feedback', 'Feedback', 'lab:feedback', 'chat', 'More',
     'Tell us what worked and what did not.'),
]

#: The group headings, in the order they appear in the rail.
GROUPS = ['Understand', 'Perform', 'More']


def build(active_slug=None):
    """Return every section as a dict, flagging which one is open."""
    return [
        {
            'slug': slug, 'label': label, 'url': reverse(url_name),
            'icon': icon, 'group': group, 'blurb': blurb,
            'active': slug == active_slug, 'number': index,
        }
        for index, (slug, label, url_name, icon, group, blurb)
        in enumerate(SECTIONS, start=1)
    ]


def grouped(active_slug=None):
    """The same sections, bucketed by group, for the rail."""
    entries = build(active_slug)
    return [
        {'name': name, 'items': [e for e in entries if e['group'] == name]}
        for name in GROUPS
    ]


def neighbours(active_slug):
    """Return the (previous, next) section dicts, for the pager."""
    entries = build(active_slug)
    slugs = [entry['slug'] for entry in entries]
    if active_slug not in slugs:
        return None, None
    position = slugs.index(active_slug)
    previous = entries[position - 1] if position > 0 else None
    following = entries[position + 1] if position < len(entries) - 1 else None
    return previous, following


def label_for(slug):
    """The human label of a section."""
    for entry in SECTIONS:
        if entry[0] == slug:
            return entry[1]
    return ''
