from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.SafecurecsLoginView.as_view(), name='login'),
    path('logout/', views.SafecurecsLogoutView.as_view(), name='logout'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/change-password/', views.SafecurecsPasswordChangeView.as_view(), name='change_password'),
    path('dashboard/', views.EmployeeDashboardView.as_view(), name='employee_dashboard'),
    path('dashboard/admin/', views.AdminDashboardView.as_view(), name='admin_dashboard'),
    path('employees/', views.EmployeeListView.as_view(), name='employee_list'),
    path('employees/add/', views.EmployeeCreateView.as_view(), name='employee_add'),
    path('employees/<int:pk>/edit/', views.EmployeeUpdateView.as_view(), name='employee_edit'),
    path(
        'employees/<int:pk>/reset-password/',
        views.EmployeeResetPasswordView.as_view(), name='employee_reset_password',
    ),
]
