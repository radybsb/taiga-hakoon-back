import importlib
import pytest

from .. import factories as f
from taiga.projects.mixins.serializers import AssignedUsersSerializerMixin

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('app,name', [('tasks', 'Task'), ('issues', 'Issue'), ('epics', 'Epic')])
def test_multiple_assignees_persist_and_remove_individually(app, name):
    project = f.ProjectFactory()
    users = [f.UserFactory(), f.UserFactory()]
    for user in users:
        f.MembershipFactory(project=project, user=user)
    item = getattr(f, name + 'Factory')(project=project, assigned_to=users[0])
    validator_class = getattr(importlib.import_module('taiga.projects.' + app + '.validators'), name + 'Validator')
    for selected in [users, users[1:], []]:
        ids = [user.id for user in selected]
        validator = validator_class(item, data={'assigned_users': ids, 'assigned_to': ids[0] if ids else None}, partial=True)
        assert validator.is_valid(), validator.errors
        item = validator.save()
        assert AssignedUsersSerializerMixin(item).data['assigned_users'] == sorted(ids)


@pytest.mark.parametrize('app,name', [('tasks', 'Task'), ('issues', 'Issue'), ('epics', 'Epic')])
def test_assignees_must_belong_to_project(app, name):
    item = getattr(f, name + 'Factory')()
    outsider = f.UserFactory()
    validator_class = getattr(importlib.import_module('taiga.projects.' + app + '.validators'), name + 'Validator')
    validator = validator_class(item, data={'assigned_users': [outsider.id]}, partial=True)
    assert not validator.is_valid()


def test_bulk_stories_apply_assignees_and_reject_outsiders():
    from types import SimpleNamespace
    from taiga.projects.userstories.api import UserStoryViewSet
    from taiga.projects.userstories.models import UserStory
    from taiga.projects.userstories.validators import UserStoriesBulkValidator
    seed = f.create_userstory()
    project = seed.project
    status = f.UserStoryStatusFactory(project=project)
    users = [f.UserFactory(), f.UserFactory()]
    for user in users:
        f.MembershipFactory(project=project, user=user)
    ids = [user.id for user in users]
    data = {'project_id': project.id, 'status_id': status.id,
            'bulk_stories': 'Bulk first\nBulk second', 'assigned_users': ids}
    view = UserStoryViewSet()
    view.action = 'bulk_create'
    view.kwargs = {}
    view.request = SimpleNamespace(DATA=data, QUERY_PARAMS={}, user=seed.owner)
    view.check_permissions = lambda *args: None
    view.pre_save = lambda *args: None
    view.post_save = lambda *args, **kwargs: None
    view.persist_history_snapshot = lambda **kwargs: None
    response = view.bulk_create(view.request)
    assert response.status_code == 200
    stories = UserStory.objects.filter(project=project, subject__startswith='Bulk ')
    assert stories.count() == 2
    for story in stories:
        assert set(story.assigned_users.values_list('id', flat=True)) == set(ids)
        assert story.assigned_to_id == ids[0]
    for invalid in [f.UserFactory(), f.UserFactory(is_active=False)]:
        if not invalid.is_active:
            f.MembershipFactory(project=project, user=invalid)
        validator = UserStoriesBulkValidator(data=dict(data, assigned_users=[invalid.id]))
        assert not validator.is_valid()


def test_bulk_tasks_apply_assignees_and_reject_outsiders():
    from types import SimpleNamespace
    from taiga.projects.tasks.api import TaskViewSet
    from taiga.projects.tasks.models import Task
    from taiga.projects.tasks.validators import TasksBulkValidator
    seed = f.create_userstory()
    project = seed.project
    status = f.TaskStatusFactory(project=project)
    users = [f.UserFactory(), f.UserFactory()]
    for user in users:
        f.MembershipFactory(project=project, user=user)
    ids = [user.id for user in users]
    data = {'project_id': project.id, 'status_id': status.id,
            'bulk_tasks': 'Bulk first\nBulk second', 'assigned_users': ids, 'milestone_id': seed.milestone_id, 'us_id': seed.id}
    view = TaskViewSet()
    view.action = 'bulk_create'
    view.kwargs = {}
    view.request = SimpleNamespace(DATA=data, QUERY_PARAMS={}, user=seed.owner)
    view.check_permissions = lambda *args: None
    view.pre_save = lambda *args: None
    view.post_save = lambda *args, **kwargs: None
    view.persist_history_snapshot = lambda **kwargs: None
    response = view.bulk_create(view.request)
    assert response.status_code == 200
    stories = Task.objects.filter(project=project, subject__startswith='Bulk ')
    assert stories.count() == 2
    for story in stories:
        assert set(story.assigned_users.values_list('id', flat=True)) == set(ids)
        assert story.assigned_to_id == ids[0]
    for invalid in [f.UserFactory(), f.UserFactory(is_active=False)]:
        if not invalid.is_active:
            f.MembershipFactory(project=project, user=invalid)
        validator = TasksBulkValidator(data=dict(data, assigned_users=[invalid.id]))
        assert not validator.is_valid()
