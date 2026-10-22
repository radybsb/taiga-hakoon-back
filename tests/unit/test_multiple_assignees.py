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
