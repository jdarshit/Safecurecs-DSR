from datetime import date, timedelta

from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.http import Http404
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone
from django.views.defaults import page_not_found, permission_denied, server_error

from dsr.models import DSR

from .forms import EmployeeAuthenticationForm

User = get_user_model()


def make_dsr(employee, **kwargs):
    defaults = dict(
        visit_date=date.today(),
        purpose_of_visit=DSR.PurposeOfVisit.SERVICE,
        client_name='Acme Corp', company_name='Acme Corp Pvt Ltd',
        contact_person='John Client', contact_number='9999999999',
        project_name='Acme HQ Fire System', project_address='123 Acme Street',
        project_type=DSR.ProjectType.COMMERCIAL, building_size=DSR.BuildingSize.MEDIUM,
        project_stage=DSR.ProjectStage.EXISTING_BUILDING,
        work_done='Inspected fire panel and sensors.',
    )
    defaults.update(kwargs)
    return DSR.objects.create(employee=employee, **defaults)


class UserManagerTests(TestCase):
    def test_create_user(self):
        user = User.objects.create_user(
            employee_id='EMP001', email='emp001@example.com', password='TestPass123',
            first_name='Jane', last_name='Doe',
        )
        self.assertEqual(user.employee_id, 'EMP001')
        self.assertEqual(user.email, 'emp001@example.com')
        self.assertTrue(user.check_password('TestPass123'))
        self.assertEqual(user.role, User.Role.EMPLOYEE)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_superuser(self):
        admin = User.objects.create_superuser(
            employee_id='ADM001', email='adm001@example.com', password='AdminPass123',
            first_name='Ada', last_name='Min',
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertEqual(admin.role, User.Role.ADMIN)

    def test_create_superuser_requires_is_staff_true(self):
        with self.assertRaises(ValueError):
            User.objects.create_superuser(
                employee_id='ADM002', email='adm002@example.com', password='AdminPass123',
                first_name='Ada', last_name='Min', is_staff=False,
            )


class AuthenticationBackendTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            employee_id='EMP002', email='emp002@example.com', password='TestPass123',
            first_name='John', last_name='Smith',
        )

    def test_login_via_employee_id(self):
        user = authenticate(username='EMP002', password='TestPass123')
        self.assertIsNotNone(user)
        self.assertEqual(user.pk, self.user.pk)

    def test_login_via_email(self):
        user = authenticate(username='emp002@example.com', password='TestPass123')
        self.assertIsNotNone(user)
        self.assertEqual(user.pk, self.user.pk)

    def test_login_via_email_case_insensitive(self):
        user = authenticate(username='EMP002@EXAMPLE.COM', password='TestPass123')
        self.assertIsNotNone(user)
        self.assertEqual(user.pk, self.user.pk)

    def test_login_wrong_password_fails(self):
        user = authenticate(username='EMP002', password='WrongPass')
        self.assertIsNone(user)

    def test_login_unknown_identifier_fails(self):
        user = authenticate(username='NOBODY', password='TestPass123')
        self.assertIsNone(user)


class EmployeeAuthenticationFormTests(TestCase):
    def test_username_field_accepts_identifier_longer_than_employee_id_max_length(self):
        # AuthenticationForm.__init__ forces the username field's max_length
        # from USERNAME_FIELD's model field (employee_id, max_length=20)
        # after Form construction - this asserts our override wins and a
        # long email isn't truncated or rejected purely for its length.
        long_identifier = 'safecure.cs@gmail.com'
        self.assertGreater(len(long_identifier), 20)

        form = EmployeeAuthenticationForm(data={'username': long_identifier, 'password': 'irrelevant'})
        form.is_valid()

        self.assertEqual(form.fields['username'].max_length, 254)
        self.assertNotIn('username', form.errors)
        self.assertEqual(form.cleaned_data.get('username'), long_identifier)


class LoginViewTests(TestCase):
    def setUp(self):
        self.employee = User.objects.create_user(
            employee_id='EMP010', email='emp010@example.com', password='TestPass123',
            first_name='Alice', last_name='Employee',
        )
        self.admin = User.objects.create_user(
            employee_id='ADM010', email='adm010@example.com', password='AdminPass123',
            first_name='Bob', last_name='Admin', role=User.Role.ADMIN,
        )

    def test_login_via_employee_id_redirects_to_employee_dashboard(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'EMP010', 'password': 'TestPass123',
        })
        self.assertRedirects(response, reverse('accounts:employee_dashboard'))

    def test_login_via_email_redirects_to_admin_dashboard(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'adm010@example.com', 'password': 'AdminPass123',
        })
        self.assertRedirects(response, reverse('accounts:admin_dashboard'))

    def test_login_with_email_longer_than_employee_id_max_length(self):
        # employee_id (USERNAME_FIELD) caps at 20 chars; this email is longer,
        # regression-testing the fix for the username field's max_length
        # being wrongly inherited from employee_id's model field.
        long_email = 'verylongname.employee@safecurecs.com'
        self.assertGreater(len(long_email), 20)
        User.objects.create_user(
            employee_id='EMP020', email=long_email, password='TestPass123',
            first_name='Very', last_name='Long',
        )
        response = self.client.post(reverse('accounts:login'), {
            'username': long_email, 'password': 'TestPass123',
        })
        self.assertRedirects(response, reverse('accounts:employee_dashboard'))

    def test_wrong_password_shows_error_and_stays_on_login_page(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'EMP010', 'password': 'WrongPass',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please enter a correct Employee ID/Email and password.')

    def test_inactive_account_shows_inactive_message(self):
        self.employee.is_active = False
        self.employee.save(update_fields=['is_active'])
        response = self.client.post(reverse('accounts:login'), {
            'username': 'EMP010', 'password': 'TestPass123',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This account is inactive.')

    def test_already_logged_in_user_redirected_from_login(self):
        self.client.login(username='EMP010', password='TestPass123')
        response = self.client.get(reverse('accounts:login'))
        self.assertRedirects(response, reverse('accounts:employee_dashboard'))

    def test_safe_next_is_honored(self):
        response = self.client.post(
            f"{reverse('accounts:login')}?next={reverse('accounts:profile')}",
            {'username': 'EMP010', 'password': 'TestPass123'},
        )
        self.assertRedirects(response, reverse('accounts:profile'))

    def test_unsafe_next_falls_back_to_role_dashboard(self):
        response = self.client.post(
            f"{reverse('accounts:login')}?next=https://evil.example.com/steal",
            {'username': 'EMP010', 'password': 'TestPass123'},
        )
        self.assertRedirects(response, reverse('accounts:employee_dashboard'))


class LogoutViewTests(TestCase):
    def setUp(self):
        self.employee = User.objects.create_user(
            employee_id='EMP011', email='emp011@example.com', password='TestPass123',
            first_name='Carl', last_name='Employee',
        )

    def test_logout_requires_post(self):
        self.client.login(username='EMP011', password='TestPass123')
        response = self.client.get(reverse('accounts:logout'))
        self.assertEqual(response.status_code, 405)

    def test_logout_via_post_redirects_to_login(self):
        self.client.login(username='EMP011', password='TestPass123')
        response = self.client.post(reverse('accounts:logout'))
        self.assertRedirects(response, reverse('accounts:login'))


class RoleAccessTests(TestCase):
    def setUp(self):
        self.employee = User.objects.create_user(
            employee_id='EMP012', email='emp012@example.com', password='TestPass123',
            first_name='Dana', last_name='Employee',
        )
        self.admin = User.objects.create_user(
            employee_id='ADM012', email='adm012@example.com', password='AdminPass123',
            first_name='Erin', last_name='Admin', role=User.Role.ADMIN,
        )

    def test_admin_can_access_admin_dashboard(self):
        self.client.login(username='ADM012', password='AdminPass123')
        response = self.client.get(reverse('accounts:admin_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Admin Dashboard')

    def test_employee_can_access_employee_dashboard(self):
        self.client.login(username='EMP012', password='TestPass123')
        response = self.client.get(reverse('accounts:employee_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Employee Dashboard')

    def test_employee_blocked_from_admin_dashboard(self):
        self.client.login(username='EMP012', password='TestPass123')
        response = self.client.get(reverse('accounts:admin_dashboard'))
        self.assertRedirects(response, reverse('accounts:employee_dashboard'))

    def test_admin_blocked_from_employee_dashboard(self):
        self.client.login(username='ADM012', password='AdminPass123')
        response = self.client.get(reverse('accounts:employee_dashboard'))
        self.assertRedirects(response, reverse('accounts:admin_dashboard'))

    def test_anonymous_user_redirected_from_protected_view(self):
        response = self.client.get(reverse('accounts:profile'))
        self.assertRedirects(
            response, f"{reverse('accounts:login')}?next={reverse('accounts:profile')}"
        )


class ProfileViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            employee_id='EMP013', email='emp013@example.com', password='TestPass123',
            first_name='Fay', last_name='Employee', department='Field Ops',
            designation='Engineer',
        )
        self.other = User.objects.create_user(
            employee_id='EMP014', email='emp014@example.com', password='TestPass123',
            first_name='Gus', last_name='Employee',
        )
        self.client.login(username='EMP013', password='TestPass123')

    def test_profile_edit_updates_email_and_mobile(self):
        response = self.client.post(reverse('accounts:profile'), {
            'email': 'new013@example.com', 'mobile_number': '9998887777',
        })
        self.assertRedirects(response, reverse('accounts:profile'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'new013@example.com')
        self.assertEqual(self.user.mobile_number, '9998887777')

    def test_profile_edit_cannot_change_employee_id_or_role(self):
        response = self.client.post(reverse('accounts:profile'), {
            'email': 'emp013@example.com', 'mobile_number': '9998887777',
            'employee_id': 'HACKED', 'role': User.Role.ADMIN,
        })
        self.assertRedirects(response, reverse('accounts:profile'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.employee_id, 'EMP013')
        self.assertEqual(self.user.role, User.Role.EMPLOYEE)

    def test_profile_edit_rejects_duplicate_email(self):
        response = self.client.post(reverse('accounts:profile'), {
            'email': 'emp014@example.com', 'mobile_number': '9998887777',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This email is already in use.')

    def test_profile_photo_rejects_invalid_extension(self):
        # A real (but tiny) GIF — valid image content so Django's ImageField
        # validation passes, letting our own extension whitelist be exercised.
        gif_bytes = (
            b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\x00\x00\x00\x00'
            b'\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00'
            b'\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
        )
        bad_file = SimpleUploadedFile('photo.gif', gif_bytes, content_type='image/gif')
        response = self.client.post(reverse('accounts:profile'), {
            'email': 'emp013@example.com', 'mobile_number': '9998887777',
            'profile_photo': bad_file,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Only JPG, JPEG, and PNG files are allowed.')


class ChangePasswordViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            employee_id='EMP015', email='emp015@example.com', password='OldPass123',
            first_name='Hank', last_name='Employee',
        )
        self.client.login(username='EMP015', password='OldPass123')

    def test_change_password_flow(self):
        response = self.client.post(reverse('accounts:change_password'), {
            'old_password': 'OldPass123',
            'new_password1': 'NewPass456',
            'new_password2': 'NewPass456',
        })
        self.assertRedirects(response, reverse('accounts:profile'))

        self.client.logout()
        login_response = self.client.post(reverse('accounts:login'), {
            'username': 'EMP015', 'password': 'NewPass456',
        })
        self.assertRedirects(login_response, reverse('accounts:employee_dashboard'))


class EmployeeDashboardContentTests(TestCase):
    def setUp(self):
        self.employee = User.objects.create_user(
            employee_id='EMP020', email='emp020@example.com', password='TestPass123',
            first_name='Nina', last_name='Employee',
        )
        self.other = User.objects.create_user(
            employee_id='EMP021', email='emp021@example.com', password='TestPass123',
            first_name='Oscar', last_name='Employee',
        )
        self.admin = User.objects.create_user(
            employee_id='ADM020', email='adm020@example.com', password='AdminPass123',
            first_name='Pia', last_name='Admin', role=User.Role.ADMIN,
        )
        self.client.login(username='EMP020', password='TestPass123')

    def test_stat_counts_correct_for_mixed_statuses(self):
        make_dsr(self.employee)
        submitted = make_dsr(self.employee)
        submitted.submit()
        approved = make_dsr(self.employee)
        approved.submit()
        approved.approve(self.admin)
        rejected = make_dsr(self.employee)
        rejected.submit()
        rejected.reject(self.admin, 'fix it')

        response = self.client.get(reverse('accounts:employee_dashboard'))
        stats = response.context['stats']
        self.assertEqual(stats['total'], 4)
        self.assertEqual(stats['draft'], 1)
        self.assertEqual(stats['submitted'], 1)
        self.assertEqual(stats['approved'], 1)
        self.assertEqual(stats['rejected'], 1)

    def test_stats_exclude_other_employees_reports(self):
        make_dsr(self.employee)
        make_dsr(self.other)
        make_dsr(self.other)
        response = self.client.get(reverse('accounts:employee_dashboard'))
        self.assertEqual(response.context['stats']['total'], 1)

    def test_needs_attention_shows_only_rejected_and_sent_back(self):
        make_dsr(self.employee)  # plain draft, no remarks - must not appear
        submitted = make_dsr(self.employee)
        submitted.submit()  # must not appear
        approved = make_dsr(self.employee)
        approved.submit()
        approved.approve(self.admin)  # must not appear
        rejected = make_dsr(self.employee)
        rejected.submit()
        rejected.reject(self.admin, 'fix contact number')
        sent_back = make_dsr(self.employee)
        sent_back.submit()
        sent_back.send_back(self.admin, 'recheck address')

        response = self.client.get(reverse('accounts:employee_dashboard'))
        needs_attention_ids = {d.pk for d in response.context['needs_attention']}
        self.assertEqual(needs_attention_ids, {rejected.pk, sent_back.pk})

    def test_recent_reports_capped_at_five(self):
        for i in range(7):
            make_dsr(self.employee, visit_date=date(2026, 1, 1) + timedelta(days=i))
        response = self.client.get(reverse('accounts:employee_dashboard'))
        self.assertEqual(len(response.context['recent_reports']), 5)

    def test_stat_card_links_carry_status_param(self):
        response = self.client.get(reverse('accounts:employee_dashboard'))
        my_reports_url = reverse('dsr:my_reports')
        self.assertContains(response, f'{my_reports_url}?status=DRAFT')
        self.assertContains(response, f'{my_reports_url}?status=SUBMITTED')
        self.assertContains(response, f'{my_reports_url}?status=APPROVED')
        self.assertContains(response, f'{my_reports_url}?status=REJECTED')

    def test_employee_dashboard_query_count(self):
        make_dsr(self.employee)
        submitted = make_dsr(self.employee)
        submitted.submit()
        # Breakdown: 1 session load + 1 auth user load + 3 view queries
        # (stats aggregate, needs-attention, recent reports) + 3 session-save
        # queries (SAVEPOINT/UPDATE django_session/RELEASE SAVEPOINT, from
        # Phase 8's SESSION_SAVE_EVERY_REQUEST=True rolling session window)
        # = 8. Employee sidebar branch does not call pending_dsr_count,
        # unlike admin's.
        with self.assertNumQueries(8):
            self.client.get(reverse('accounts:employee_dashboard'))


class AdminDashboardContentTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            employee_id='ADM030', email='adm030@example.com', password='AdminPass123',
            first_name='Quinn', last_name='Admin', role=User.Role.ADMIN,
        )
        self.emp1 = User.objects.create_user(
            employee_id='EMP030', email='emp030@example.com', password='TestPass123',
            first_name='Rita', last_name='Employee',
        )
        self.emp2 = User.objects.create_user(
            employee_id='EMP031', email='emp031@example.com', password='TestPass123',
            first_name='Sam', last_name='Employee',
        )
        self.inactive_employee = User.objects.create_user(
            employee_id='EMP032', email='emp032@example.com', password='TestPass123',
            first_name='Tina', last_name='Employee', is_active=False,
        )
        self.client.login(username='ADM030', password='AdminPass123')

    def test_counts_span_all_employees(self):
        make_dsr(self.emp1)
        make_dsr(self.emp2)
        response = self.client.get(reverse('accounts:admin_dashboard'))
        self.assertEqual(response.context['stats']['total'], 2)

    def test_pending_queue_oldest_first_capped_and_submitted_only(self):
        for i in range(12):
            d = make_dsr(self.emp1)
            d.submit()
            DSR.objects.filter(pk=d.pk).update(submitted_at=timezone.now() - timedelta(hours=(20 - i)))
        make_dsr(self.emp1)  # DRAFT - must be excluded
        approved = make_dsr(self.emp1)
        approved.submit()
        approved.approve(self.admin)  # APPROVED - must be excluded

        response = self.client.get(reverse('accounts:admin_dashboard'))
        queue = list(response.context['pending_queue'])
        self.assertEqual(len(queue), 10)
        self.assertTrue(all(d.status == DSR.Status.SUBMITTED for d in queue))
        submitted_ats = [d.submitted_at for d in queue]
        self.assertEqual(submitted_ats, sorted(submitted_ats))

    def test_recent_activity_capped_at_eight(self):
        for i in range(10):
            make_dsr(self.emp1)
        response = self.client.get(reverse('accounts:admin_dashboard'))
        self.assertEqual(len(response.context['recent_activity']), 8)

    def test_today_counts(self):
        today_submitted = make_dsr(self.emp1)
        today_submitted.submit()

        yesterday_submitted = make_dsr(self.emp1)
        yesterday_submitted.submit()
        DSR.objects.filter(pk=yesterday_submitted.pk).update(
            submitted_at=timezone.now() - timedelta(days=1),
        )

        approved_today = make_dsr(self.emp1)
        approved_today.submit()
        approved_today.approve(self.admin)

        approved_yesterday_review = make_dsr(self.emp1)
        approved_yesterday_review.submit()
        approved_yesterday_review.approve(self.admin)
        DSR.objects.filter(pk=approved_yesterday_review.pk).update(
            reviewed_at=timezone.now() - timedelta(days=1),
        )

        rejected_today = make_dsr(self.emp1)
        rejected_today.submit()
        rejected_today.reject(self.admin, 'fix it')

        response = self.client.get(reverse('accounts:admin_dashboard'))
        stats = response.context['stats']
        # submitted_today counts every DSR submitted today regardless of later
        # status: today_submitted, approved_today, approved_yesterday_review
        # (its submitted_at is untouched, only reviewed_at was backdated), and
        # rejected_today - 4 total. yesterday_submitted is excluded.
        self.assertEqual(stats['submitted_today'], 4)
        self.assertEqual(stats['approved_today'], 1)
        self.assertEqual(stats['rejected_today'], 1)

    def test_active_employee_count(self):
        response = self.client.get(reverse('accounts:admin_dashboard'))
        self.assertEqual(response.context['active_employee_count'], 2)

    def test_admin_dashboard_query_count(self):
        d = make_dsr(self.emp1)
        d.submit()
        # Breakdown: 1 session load + 1 auth user load + 4 view queries
        # (combined stats/today aggregate, active employee count, pending
        # queue, recent activity) + 1 sidebar pending_dsr_count badge + 3
        # session-save queries (SAVEPOINT/UPDATE django_session/RELEASE
        # SAVEPOINT, from Phase 8's SESSION_SAVE_EVERY_REQUEST=True rolling
        # session window) = 10.
        with self.assertNumQueries(10):
            self.client.get(reverse('accounts:admin_dashboard'))


class CreateEmployeeCommandTests(TestCase):
    def test_creates_employee_with_given_fields(self):
        call_command(
            'create_employee', 'EMP500', 'emp500@example.com', 'New', 'Hire',
            '--department', 'Field Ops', '--designation', 'Engineer', '--password', 'TestPass123',
        )
        user = User.objects.get(employee_id='EMP500')
        self.assertEqual(user.email, 'emp500@example.com')
        self.assertEqual(user.first_name, 'New')
        self.assertEqual(user.last_name, 'Hire')
        self.assertEqual(user.department, 'Field Ops')
        self.assertEqual(user.designation, 'Engineer')
        self.assertEqual(user.role, User.Role.EMPLOYEE)
        self.assertTrue(user.check_password('TestPass123'))

    def test_duplicate_employee_id_raises(self):
        call_command('create_employee', 'EMP501', 'a@example.com', 'A', 'One', '--password', 'TestPass123')
        with self.assertRaises(CommandError):
            call_command('create_employee', 'EMP501', 'b@example.com', 'B', 'Two', '--password', 'TestPass123')

    def test_duplicate_email_raises(self):
        call_command('create_employee', 'EMP502', 'dup@example.com', 'A', 'One', '--password', 'TestPass123')
        with self.assertRaises(CommandError):
            call_command('create_employee', 'EMP503', 'dup@example.com', 'B', 'Two', '--password', 'TestPass123')


class ErrorPageTests(TestCase):
    """Exercises Django's actual default error-handling view functions
    directly via RequestFactory - the same code path used in production when
    DEBUG=False - so these templates are verified without needing a real
    broken URL or a DEBUG=False override. (One manual end-to-end check with
    DEBUG=False against a real dev server was also performed - see CLAUDE.md.)
    """

    def setUp(self):
        self.factory = RequestFactory()

    def test_404_page_renders(self):
        request = self.factory.get('/nonexistent/')
        response = page_not_found(request, Http404('not found'))
        self.assertEqual(response.status_code, 404)
        self.assertIn(b'Page Not Found', response.content)

    def test_403_page_renders(self):
        request = self.factory.get('/forbidden/')
        response = permission_denied(request, PermissionDenied('denied'))
        self.assertEqual(response.status_code, 403)
        self.assertIn(b'Access Denied', response.content)

    def test_500_page_renders(self):
        request = self.factory.get('/error/')
        response = server_error(request)
        self.assertEqual(response.status_code, 500)
        self.assertIn(b'Something Went Wrong', response.content)


def valid_employee_post_data(**overrides):
    data = {
        'employee_id': 'EMP900',
        'email': 'emp900@example.com',
        'first_name': 'New',
        'last_name': 'Hire',
        'mobile_number': '9998887777',
        'department': 'Field Ops',
        'designation': 'Engineer',
        'password1': 'StrongPass987!',
        'password2': 'StrongPass987!',
    }
    data.update(overrides)
    return data


class EmployeeManagementAccessTests(TestCase):
    def setUp(self):
        self.employee = User.objects.create_user(
            employee_id='EMP600', email='emp600@example.com', password='TestPass123',
            first_name='Ann', last_name='Employee',
        )
        self.admin = User.objects.create_user(
            employee_id='ADM600', email='adm600@example.com', password='AdminPass123',
            first_name='Bea', last_name='Admin', role=User.Role.ADMIN,
        )
        self.other_employee = User.objects.create_user(
            employee_id='EMP601', email='emp601@example.com', password='TestPass123',
            first_name='Cid', last_name='Employee',
        )

    def test_employee_blocked_from_list(self):
        self.client.login(username='EMP600', password='TestPass123')
        response = self.client.get(reverse('accounts:employee_list'))
        self.assertRedirects(response, reverse('accounts:employee_dashboard'))

    def test_employee_blocked_from_add(self):
        self.client.login(username='EMP600', password='TestPass123')
        response = self.client.get(reverse('accounts:employee_add'))
        self.assertRedirects(response, reverse('accounts:employee_dashboard'))

    def test_employee_blocked_from_edit(self):
        self.client.login(username='EMP600', password='TestPass123')
        response = self.client.get(reverse('accounts:employee_edit', args=[self.other_employee.pk]))
        self.assertRedirects(response, reverse('accounts:employee_dashboard'))

    def test_employee_blocked_from_reset_password(self):
        self.client.login(username='EMP600', password='TestPass123')
        response = self.client.post(reverse('accounts:employee_reset_password', args=[self.other_employee.pk]))
        self.assertRedirects(response, reverse('accounts:employee_dashboard'))

    def test_admin_allowed_list(self):
        self.client.login(username='ADM600', password='AdminPass123')
        response = self.client.get(reverse('accounts:employee_list'))
        self.assertEqual(response.status_code, 200)

    def test_admin_allowed_add(self):
        self.client.login(username='ADM600', password='AdminPass123')
        response = self.client.get(reverse('accounts:employee_add'))
        self.assertEqual(response.status_code, 200)

    def test_admin_allowed_edit(self):
        self.client.login(username='ADM600', password='AdminPass123')
        response = self.client.get(reverse('accounts:employee_edit', args=[self.other_employee.pk]))
        self.assertEqual(response.status_code, 200)


class EmployeeListViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            employee_id='ADM610', email='adm610@example.com', password='AdminPass123',
            first_name='Dee', last_name='Admin', role=User.Role.ADMIN,
        )
        self.client.login(username='ADM610', password='AdminPass123')

    def test_only_employees_shown_admins_excluded(self):
        emp = User.objects.create_user(
            employee_id='EMP610', email='emp610@example.com', password='TestPass123',
            first_name='Eve', last_name='Employee',
        )
        response = self.client.get(reverse('accounts:employee_list'))
        employee_ids = {u.employee_id for u in response.context['employees']}
        self.assertEqual(employee_ids, {emp.employee_id})
        self.assertNotIn(self.admin.employee_id, employee_ids)

    def test_search_by_employee_id_name_email(self):
        match = User.objects.create_user(
            employee_id='EMP611', email='zephyr.match@example.com', password='TestPass123',
            first_name='Zephyr', last_name='Match',
        )
        User.objects.create_user(
            employee_id='EMP612', email='other@example.com', password='TestPass123',
            first_name='Other', last_name='Person',
        )
        response = self.client.get(reverse('accounts:employee_list'), {'q': 'zephyr'})
        ids = {u.employee_id for u in response.context['employees']}
        self.assertEqual(ids, {match.employee_id})

    def test_filter_by_active_status(self):
        active = User.objects.create_user(
            employee_id='EMP613', email='active@example.com', password='TestPass123',
            first_name='Active', last_name='One',
        )
        inactive = User.objects.create_user(
            employee_id='EMP614', email='inactive@example.com', password='TestPass123',
            first_name='Inactive', last_name='One', is_active=False,
        )
        response = self.client.get(reverse('accounts:employee_list'), {'is_active': 'false'})
        ids = {u.employee_id for u in response.context['employees']}
        self.assertEqual(ids, {inactive.employee_id})
        self.assertNotIn(active.employee_id, ids)

    def test_filter_by_department(self):
        match = User.objects.create_user(
            employee_id='EMP615', email='dept1@example.com', password='TestPass123',
            first_name='Dep', last_name='One', department='Field Ops',
        )
        User.objects.create_user(
            employee_id='EMP616', email='dept2@example.com', password='TestPass123',
            first_name='Dep', last_name='Two', department='Sales',
        )
        response = self.client.get(reverse('accounts:employee_list'), {'department': 'Field Ops'})
        ids = {u.employee_id for u in response.context['employees']}
        self.assertEqual(ids, {match.employee_id})

    def test_pagination(self):
        for i in range(22):
            User.objects.create_user(
                employee_id=f'EMP7{i:02d}', email=f'page{i}@example.com', password='TestPass123',
                first_name='Page', last_name=str(i),
            )
        response = self.client.get(reverse('accounts:employee_list'))
        self.assertEqual(len(response.context['employees']), 20)
        response_page2 = self.client.get(reverse('accounts:employee_list'), {'page': 2})
        self.assertEqual(len(response_page2.context['employees']), 2)


class EmployeeCreateViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            employee_id='ADM620', email='adm620@example.com', password='AdminPass123',
            first_name='Fay', last_name='Admin', role=User.Role.ADMIN,
        )
        self.client.login(username='ADM620', password='AdminPass123')

    def test_valid_data_creates_employee_ignoring_role_tampering(self):
        data = valid_employee_post_data()
        data['role'] = User.Role.ADMIN
        data['is_staff'] = 'on'
        data['is_superuser'] = 'on'
        response = self.client.post(reverse('accounts:employee_add'), data)
        self.assertRedirects(response, reverse('accounts:employee_list'))

        user = User.objects.get(employee_id='EMP900')
        self.assertEqual(user.role, User.Role.EMPLOYEE)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_duplicate_employee_id_shows_field_error(self):
        User.objects.create_user(
            employee_id='EMP900', email='existing@example.com', password='TestPass123',
            first_name='Existing', last_name='One',
        )
        response = self.client.post(reverse('accounts:employee_add'), valid_employee_post_data())
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'employee_id', 'User with this Employee id already exists.')

    def test_duplicate_email_shows_field_error(self):
        User.objects.create_user(
            employee_id='EMP901', email='emp900@example.com', password='TestPass123',
            first_name='Existing', last_name='One',
        )
        response = self.client.post(reverse('accounts:employee_add'), valid_employee_post_data())
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'email', 'User with this Email already exists.')

    def test_weak_password_rejected(self):
        response = self.client.post(reverse('accounts:employee_add'), valid_employee_post_data(
            password1='password', password2='password',
        ))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(employee_id='EMP900').exists())

    def test_created_employee_can_log_in(self):
        self.client.post(reverse('accounts:employee_add'), valid_employee_post_data())
        self.client.logout()
        response = self.client.post(reverse('accounts:login'), {
            'username': 'EMP900', 'password': 'StrongPass987!',
        })
        self.assertRedirects(response, reverse('accounts:employee_dashboard'))


class EmployeeUpdateViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            employee_id='ADM630', email='adm630@example.com', password='AdminPass123',
            first_name='Gia', last_name='Admin', role=User.Role.ADMIN,
        )
        self.employee = User.objects.create_user(
            employee_id='EMP630', email='emp630@example.com', password='TestPass123',
            first_name='Hank', last_name='Employee',
        )
        self.client.login(username='ADM630', password='AdminPass123')

    def _edit_data(self, **overrides):
        data = {
            'first_name': 'Updated', 'last_name': 'Name', 'email': 'updated@example.com',
            'mobile_number': '1112223333', 'department': 'New Dept', 'designation': 'New Title',
            'is_active': 'on',
        }
        data.update(overrides)
        return data

    def test_allowed_fields_update(self):
        response = self.client.post(
            reverse('accounts:employee_edit', args=[self.employee.pk]), self._edit_data(),
        )
        self.assertRedirects(response, reverse('accounts:employee_list'))
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.first_name, 'Updated')
        self.assertEqual(self.employee.email, 'updated@example.com')
        self.assertEqual(self.employee.department, 'New Dept')

    def test_employee_id_and_role_unchangeable(self):
        data = self._edit_data(employee_id='HACKED', role=User.Role.ADMIN)
        self.client.post(reverse('accounts:employee_edit', args=[self.employee.pk]), data)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.employee_id, 'EMP630')
        self.assertEqual(self.employee.role, User.Role.EMPLOYEE)

    def test_deactivate_blocks_login(self):
        data = self._edit_data()
        del data['is_active']  # unchecked checkbox
        self.client.post(reverse('accounts:employee_edit', args=[self.employee.pk]), data)
        self.employee.refresh_from_db()
        self.assertFalse(self.employee.is_active)

        self.client.logout()
        response = self.client.post(reverse('accounts:login'), {
            'username': 'EMP630', 'password': 'TestPass123',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This account is inactive.')

    def test_reactivate_restores_login(self):
        self.employee.is_active = False
        self.employee.save(update_fields=['is_active'])

        self.client.post(reverse('accounts:employee_edit', args=[self.employee.pk]), self._edit_data(is_active='on'))
        self.employee.refresh_from_db()
        self.assertTrue(self.employee.is_active)

        self.client.logout()
        response = self.client.post(reverse('accounts:login'), {
            'username': 'EMP630', 'password': 'TestPass123',
        })
        self.assertRedirects(response, reverse('accounts:employee_dashboard'))

    def test_admin_pk_returns_404(self):
        response = self.client.get(reverse('accounts:employee_edit', args=[self.admin.pk]))
        self.assertEqual(response.status_code, 404)


class EmployeeResetPasswordViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            employee_id='ADM640', email='adm640@example.com', password='AdminPass123',
            first_name='Ivy', last_name='Admin', role=User.Role.ADMIN,
        )
        self.employee = User.objects.create_user(
            employee_id='EMP640', email='emp640@example.com', password='OldPass123',
            first_name='Jon', last_name='Employee',
        )
        self.client.login(username='ADM640', password='AdminPass123')

    def test_new_password_works_old_stops_working(self):
        response = self.client.post(
            reverse('accounts:employee_reset_password', args=[self.employee.pk]),
            {'new_password1': 'BrandNewPass456!', 'new_password2': 'BrandNewPass456!'},
        )
        self.assertRedirects(response, reverse('accounts:employee_edit', args=[self.employee.pk]))

        self.client.logout()
        old_login = self.client.post(reverse('accounts:login'), {
            'username': 'EMP640', 'password': 'OldPass123',
        })
        self.assertEqual(old_login.status_code, 200)
        self.assertContains(old_login, 'Please enter a correct Employee ID/Email and password.')

        new_login = self.client.post(reverse('accounts:login'), {
            'username': 'EMP640', 'password': 'BrandNewPass456!',
        })
        self.assertRedirects(new_login, reverse('accounts:employee_dashboard'))

    def test_weak_password_rejected_old_password_still_works(self):
        response = self.client.post(
            reverse('accounts:employee_reset_password', args=[self.employee.pk]),
            {'new_password1': 'password', 'new_password2': 'password'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['reset_password_form'].errors)

        self.client.logout()
        old_login = self.client.post(reverse('accounts:login'), {
            'username': 'EMP640', 'password': 'OldPass123',
        })
        self.assertRedirects(old_login, reverse('accounts:employee_dashboard'))

    def test_admin_pk_returns_404(self):
        response = self.client.post(
            reverse('accounts:employee_reset_password', args=[self.admin.pk]),
            {'new_password1': 'Whatever123!', 'new_password2': 'Whatever123!'},
        )
        self.assertEqual(response.status_code, 404)
