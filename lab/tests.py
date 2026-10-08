"""Unit tests for the virtual lab.

* `SectionPageTests`   — every section of the experiment renders
* `NavigationTests`    — the sidebar and previous/next links
* `QuizFormTests`      — the dynamically built quiz form
* `QuizViewTests`      — scoring and storing an attempt
* `FeedbackFormTests`  — each custom validation rule
* `FeedbackViewTests`  — storing a valid submission
* `ExerciseTests`      — auto-checking against the statement log
"""

from django.test import TestCase
from django.urls import reverse

from students.models import OperationLog, Student

from . import exercises, navigation
from .forms import FeedbackForm, QuizForm
from .models import Choice, Feedback, Question, QuizAttempt


class SectionPageTests(TestCase):
    """Every section listed in the sidebar must resolve and render."""

    def test_every_section_returns_200(self):
        for slug, label, url_name, _icon, _group, _blurb in navigation.SECTIONS:
            with self.subTest(section=slug):
                response = self.client.get(reverse(url_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, label)

    def test_home_page_is_the_aim(self):
        response = self.client.get('/')
        self.assertContains(response, 'Learning Objectives')
        self.assertContains(response, 'Performing CRUD Operations')

    def test_home_page_links_to_every_section(self):
        """The index grid on the home page is the clickable table of contents."""
        response = self.client.get('/')
        for entry in navigation.build():
            with self.subTest(section=entry['slug']):
                self.assertContains(response, f'href="{entry["url"]}"')

    def test_every_breadcrumb_entry_is_a_link(self):
        """Regression: the breadcrumb used to be unclickable placeholder text.

        It is back, because the Virtual Labs house style has one — but every
        entry must resolve to a real URL, which is what was wrong before.
        """
        from . import content
        response = self.client.get(reverse('lab:theory'))
        self.assertTrue(response.context['breadcrumb'])
        self.assertEqual(len(response.context['breadcrumb']), len(content.BREADCRUMB))
        for entry in response.context['breadcrumb']:
            with self.subTest(crumb=entry['label']):
                self.assertTrue(entry['url'], f'{entry["label"]} has no URL')
                self.assertContains(
                    response, f'<a href="{entry["url"]}">{entry["label"]}</a>',
                    html=False,
                )

    def test_footer_links_all_resolve(self):
        response = self.client.get(reverse('lab:aim'))
        for column in response.context['footer_columns']:
            for link in column['links']:
                with self.subTest(link=link['label']):
                    self.assertTrue(link['url'])

    def test_masthead_shows_the_configured_institution(self):
        from . import content
        response = self.client.get(reverse('lab:aim'))
        self.assertContains(response, content.INSTITUTION_NAME)

    def test_theory_lists_all_four_operations(self):
        response = self.client.get(reverse('lab:theory'))
        for operation in ('CREATE', 'READ', 'UPDATE', 'DELETE'):
            self.assertContains(response, operation)

    def test_contributors_shows_the_configured_people(self):
        from . import content
        response = self.client.get(reverse('lab:contributors'))
        self.assertContains(response, content.CONTRIBUTORS[0]['name'])


class NavigationTests(TestCase):
    """The sidebar highlights the current page and links to its neighbours."""

    def test_sidebar_marks_the_active_section(self):
        entries = navigation.build('theory')
        active = [entry for entry in entries if entry['active']]
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]['slug'], 'theory')

    def test_neighbours_of_a_middle_section(self):
        previous, following = navigation.neighbours('theory')
        self.assertEqual(previous['slug'], 'introduction')
        self.assertEqual(following['slug'], 'case-study')

    def test_first_section_has_no_previous(self):
        previous, following = navigation.neighbours('aim')
        self.assertIsNone(previous)
        self.assertEqual(following['slug'], 'introduction')

    def test_last_section_has_no_next(self):
        previous, following = navigation.neighbours('feedback')
        self.assertEqual(previous['slug'], 'contributors')
        self.assertIsNone(following)

    def test_simulator_pages_highlight_the_simulation_section(self):
        """A sub-page of the simulator still shows Simulation as active."""
        student = Student.objects.create(
            name='Asha', email='asha@example.com', phone='9876543210'
        )
        response = self.client.get(reverse('students:update', args=[student.pk]))
        self.assertEqual(response.status_code, 200)
        active = [e for e in response.context['nav_sections'] if e['active']]
        self.assertEqual(active[0]['slug'], 'simulation')


class QuizFormTests(TestCase):
    """The quiz form builds its fields from the questions in the database."""

    def setUp(self):
        self.question = Question.objects.create(stage=Question.PRETEST, order=99, text='Q?')
        self.right = Choice.objects.create(question=self.question, text='yes', is_correct=True)
        self.wrong = Choice.objects.create(question=self.question, text='no', is_correct=False)

    def test_a_field_is_built_for_each_question(self):
        form = QuizForm(questions=[self.question])
        self.assertIn(f'question_{self.question.pk}', form.fields)

    def test_valid_when_every_question_is_answered(self):
        form = QuizForm(
            data={f'question_{self.question.pk}': self.right.pk},
            questions=[self.question],
        )
        self.assertTrue(form.is_valid())

    def test_invalid_when_a_question_is_unanswered(self):
        form = QuizForm(data={}, questions=[self.question])
        self.assertFalse(form.is_valid())

    def test_answered_choices_pairs_question_with_selection(self):
        form = QuizForm(
            data={f'question_{self.question.pk}': self.wrong.pk},
            questions=[self.question],
        )
        self.assertTrue(form.is_valid())
        pairs = list(form.answered_choices())
        self.assertEqual(pairs, [(self.question, self.wrong)])


class QuizViewTests(TestCase):
    """Taking a test scores it and stores the attempt."""

    def answers_for(self, stage, correct=True):
        """Build POST data answering every question of `stage`."""
        data = {}
        for question in Question.objects.filter(stage=stage):
            choice = question.choices.filter(is_correct=correct).first()
            data[f'question_{question.pk}'] = choice.pk
        return data

    def test_questions_were_seeded_by_the_data_migration(self):
        self.assertEqual(Question.objects.filter(stage=Question.PRETEST).count(), 5)
        self.assertEqual(Question.objects.filter(stage=Question.POSTTEST).count(), 5)

    def test_every_question_has_exactly_one_correct_choice(self):
        for question in Question.objects.all():
            with self.subTest(question=question.pk):
                self.assertEqual(question.choices.filter(is_correct=True).count(), 1)

    def test_pretest_renders_its_questions(self):
        response = self.client.get(reverse('lab:pretest'))
        self.assertEqual(len(response.context['questions']), 5)

    def test_the_form_does_not_reveal_which_answer_is_correct(self):
        """Regression test: Choice.__str__ is used as the radio-button label,
        so it must not leak correctness onto the page."""
        response = self.client.get(reverse('lab:pretest'))
        body = response.content.decode()
        self.assertNotIn('(correct)', body)
        self.assertNotIn('(incorrect)', body)

    def test_all_correct_scores_full_marks(self):
        response = self.client.post(
            reverse('lab:pretest'), self.answers_for(Question.PRETEST, correct=True)
        )
        attempt = response.context['attempt']
        self.assertEqual(attempt.score, 5)
        self.assertEqual(attempt.total, 5)
        self.assertEqual(attempt.percentage, 100)
        self.assertTrue(attempt.passed)

    def test_all_wrong_scores_zero(self):
        response = self.client.post(
            reverse('lab:posttest'), self.answers_for(Question.POSTTEST, correct=False)
        )
        attempt = response.context['attempt']
        self.assertEqual(attempt.score, 0)
        self.assertFalse(attempt.passed)

    def test_the_attempt_and_its_answers_are_stored(self):
        self.client.post(reverse('lab:pretest'), self.answers_for(Question.PRETEST))
        attempt = QuizAttempt.objects.get()
        self.assertEqual(attempt.stage, Question.PRETEST)
        self.assertEqual(attempt.answers.count(), 5)

    def test_an_incomplete_submission_is_rejected(self):
        data = self.answers_for(Question.PRETEST)
        data.pop(next(iter(data)))          # drop one answer
        response = self.client.post(reverse('lab:pretest'), data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(QuizAttempt.objects.count(), 0)

    def test_percentage_handles_an_empty_test(self):
        attempt = QuizAttempt(stage=Question.PRETEST, score=0, total=0)
        self.assertEqual(attempt.percentage, 0)


class FeedbackFormTests(TestCase):
    """Each custom validation rule on the feedback form."""

    def valid_data(self, **overrides):
        data = {
            'name': 'Asha Patil',
            'email': 'asha@example.com',
            'rating': 5,
            'comments': 'Clear and well explained throughout.',
        }
        data.update(overrides)
        return data

    def test_accepts_valid_feedback(self):
        self.assertTrue(FeedbackForm(data=self.valid_data()).is_valid())

    def test_email_is_optional(self):
        self.assertTrue(FeedbackForm(data=self.valid_data(email='')).is_valid())

    def test_rejects_a_one_character_name(self):
        form = FeedbackForm(data=self.valid_data(name='A'))
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)

    def test_rejects_a_short_comment(self):
        form = FeedbackForm(data=self.valid_data(comments='Good'))
        self.assertFalse(form.is_valid())
        self.assertIn('comments', form.errors)

    def test_low_rating_requires_a_longer_explanation(self):
        """The form-wide clean() compares rating against comments."""
        form = FeedbackForm(data=self.valid_data(rating=1, comments='It was not good.'))
        self.assertFalse(form.is_valid())
        self.assertIn('comments', form.errors)

    def test_low_rating_is_accepted_with_a_full_explanation(self):
        form = FeedbackForm(data=self.valid_data(
            rating=1,
            comments='The simulation did not make it clear which id the new row received.',
        ))
        self.assertTrue(form.is_valid())

    def test_email_is_normalised_to_lowercase(self):
        form = FeedbackForm(data=self.valid_data(email='ASHA@Example.COM'))
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['email'], 'asha@example.com')


class FeedbackViewTests(TestCase):
    def test_valid_feedback_is_saved_and_redirects(self):
        response = self.client.post(reverse('lab:feedback'), {
            'name': 'Asha Patil', 'email': 'asha@example.com',
            'rating': 4, 'comments': 'The statement log was the most useful part.',
        })
        self.assertRedirects(response, reverse('lab:feedback'))
        self.assertEqual(Feedback.objects.count(), 1)

    def test_invalid_feedback_is_not_saved(self):
        response = self.client.post(reverse('lab:feedback'), {
            'name': 'A', 'rating': 4, 'comments': 'short',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Feedback.objects.count(), 0)


class ExerciseTests(TestCase):
    """Exercises are marked complete from the statement log."""

    def log(self, tag, operation=OperationLog.READ):
        OperationLog.record(operation, tag, sql='...', orm='...', http='...')

    def test_nothing_is_complete_initially(self):
        completed, total = exercises.progress()
        self.assertEqual(completed, 0)
        self.assertEqual(total, 7)

    def test_an_exercise_completes_when_its_tag_is_logged(self):
        self.log('read_all')
        results = dict(
            (exercise.number, done) for exercise, done in exercises.evaluate()
        )
        self.assertTrue(results[1])
        self.assertFalse(results[2])

    def test_all_seven_tags_complete_every_exercise(self):
        for tag in ('read_all', 'read_filtered', 'read_one',
                    'create', 'create_rejected', 'update', 'delete'):
            self.log(tag)
        completed, total = exercises.progress()
        self.assertEqual(completed, total)

    def test_exercise_page_reports_progress(self):
        self.log('read_all')
        response = self.client.get(reverse('lab:exercises'))
        self.assertEqual(response.context['completed'], 1)
        self.assertEqual(response.context['total'], 7)
        self.assertFalse(response.context['all_done'])

    def test_performing_an_operation_completes_its_exercise(self):
        """End to end: use the simulator, then check the exercise page."""
        Student.objects.create(name='Asha', email='asha@example.com', phone='9876543210')
        self.client.get(reverse('students:simulator'), {'q': 'asha'})
        response = self.client.get(reverse('lab:exercises'))
        completed = {e.number for e, done in response.context['results'] if done}
        self.assertIn(2, completed)   # exercise 2 is the filtered SELECT
