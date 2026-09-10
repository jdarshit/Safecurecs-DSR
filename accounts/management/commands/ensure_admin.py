import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Create the configured deployment admin account if it does not exist.'

    def handle(self, *args, **options):
        values = {
            key: os.environ.get(key, '').strip()
            for key in (
                'BOOTSTRAP_ADMIN_ID', 'BOOTSTRAP_ADMIN_EMAIL',
                'BOOTSTRAP_ADMIN_FIRST_NAME', 'BOOTSTRAP_ADMIN_LAST_NAME',
                'BOOTSTRAP_ADMIN_PASSWORD',
            )
        }
        if not all(values.values()):
            self.stdout.write('Bootstrap admin variables are incomplete; skipping.')
            return

        User = get_user_model()
        user, created = User.objects.get_or_create(
            employee_id=values['BOOTSTRAP_ADMIN_ID'],
            defaults={
                'email': values['BOOTSTRAP_ADMIN_EMAIL'],
                'first_name': values['BOOTSTRAP_ADMIN_FIRST_NAME'],
                'last_name': values['BOOTSTRAP_ADMIN_LAST_NAME'],
                'role': User.Role.ADMIN,
                'is_staff': True,
                'is_superuser': True,
            },
        )
        if created:
            user.set_password(values['BOOTSTRAP_ADMIN_PASSWORD'])
            user.save(update_fields=['password'])
            self.stdout.write(self.style.SUCCESS(f'Created bootstrap admin {user.employee_id}.'))
            return

        if user.role != User.Role.ADMIN or not user.is_staff or not user.is_superuser:
            raise CommandError(f'Bootstrap ID {user.employee_id} exists but is not an admin.')
        self.stdout.write(f'Bootstrap admin {user.employee_id} already exists; skipped.')
