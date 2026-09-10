from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ['employee_id']
    list_display = ['employee_id', 'email', 'first_name', 'last_name', 'role', 'department', 'is_active', 'is_staff']
    list_filter = ['role', 'department', 'is_active', 'is_staff']
    search_fields = ['employee_id', 'email', 'first_name', 'last_name']

    fieldsets = (
        (None, {'fields': ('employee_id', 'email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'mobile_number', 'profile_photo')}),
        ('Work info', {'fields': ('department', 'designation', 'role')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined', 'created_at', 'updated_at')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('employee_id', 'email', 'first_name', 'last_name', 'role', 'password1', 'password2'),
        }),
    )
    readonly_fields = ['last_login', 'date_joined', 'created_at', 'updated_at']
