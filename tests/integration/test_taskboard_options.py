from django.test import TestCase
from taiga.base.exceptions import ValidationError
from taiga.projects.models import Project, TaskStatus, UserStoryStatus
from taiga.projects.tasks.models import Task
from taiga.projects.userstories.models import UserStory
from taiga.projects.validators import ProjectValidator
from taiga.projects.taskboard import update_story_status, validate_options


class TaskboardOptionsTests(TestCase):
    def setUp(self):
        self.project = Project(name='Taskboard options', slug='taskboard-options')
        self.project._importing = True
        self.project.save()
        self.open_task = TaskStatus.objects.create(project=self.project, name='New')
        self.closed_task = TaskStatus.objects.create(project=self.project, name='Closed', is_closed=True)
        self.other_closed = TaskStatus.objects.create(project=self.project, name='Accepted', is_closed=True)
        self.open_story = UserStoryStatus.objects.create(project=self.project, name='Open')
        self.progress = UserStoryStatus.objects.create(project=self.project, name='In progress')
        self.done = UserStoryStatus.objects.create(project=self.project, name='Done', is_closed=True)
        self.options = dict(story_filters=True, automatic_status=True,
                            closed_task_statuses=[self.closed_task.pk, self.other_closed.pk],
                            closed_story_status=self.done.pk, opened_story_status=self.open_story.pk)
        self.project.taskboard_options = self.options
        self.project.save()
        self.story = UserStory.objects.create(project=self.project, subject='Story', status=self.progress)

    def task(self, status=None, story=None):
        return Task.objects.create(project=self.project, user_story=story or self.story,
                                   subject='Task', status=status or self.open_task)

    def status(self):
        self.story.refresh_from_db()
        return self.story.status_id

    def test_last_of_three_tasks_closes_story_and_reopening_reopens(self):
        tasks = [self.task() for _ in range(3)]
        for task in tasks[:2]:
            task.status = self.closed_task
            task.save()
            self.assertEqual(self.status(), self.progress.pk)
        tasks[2].status = self.other_closed
        tasks[2].save()
        self.assertEqual(self.status(), self.done.pk)
        tasks[0].status = self.open_task
        tasks[0].save()
        self.assertEqual(self.status(), self.open_story.pk)

    def test_single_task_and_new_unfinished_task(self):
        task = self.task()
        task.status = self.closed_task
        task.save()
        self.assertEqual(self.status(), self.done.pk)
        self.task()
        self.assertEqual(self.status(), self.open_story.pk)

    def test_disabled_keeps_existing_status(self):
        self.project.taskboard_options = dict(self.options, automatic_status=False)
        self.project.save()
        self.task(self.closed_task)
        self.assertEqual(self.status(), self.progress.pk)

    def test_unselected_closed_status_does_not_complete(self):
        other = TaskStatus.objects.create(project=self.project, name='Excluded closed', is_closed=True)
        self.task(other)
        self.assertEqual(self.status(), self.progress.pk)

    def test_empty_story_and_unrelated_task(self):
        update_story_status(self.story.pk)
        Task.objects.create(project=self.project, subject='Unrelated', status=self.closed_task)
        self.assertEqual(self.status(), self.progress.pk)

    def test_deleting_unfinished_task_completes_remaining_tasks(self):
        unfinished = self.task()
        self.task(self.closed_task)
        unfinished.delete()
        self.assertEqual(self.status(), self.done.pk)

    def test_move_recalculates_both_stories(self):
        self.task(self.closed_task)
        unfinished = self.task()
        second = UserStory.objects.create(project=self.project, subject='Second', status=self.done)
        unfinished.user_story = second
        unfinished.save()
        second.refresh_from_db()
        self.assertEqual(self.status(), self.done.pk)
        self.assertEqual(second.status_id, self.open_story.pk)

    def test_deleted_or_reclassified_configuration_is_safe(self):
        self.closed_task.is_closed = False
        self.closed_task.save()
        self.task(self.other_closed)
        self.assertEqual(self.status(), self.progress.pk)

    def test_validator_rejects_invalid_and_cross_project_statuses(self):
        for patch in [dict(story_filters='false'), dict(automatic_status=True, closed_task_statuses=[]),
                      dict(closed_task_statuses=[self.open_task.pk]), dict(opened_story_status=self.done.pk),
                      dict(closed_story_status=self.open_story.pk), dict(closed_task_statuses=[999999]),
                      dict(closed_task_statuses='bad')]:
            with self.subTest(patch=patch), self.assertRaises(ValidationError):
                validate_options(dict(self.options, **patch), self.project)
        other = Project(name='Other', slug='other'); other._importing = True; other.save()
        foreign = TaskStatus.objects.create(project=other, name='Closed', is_closed=True)
        with self.assertRaises(ValidationError):
            validate_options(dict(self.options, closed_task_statuses=[foreign.pk]), self.project)

    def test_project_validator_roundtrip(self):
        validator = ProjectValidator(self.project, data={'taskboard_options': self.options}, partial=True)
        self.assertTrue(validator.is_valid(), validator.errors)
        validator.save()
        self.project.refresh_from_db()
        self.assertEqual(self.project.taskboard_options, self.options)

    def test_defaults_and_version(self):
        self.assertEqual(Project().taskboard_options, {})
        old_version = self.story.version
        self.task(self.closed_task)
        self.assertEqual(self.status(), self.done.pk)
        self.assertEqual(self.story.version, old_version + 1)
        update_story_status(self.story.pk)
        self.story.refresh_from_db()
        self.assertEqual(self.story.version, old_version + 1)
