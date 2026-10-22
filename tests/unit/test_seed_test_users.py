from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from taiga.users.management.commands.seed_test_users import TEST_USERS

pytestmark = pytest.mark.django_db
PASSWORD = 'Test-only-password-123!'


@override_settings(HAKOON_ENVIRONMENT='homolog', SEED_TEST_USERS_ENABLED=True, TEST_USERS_PASSWORD=PASSWORD)
def test_seed_creates_three_regular_users_and_preserves_existing_passwords():
    output = StringIO()
    call_command('seed_test_users', stdout=output)
    User = get_user_model()
    assert User.objects.count() == 3
    for username, full_name, email in TEST_USERS:
        user = User.objects.get(username=username)
        assert user.full_name == full_name and user.email == email
        assert user.check_password(PASSWORD)
        assert user.is_active and not user.is_staff and not user.is_superuser
    user = User.objects.get(username=TEST_USERS[0][0])
    user.set_password('Changed by user later!')
    user.full_name = 'Edited display name'
    user.save()
    before = list(User.objects.order_by('pk').values())
    with override_settings(TEST_USERS_PASSWORD=''):
        call_command('seed_test_users', stdout=output)
    assert list(User.objects.order_by('pk').values()) == before
    assert User.objects.get(pk=user.pk).check_password('Changed by user later!')
    assert PASSWORD not in output.getvalue()


@pytest.mark.parametrize('environment', ['', 'production', 'dev'])
@override_settings(SEED_TEST_USERS_ENABLED=True, TEST_USERS_PASSWORD=PASSWORD)
def test_seed_refuses_other_environments(environment):
    with override_settings(HAKOON_ENVIRONMENT=environment), pytest.raises(CommandError):
        call_command('seed_test_users')
    assert get_user_model().objects.count() == 0


@override_settings(HAKOON_ENVIRONMENT='homolog', SEED_TEST_USERS_ENABLED=False)
def test_seed_can_be_disabled():
    call_command('seed_test_users', stdout=StringIO())
    assert get_user_model().objects.count() == 0


@override_settings(HAKOON_ENVIRONMENT='homolog', SEED_TEST_USERS_ENABLED=True, TEST_USERS_PASSWORD='')
def test_seed_requires_an_initial_password_without_partial_creation():
    with pytest.raises(CommandError, match='TEST_USERS_PASSWORD'):
        call_command('seed_test_users')
    assert get_user_model().objects.count() == 0


@override_settings(HAKOON_ENVIRONMENT='homolog', SEED_TEST_USERS_ENABLED=True, TEST_USERS_PASSWORD=PASSWORD)
@pytest.mark.parametrize('conflict', ['username', 'email'])
def test_seed_conflicts_do_not_change_or_create_accounts(conflict):
    User = get_user_model()
    username, _, email = TEST_USERS[-1]
    user = User.objects.create_user(username=username if conflict == 'username' else 'someone.else',
                                    email='different@homolog.invalid' if conflict == 'username' else email,
                                    password='Existing password!')
    before = list(User.objects.values())
    with pytest.raises(CommandError, match='conflict'):
        call_command('seed_test_users')
    assert list(User.objects.values()) == before
    assert User.objects.get(pk=user.pk).check_password('Existing password!')
