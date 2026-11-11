import pytest
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from taiga.projects.attachments.models import Attachment
from .. import factories as f

pytestmark = pytest.mark.django_db


def setup_story():
    story = f.create_user_story()
    f.MembershipFactory(project=story.project, user=story.owner, is_admin=True)
    task = f.create_task(project=story.project, user_story=story)
    other = f.create_task(project=story.project)
    direct = f.UserStoryAttachmentFactory(project=story.project, content_object=story, owner=story.owner,
        attached_file=SimpleUploadedFile('story.gif', b'GIF89a'))
    inherited = f.TaskAttachmentFactory(project=story.project, content_object=task, owner=story.owner,
        attached_file=SimpleUploadedFile('task.gif', b'GIF89a'))
    unrelated = f.TaskAttachmentFactory(project=story.project, content_object=other, owner=story.owner,
        attached_file=SimpleUploadedFile('other.gif', b'GIF89a'))
    return story, task, direct, inherited, unrelated


def test_story_inherits_task_files_without_copying_or_changing_ownership(client):
    story, task, direct, inherited, unrelated = setup_story()
    client.login(story.owner)
    before = Attachment.objects.count()
    response = client.get(reverse('userstory-attachments-list'),
        {'project': story.project_id, 'object_id': story.id, 'include_task_attachments': '1'},
        HTTP_X_DISABLE_PAGINATION='1')
    assert response.status_code == 200
    assert {item['id'] for item in response.data} == {direct.id, inherited.id}
    assert next(item for item in response.data if item['id'] == inherited.id)['source_task_id'] == task.id
    assert Attachment.objects.count() == before
    inherited.refresh_from_db()
    assert inherited.content_object == task
    # Typed mutation/retrieve routes cannot treat the task file as a story file.
    assert client.get(reverse('userstory-attachments-detail', args=[inherited.id])).status_code == 404
    task.user_story = None
    task.save()
    response = client.get(reverse('userstory-attachments-list'),
        {'project': story.project_id, 'object_id': story.id, 'include_task_attachments': '1'},
        HTTP_X_DISABLE_PAGINATION='1')
    assert {item['id'] for item in response.data} == {direct.id}


def test_card_summaries_include_child_files_and_follow_deprecation(client):
    story, task, direct, inherited, unrelated = setup_story()
    client.login(story.owner)
    def load():
        response = client.get(reverse('userstories-list'),
            {'project': story.project_id, 'include_attachments': '1', 'order_by': '-kanban_order'},
            HTTP_X_DISABLE_PAGINATION='1')
        assert response.status_code == 200
        return next(item for item in response.data if item['id'] == story.id)
    data = load()
    assert {item['id'] for item in data['attachments']} == {direct.id, inherited.id}
    assert data['total_attachments'] == 2
    inherited.is_deprecated = True
    inherited.save()
    assert {item['id'] for item in load()['attachments']} == {direct.id}


def test_child_files_require_task_view_permission(client):
    story, task, direct, inherited, unrelated = setup_story()
    project = story.project
    project.is_private = True
    project.public_permissions = []
    project.anon_permissions = []
    project.save()
    observer = f.UserFactory()
    role = f.RoleFactory(project=project, permissions=['view_project', 'view_us'])
    f.MembershipFactory(project=project, user=observer, role=role, is_admin=False)
    client.login(observer)
    response = client.get(reverse('userstory-attachments-list'),
        {'project': project.id, 'object_id': story.id, 'include_task_attachments': '1'},
        HTTP_X_DISABLE_PAGINATION='1')
    assert {item['id'] for item in response.data} == {direct.id}
    response = client.get(reverse('userstories-list'),
        {'project': project.id, 'include_attachments': '1'}, HTTP_X_DISABLE_PAGINATION='1')
    data = next(item for item in response.data if item['id'] == story.id)
    assert {item['id'] for item in data['attachments']} == {direct.id}
    assert data['total_attachments'] == 1
