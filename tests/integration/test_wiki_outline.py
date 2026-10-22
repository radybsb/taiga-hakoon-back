from types import SimpleNamespace

import pytest
from django.contrib.auth.models import AnonymousUser

from taiga.base.exceptions import PermissionDenied
from taiga.projects.wiki.api import WikiViewSet
from .. import factories as f


@pytest.mark.django_db
def test_outline_requires_project_permission_and_returns_only_metadata():
    page = f.WikiPageFactory(project=f.ProjectFactory(is_private=True), content='## Chapter\n\n### Child')
    f.WikiPageFactory(project=f.ProjectFactory(is_private=True), content='## Private elsewhere')
    member = f.UserFactory()
    role = f.RoleFactory(project=page.project, permissions=['view_wiki_pages'])
    f.MembershipFactory(project=page.project, user=member, role=role)
    view = WikiViewSet()
    view.kwargs = {}
    request = SimpleNamespace(user=AnonymousUser(), successful_authenticator=True,
                              method='GET', QUERY_PARAMS={'project': str(page.project_id)})
    view.request = request
    with pytest.raises(PermissionDenied):
        view.outline(request)
    request.user = f.UserFactory()
    with pytest.raises(PermissionDenied):
        view.outline(request)
    request.user = member
    result = view.outline(request).data
    assert len(result) == 1
    assert set(result[0]) == {'id', 'slug', 'outline'}
    assert [h['level'] for h in result[0]['outline']] == [1, 2]


@pytest.mark.django_db
def test_model_preserves_heading_ids_after_save_and_rename():
    page = f.WikiPageFactory(content='## Chapter\n\n### Child')
    previous = [h['id'] for h in page.outline]
    page.content = '## Renamed chapter\n\n### Child'
    page.save()
    page.refresh_from_db()
    assert [h['id'] for h in page.outline] == previous
