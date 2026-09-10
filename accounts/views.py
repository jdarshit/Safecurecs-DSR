from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, ListView, RedirectView, TemplateView, UpdateView

from dsr.models import DSR

from .forms import (
    EmployeeAuthenticationForm, EmployeeCreateForm, EmployeeEditForm, EmployeeFilterForm,
    ProfileUpdateForm, StyledPasswordChangeForm, StyledSetPasswordForm,
)
from .mixins import AdminRequiredMixin, EmployeeRequiredMixin
from .utils import get_dashboard_url

User = get_user_model()


def health_check(request):
    return JsonResponse({'status': 'ok'})


class IndexRedirectView(RedirectView):
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        if self.request.user.is_authenticated:
            return get_dashboard_url(self.request.user)
        return reverse('accounts:login')


class SafecurecsLoginView(LoginView):
    template_name = 'accounts/login.html'
    authentication_form = EmployeeAuthenticationForm
    redirect_authenticated_user = True

    def get_default_redirect_url(self):
        return get_dashboard_url(self.request.user)


class SafecurecsLogoutView(LogoutView):
    next_page = reverse_lazy('accounts:login')

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        messages.success(request, 'You have been logged out.')
        return response


class AdminDashboardView(AdminRequiredMixin, TemplateView):
    template_name = 'accounts/dashboard_admin.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Deliberately a tz-aware gte/lt range, not a `__date` lookup: `__date`
        # on a DateTimeField asks MySQL to CONVERT_TZ from UTC storage to
        # TIME_ZONE, which silently returns NULL (matching nothing) if the
        # server's timezone tables aren't loaded (mysql_tzinfo_to_sql) - not
        # something this app can assume about every deployment. A plain range
        # comparison against tz-aware boundaries needs no server-side TZ data.
        now_local = timezone.localtime()
        today_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        # One combined aggregate for both the stat cards and today's snapshot -
        # conditional Count(filter=...) avoids a second query for the "today" row.
        context['stats'] = DSR.objects.aggregate(
            total=Count('pk'),
            draft=Count('pk', filter=Q(status=DSR.Status.DRAFT)),
            submitted=Count('pk', filter=Q(status=DSR.Status.SUBMITTED)),
            approved=Count('pk', filter=Q(status=DSR.Status.APPROVED)),
            rejected=Count('pk', filter=Q(status=DSR.Status.REJECTED)),
            submitted_today=Count('pk', filter=Q(submitted_at__gte=today_start, submitted_at__lt=today_end)),
            approved_today=Count('pk', filter=Q(
                status=DSR.Status.APPROVED, reviewed_at__gte=today_start, reviewed_at__lt=today_end,
            )),
            rejected_today=Count('pk', filter=Q(
                status=DSR.Status.REJECTED, reviewed_at__gte=today_start, reviewed_at__lt=today_end,
            )),
        )

        User = get_user_model()
        context['active_employee_count'] = User.objects.filter(
            role=User.Role.EMPLOYEE, is_active=True,
        ).count()

        # Oldest first - those reports have been waiting longest for review.
        context['pending_queue'] = DSR.objects.filter(
            status=DSR.Status.SUBMITTED,
        ).select_related('employee').order_by('submitted_at')[:10]

        context['recent_activity'] = DSR.objects.select_related('employee').order_by('-updated_at')[:8]
        return context


class EmployeeDashboardView(EmployeeRequiredMixin, TemplateView):
    template_name = 'accounts/dashboard_employee.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        own_reports = DSR.objects.filter(employee=user)

        context['stats'] = own_reports.aggregate(
            total=Count('pk'),
            draft=Count('pk', filter=Q(status=DSR.Status.DRAFT)),
            submitted=Count('pk', filter=Q(status=DSR.Status.SUBMITTED)),
            approved=Count('pk', filter=Q(status=DSR.Status.APPROVED)),
            rejected=Count('pk', filter=Q(status=DSR.Status.REJECTED)),
        )

        # Rejected, or sent-back-for-correction (DRAFT with leftover admin remarks) -
        # both need the employee to act. Capped at 10 as a lightweight safety bound.
        context['needs_attention'] = own_reports.filter(
            Q(status=DSR.Status.REJECTED)
            | (Q(status=DSR.Status.DRAFT) & ~Q(admin_remarks=''))
        ).order_by('-updated_at')[:10]

        context['recent_reports'] = own_reports.order_by('-updated_at')[:5]
        return context


class ProfileView(LoginRequiredMixin, UpdateView):
    form_class = ProfileUpdateForm
    template_name = 'accounts/profile.html'
    success_url = reverse_lazy('accounts:profile')

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, 'Profile updated successfully.')
        return super().form_valid(form)


class SafecurecsPasswordChangeView(PasswordChangeView):
    template_name = 'accounts/change_password.html'
    form_class = StyledPasswordChangeForm
    success_url = reverse_lazy('accounts:profile')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Password changed successfully.')
        return response


class EmployeeListView(AdminRequiredMixin, ListView):
    model = User
    template_name = 'accounts/employee_list.html'
    context_object_name = 'employees'
    paginate_by = 20

    def get_queryset(self):
        queryset = User.objects.filter(role=User.Role.EMPLOYEE)

        department_choices = (
            User.objects.filter(role=User.Role.EMPLOYEE)
            .exclude(department='').order_by('department')
            .values_list('department', flat=True).distinct()
        )
        self.filter_form = EmployeeFilterForm(
            self.request.GET or None, department_choices=[(d, d) for d in department_choices],
        )
        if self.filter_form.is_valid():
            data = self.filter_form.cleaned_data
            if data.get('q'):
                q = data['q']
                queryset = queryset.filter(
                    Q(employee_id__icontains=q) | Q(first_name__icontains=q)
                    | Q(last_name__icontains=q) | Q(email__icontains=q)
                )
            if data.get('is_active'):
                queryset = queryset.filter(is_active=(data['is_active'] == 'true'))
            if data.get('department'):
                queryset = queryset.filter(department=data['department'])
        return queryset.order_by('employee_id')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = self.filter_form
        params = self.request.GET.copy()
        params.pop('page', None)
        context['querystring'] = params.urlencode()
        return context


class EmployeeCreateView(AdminRequiredMixin, CreateView):
    form_class = EmployeeCreateForm
    template_name = 'accounts/employee_add.html'
    success_url = reverse_lazy('accounts:employee_list')

    def form_valid(self, form):
        self.object = form.save()
        messages.success(
            self.request,
            f'Employee {self.object.employee_id} created - ask them to change their password after first login.',
        )
        return redirect(self.success_url)


class EmployeeUpdateView(AdminRequiredMixin, UpdateView):
    form_class = EmployeeEditForm
    template_name = 'accounts/employee_edit.html'
    success_url = reverse_lazy('accounts:employee_list')

    def get_queryset(self):
        return User.objects.filter(role=User.Role.EMPLOYEE)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault('reset_password_form', StyledSetPasswordForm(self.object))
        return context

    def form_valid(self, form):
        messages.success(self.request, f'{self.object.employee_id} updated.')
        return super().form_valid(form)


class EmployeeResetPasswordView(AdminRequiredMixin, View):
    def post(self, request, pk):
        employee = get_object_or_404(User, pk=pk, role=User.Role.EMPLOYEE)
        form = StyledSetPasswordForm(employee, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f'Password reset for {employee.employee_id}.')
            return redirect('accounts:employee_edit', pk=employee.pk)

        messages.error(request, 'Could not reset password - see errors below.')
        return render(request, 'accounts/employee_edit.html', {
            'object': employee,
            'form': EmployeeEditForm(instance=employee),
            'reset_password_form': form,
        })
