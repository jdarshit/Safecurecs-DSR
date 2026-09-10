from django.urls import reverse


def get_dashboard_url(user):
    """Single source of truth for 'where does this user belong' by role."""
    if user.role == user.Role.ADMIN:
        return reverse('accounts:admin_dashboard')
    return reverse('accounts:employee_dashboard')
