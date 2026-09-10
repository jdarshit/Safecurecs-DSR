import getpass

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

User = get_user_model()


class Command(BaseCommand):
    help = (
        'Create a new employee user account from the CLI - a thin wrapper '
        'over UserManager.create_user for operational convenience. Django '
        'admin remains the primary way to onboard employees.'
    )

    def add_arguments(self, parser):
        parser.add_argument('employee_id')
        parser.add_argument('email')
        parser.add_argument('first_name')
        parser.add_argument('last_name')
        parser.add_argument('--department', default='')
        parser.add_argument('--designation', default='')
        parser.add_argument('--password', default=None, help='If omitted, you will be prompted securely.')

    def handle(self, *args, **options):
        employee_id = options['employee_id']
        email = options['email']

        if User.objects.filter(employee_id=employee_id).exists():
            raise CommandError(f"Employee ID '{employee_id}' already exists.")
        if User.objects.filter(email__iexact=email).exists():
            raise CommandError(f"Email '{email}' already exists.")

        password = options['password']
        if not password:
            password = getpass.getpass('Password: ')
            confirm = getpass.getpass('Confirm password: ')
            if password != confirm:
                raise CommandError('Passwords do not match.')

        user = User.objects.create_user(
            employee_id=employee_id,
            email=email,
            password=password,
            first_name=options['first_name'],
            last_name=options['last_name'],
            department=options['department'],
            designation=options['designation'],
        )
        self.stdout.write(self.style.SUCCESS(
            f'Created employee {user.employee_id} ({user.get_full_name()}).'
        ))
