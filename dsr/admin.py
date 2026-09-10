from django.contrib import admin

from .models import DSR, DSRAttachment


class DSRAttachmentInline(admin.TabularInline):
    model = DSRAttachment
    extra = 0
    fields = ['file', 'original_filename', 'category', 'uploaded_at']
    readonly_fields = ['uploaded_at']


@admin.register(DSR)
class DSRAdmin(admin.ModelAdmin):
    list_display = ['dsr_number', 'employee', 'client_name', 'visit_date', 'status', 'created_at']
    list_filter = ['status', 'project_type', 'visit_date']
    search_fields = [
        'dsr_number', 'client_name', 'company_name', 'project_name',
        'employee__employee_id', 'employee__first_name', 'employee__last_name',
    ]
    readonly_fields = ['dsr_number', 'submitted_at', 'reviewed_by', 'reviewed_at', 'created_at', 'updated_at']
    inlines = [DSRAttachmentInline]
    ordering = ['-created_at']


@admin.register(DSRAttachment)
class DSRAttachmentAdmin(admin.ModelAdmin):
    list_display = ['dsr', 'category', 'original_filename', 'uploaded_at']
    list_filter = ['category']
    readonly_fields = ['uploaded_at']
