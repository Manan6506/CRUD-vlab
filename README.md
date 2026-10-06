# Virtual Lab — CRUD Operations on a Relational Database

A Django virtual-lab experiment, modelled on the Virtual Labs (vlabs.ac.in) format. A student
reads the theory, performs Create / Read / Update / Delete operations against a live database
table, and sees the SQL statement and Django ORM call behind each one.

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py seedlab
python manage.py runserver
```

Then open <http://127.0.0.1:8000/>.

> On this machine use `python`, not `python3` — `python3` resolves to Apple's
> `/usr/bin/python3`, which has no Django. See **Running it** below.

---

## 1. Where each required concept is demonstrated

This table is the quickest route into the code.

| Concept | Where to look | What it shows |
|---|---|---|
| **URL mapping** | [studentproject/urls.py](studentproject/urls.py), [lab/urls.py](lab/urls.py), [students/urls.py](students/urls.py) | `include()` to delegate per app, application namespaces, **named** patterns, the `<int:pk>` path converter, and a DRF router that generates URLs automatically |
| **Template rendering** | [lab/templates/lab/base.html](lab/templates/lab/base.html) | Template inheritance (`{% extends %}` / `{% block %}`), partials via `{% include %}` ([`_quiz.html`](lab/templates/lab/_quiz.html), [`_opspec.html`](students/templates/students/_opspec.html)), `{% url %}` instead of hard-coded paths, `{% static %}` for CSS |
| **Forms with custom field validation** | [students/forms.py](students/forms.py), [lab/forms.py](lab/forms.py), [students/validators.py](students/validators.py) | All three validation stages: field validators, `clean_<field>()` per field, and a form-wide `clean()` comparing two fields. `QuizForm` additionally builds its fields **dynamically** from the database |
| **Displaying data on templates** | [students/templates/students/simulator.html](students/templates/students/simulator.html) | Looping a queryset into a table, `{% if %}` / `{% empty %}` branches, filters (`date`, `pluralize`, `widthratio`), and rendering model properties |
| **Unit testing** | [students/tests.py](students/tests.py), [students/test_terminal.py](students/test_terminal.py), [lab/tests.py](lab/tests.py) | 132 tests across models, validators, forms, views, navigation, the API, the terminal parsers and the exercise checker |
| **Simulated terminal** | [students/terminal/](students/terminal/) | A command console with two modes. Input is **parsed, never evaluated** — see section 3 below |
| **REST API + serializers** | [students/serializers.py](students/serializers.py), [students/api.py](students/api.py) | A `ModelSerializer` with `validate_<field>()` hooks and `read_only_fields`, exposed through a `ModelViewSet`. Browsable at `/api/students/` |
| **Django admin** | [students/admin.py](students/admin.py), [lab/admin.py](lab/admin.py) | `list_display`, `list_filter`, `search_fields`, `fieldsets`, `readonly_fields`, `date_hierarchy`, a **custom `SimpleListFilter`**, **inlines** for related models, `@admin.display` computed columns with coloured HTML, and a custom bulk **action** |
| **Models & migrations** | [students/models.py](students/models.py), [lab/models.py](lab/models.py), [lab/migrations/0002_seed_questions.py](lab/migrations/0002_seed_questions.py) | Field types, `UniqueConstraint`, related names, model properties, and a **data migration** that seeds the quiz questions so no manual setup is needed |

---

### Interface

The experiment is laid out as a **navigation rail** grouping the twelve sections under
*Understand*, *Perform* and *More*, with a live exercise-progress meter at the top. The home page
carries a hero and a **clickable index** of all twelve sections, so there is no dead breadcrumb
text anywhere — every navigational element goes somewhere.

Typography is Inter (interface) and JetBrains Mono (code, identifiers, SQL), loaded from Google
Fonts with system fallbacks.

**Light and dark themes.** Every colour is a CSS custom property declared twice in
[lab.css](lab/static/lab/css/lab.css) — once on `:root`, once under `[data-theme="dark"]` — so
nothing below the palette blocks refers to a literal colour. The toggle in the top bar sets that
attribute on `<html>` and stores the choice in `localStorage`; an inline script in `<head>`
applies it before first paint so the page never flashes. The initial theme follows the operating
system's `prefers-color-scheme` until the student picks one.

---

## 2. The twelve sections

Each is a separate URL, which is what makes the sidebar work.

| # | Section | URL | Notes |
|---|---|---|---|
| 1 | Aim | `/` | Home page: aim and learning outcomes |
| 2 | Introduction | `/introduction/` | What CRUD is and why it matters |
| 3 | Theory | `/theory/` | CRUD↔SQL↔HTTP↔ORM mapping, schema, request flow |
| 4 | Case Study | `/case-study/` | A college records desk, and how each design decision answers a real failure |
| 5 | Pretest | `/pretest/` | 5 MCQs, scored and stored |
| 6 | Simulation | `/simulation/` | Visual mode — forms and a live table |
| 6 | Simulation | `/simulation/terminal/` | Terminal mode — type SQL or ORM commands |
| 7 | Procedure | `/procedure/` | Step-by-step instructions |
| 8 | Exercises | `/exercises/` | 7 tasks, **checked automatically** |
| 9 | Posttest | `/posttest/` | 5 MCQs about what was observed |
| 10 | References | `/references/` | Further reading |
| 11 | Contributors | `/contributors/` | **Placeholder names — edit `lab/content.py`** |
| 12 | Feedback | `/feedback/` | Validated form, stored and reviewable in the admin |

Plus `/api/students/` (REST API) and `/admin/` (admin site).

---

## 3. The simulated terminal

`/simulation/terminal/` gives the student a console: they type a command, press Enter, and see
terminal-style output. It has two modes, switchable at any time:

| Mode | What you type | Example |
|---|---|---|
| **SQL** | A subset of SQL | `SELECT * FROM students WHERE name LIKE '%asha%';` |
| **ORM** | A subset of Django ORM | `Student.objects.filter(name__icontains='asha')` |

After each command the console prints **the other form of the same command**, so a student can
run an operation one way and immediately see how it is written the other way.

### It is simulated, not a shell

This is the important design point, and the one worth explaining to an evaluator:

* There is **no shell, no filesystem and no code execution**. `eval()` is never called and typed
  input is never sent to the database as raw SQL.
* Input is **parsed** ([students/terminal/parsers.py](students/terminal/parsers.py)) into a
  `Command` object — an action plus validated filters and values. Every column name is checked
  against a whitelist and the only table reachable is `students`.
* The `Command` is then carried out through the ORM
  ([students/terminal/engine.py](students/terminal/engine.py)), which is also what lets the same
  command be rendered as both SQL and ORM.

Statements that would change the schema (`DROP`, `ALTER`, `PRAGMA`, `ATTACH`, …), other tables,
other models, and anything that is not one of the supported expressions are all refused with an
explanation. `DELETE` without a `WHERE` clause is refused too, so a student cannot wipe the table
by accident. There are tests for each of these in
[students/test_terminal.py](students/test_terminal.py).

Because the engine writes to the same statement log the forms use, **work done in the terminal
counts towards the Exercises** exactly as work done through the forms does.

---

## 4. How the auto-checked exercises work

This is the one non-obvious mechanism in the project, so it is worth explaining:

1. Every operation the simulator performs is written to `OperationLog`
   ([students/models.py](students/models.py)) along with a short machine-readable **`tag`** —
   `read_all`, `read_filtered`, `create_rejected`, `update`, and so on.
2. Each exercise in [lab/exercises.py](lab/exercises.py) carries a `rule`: a function that
   receives every logged statement and returns whether the task has been done.
3. The Exercises page calls `exercises.evaluate()` and renders the result.

Rejected operations are logged too (with `status=REJECTED`), which is what lets Exercise 5 —
"trigger the UNIQUE constraint" — be checked at all.

---

## 5. Project layout

```
studentproject/          project configuration
  settings.py              INSTALLED_APPS, templates, REST_FRAMEWORK
  urls.py                  top-level URL mapping + the DRF router

students/                the table under test, and the simulator
  models.py                Student, OperationLog
  validators.py            reusable field validators
  forms.py                 StudentForm — the custom-validation example
  views.py                 the five CRUD views, each logging its statement
  urls.py                  mounted at /simulation/
  serializers.py           StudentSerializer
  api.py                   StudentViewSet
  admin.py                 admin configuration
  sample_data.py           the initial dataset and the reset routine
  management/commands/
    seedlab.py             `python manage.py seedlab` — load the sample rows
  tests.py                 CRUD, form, model and API tests
  test_terminal.py         parser, engine, safety and endpoint tests
  terminal/                the simulated terminal
    parsers.py               SQL and ORM text -> Command (no eval)
    engine.py                executes a Command, renders both forms
    result.py                the structured result a command produces
  templates/students/      simulator, terminal, form, detail, delete-confirm

lab/                     the virtual lab itself
  models.py                Question, Choice, QuizAttempt, QuizAnswer, Feedback
  forms.py                 QuizForm (dynamic), FeedbackForm (custom validation)
  content.py               written content  <-- EDIT CONTRIBUTORS HERE
  navigation.py            the twelve sections, in order
  exercises.py             the seven tasks and their checking rules
  context_processors.py    sidebar, prev/next links, row count
  views.py                 one view per section
  urls.py                  one URL per section
  admin.py                 admin configuration
  tests.py                 section, navigation, quiz and feedback tests
  templates/lab/           base + one template per section
    _icons.html              SVG sprite used by the sidebar and headings
  static/lab/css/lab.css   the stylesheet (light + dark themes)
  migrations/0002_…        data migration seeding the quiz questions
```

---

## 6. Running it

```bash
python manage.py runserver
```

**Use `python`, not `python3`.** On this machine `python3` resolves to Apple's
`/usr/bin/python3`, which has no Django installed; `python` resolves to the miniconda
install that does. To remove the ambiguity entirely, create a virtualenv once:

```bash
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

If port 8000 is already taken by another project, pick another:

```bash
python manage.py runserver 8010
```

### Admin access

```bash
python manage.py createsuperuser
```

Then sign in at `/admin/` to edit quiz questions, review attempts and read feedback.

### Resetting the experiment

The **Reset** button on the Simulation page restores the table to its original four rows
(ids 1–4, by rewinding the primary-key sequence) and clears the statement log.

---

## 7. Tests

```bash
python manage.py test
```

132 tests. To run one app or one class:

```bash
python manage.py test lab.tests.FeedbackFormTests
```
