"""Idempotent test accounts, explicitly enabled for homolog deployments only."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


TEST_USERS = (
    ('test.alex', 'Alex Morgan', 'alex.morgan@homolog.invalid'),
    ('test.jamie', 'Jamie Chen', 'jamie.chen@homolog.invalid'),
    ('test.sam', 'Sam Taylor', 'sam.taylor@homolog.invalid'),
)


class Command(BaseCommand):
    help = 'Create missing homolog test users; preserve existing accounts and passwords.'

    def handle(self, *args, **options):
        if getattr(settings, 'HAKOON_ENVIRONMENT', '') != 'homolog':
            raise CommandError('seed_test_users is only allowed in the homolog environment.')
        if not getattr(settings, 'SEED_TEST_USERS_ENABLED', False):
            self.stdout.write('Test-user seeding is disabled.')
            return
        User = get_user_model()
        created = []
        with transaction.atomic():
            missing = []
            for username, full_name, email in TEST_USERS:
                existing = User.objects.filter(username=username).first()
                if existing:
                    if existing.email.casefold() != email.casefold():
                        raise CommandError('Test username conflict: {}. No accounts changed.'.format(username))
                    continue
                if User.objects.filter(email__iexact=email).exists():
                    raise CommandError('Test email conflict for {}. No accounts changed.'.format(username))
                missing.append((username, full_name, email))
            password = getattr(settings, 'TEST_USERS_PASSWORD', '')
            if missing and (not password or len(password) < 12):
                raise CommandError('Set TEST_USERS_PASSWORD to at least 12 characters before creating test users.')
            for username, full_name, email in missing:
                User.objects.create_user(username=username, email=email, password=password,
                                         full_name=full_name, is_active=True, is_staff=False,
                                         is_superuser=False, verified_email=True, read_new_terms=True)
                created.append(username)
        for username in created:
            self.stdout.write('Created test user: {}'.format(username))
        self.stdout.write('Test users ready: {} created, {} preserved.'.format(len(created), len(TEST_USERS) - len(created)))
