from django.contrib import messages
from django.contrib.auth.mixins import AccessMixin
from django.shortcuts import redirect

from .utils import get_dashboard_url


class RoleRequiredMixin(AccessMixin):
    """Base for role-gated CBVs. Subclass and set allowed_roles."""

    allowed_roles = ()

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.role not in self.allowed_roles:
            messages.error(request, "You don't have permission to access that page.")
            return redirect(get_dashboard_url(request.user))
        return super().dispatch(request, *args, **kwargs)


class AdminRequiredMixin(RoleRequiredMixin):
    allowed_roles = ('ADMIN',)


class EmployeeRequiredMixin(RoleRequiredMixin):
    allowed_roles = ('EMPLOYEE',)
