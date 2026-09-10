import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .exceptions import InvalidStatusTransition
from .utils import generate_dsr_number
from .validators import validate_dsr_attachment

logger = logging.getLogger(__name__)


class DSRDailySequence(models.Model):
    """Internal per-day counter backing DSR number generation. Not exposed in admin."""

    date = models.DateField(unique=True)
    last_number = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f'{self.date}: {self.last_number}'


class DSR(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        SUBMITTED = 'SUBMITTED', 'Submitted'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'

    class PurposeOfVisit(models.TextChoices):
        INSTALLATION = 'INSTALLATION', 'Installation'
        SERVICE = 'SERVICE', 'Service'
        INSPECTION = 'INSPECTION', 'Inspection'
        AMC = 'AMC', 'AMC'
        MEETING = 'MEETING', 'Meeting'
        SURVEY = 'SURVEY', 'Survey'
        OTHER = 'OTHER', 'Other'

    class ProjectType(models.TextChoices):
        RESIDENTIAL = 'RESIDENTIAL', 'Residential'
        COMMERCIAL = 'COMMERCIAL', 'Commercial'
        INDUSTRIAL = 'INDUSTRIAL', 'Industrial'
        HOSPITAL = 'HOSPITAL', 'Hospital'
        SCHOOL_COLLEGE = 'SCHOOL_COLLEGE', 'School/College'
        HOTEL = 'HOTEL', 'Hotel'
        OFFICE = 'OFFICE', 'Office'
        FACTORY = 'FACTORY', 'Factory'
        WAREHOUSE = 'WAREHOUSE', 'Warehouse'
        GOVERNMENT = 'GOVERNMENT', 'Government'
        OTHER = 'OTHER', 'Other'

    class BuildingSize(models.TextChoices):
        SMALL = 'SMALL', 'Small'
        MEDIUM = 'MEDIUM', 'Medium'
        LARGE = 'LARGE', 'Large'

    class ProjectStage(models.TextChoices):
        NEW_CONSTRUCTION = 'NEW_CONSTRUCTION', 'New Construction'
        UNDER_CONSTRUCTION = 'UNDER_CONSTRUCTION', 'Under Construction'
        EXISTING_BUILDING = 'EXISTING_BUILDING', 'Existing Building'
        RENOVATION = 'RENOVATION', 'Renovation'

    ALLOWED_TRANSITIONS = {
        Status.DRAFT: {Status.SUBMITTED},
        Status.SUBMITTED: {Status.APPROVED, Status.REJECTED, Status.DRAFT},
        Status.REJECTED: {Status.SUBMITTED},
        Status.APPROVED: set(),
    }

    dsr_number = models.CharField(max_length=20, unique=True, editable=False)
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='dsrs')
    visit_date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    purpose_of_visit = models.CharField(max_length=20, choices=PurposeOfVisit.choices)

    # Client details (Section 2)
    client_name = models.CharField(max_length=150)
    company_name = models.CharField(max_length=150)
    contact_person = models.CharField(max_length=150)
    contact_number = models.CharField(max_length=20)
    client_email = models.EmailField(blank=True)

    # Project details (Section 3)
    project_name = models.CharField(max_length=200)
    project_address = models.TextField()
    google_maps_link = models.URLField(blank=True)
    project_type = models.CharField(max_length=20, choices=ProjectType.choices)
    building_size = models.CharField(max_length=10, choices=BuildingSize.choices)
    built_up_area = models.CharField(max_length=50, blank=True)
    project_stage = models.CharField(max_length=20, choices=ProjectStage.choices)

    # Visit information (Section 4)
    work_done = models.TextField(blank=True)
    remarks = models.TextField(blank=True)
    next_followup_date = models.DateField(null=True, blank=True)

    # Review / approval (stored on DSR, not a separate model)
    admin_remarks = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='dsrs_reviewed',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['visit_date']),
        ]

    def __str__(self):
        return self.dsr_number

    def save(self, *args, **kwargs):
        if self.pk is None and not self.dsr_number:
            self.dsr_number = generate_dsr_number()
        super().save(*args, **kwargs)

    def _check_transition(self, new_status):
        if new_status not in self.ALLOWED_TRANSITIONS.get(self.status, set()):
            raise InvalidStatusTransition(
                f'Cannot transition DSR {self.dsr_number} from {self.status} to {new_status}.'
            )

    def submit(self):
        """Owner action. Valid from DRAFT or REJECTED -> SUBMITTED."""
        self._check_transition(self.Status.SUBMITTED)
        if not self.work_done.strip():
            raise ValidationError({'work_done': 'Work Done is required before submitting.'})
        self.status = self.Status.SUBMITTED
        self.submitted_at = timezone.now()
        self.save(update_fields=['status', 'submitted_at', 'updated_at'])
        logger.info('DSR %s submitted by %s', self.dsr_number, self.employee.employee_id)

    def approve(self, reviewed_by, admin_remarks=''):
        """Admin action. Valid from SUBMITTED -> APPROVED. admin_remarks optional."""
        self._check_transition(self.Status.APPROVED)
        self.status = self.Status.APPROVED
        self.reviewed_by = reviewed_by
        self.reviewed_at = timezone.now()
        if admin_remarks:
            self.admin_remarks = admin_remarks
        self.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'admin_remarks', 'updated_at'])
        logger.info('DSR %s approved by %s', self.dsr_number, reviewed_by.employee_id)

    def reject(self, reviewed_by, admin_remarks):
        """Admin action. Valid from SUBMITTED -> REJECTED. admin_remarks required."""
        self._check_transition(self.Status.REJECTED)
        if not admin_remarks or not admin_remarks.strip():
            raise ValidationError({'admin_remarks': 'Admin remarks are required when rejecting a report.'})
        self.status = self.Status.REJECTED
        self.reviewed_by = reviewed_by
        self.reviewed_at = timezone.now()
        self.admin_remarks = admin_remarks
        self.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'admin_remarks', 'updated_at'])
        logger.info('DSR %s rejected by %s', self.dsr_number, reviewed_by.employee_id)

    def send_back(self, reviewed_by, admin_remarks=''):
        """Admin action ('send back for correction'). Valid from SUBMITTED -> DRAFT.
        admin_remarks required (the employee needs to know what to fix)."""
        self._check_transition(self.Status.DRAFT)
        if not admin_remarks or not admin_remarks.strip():
            raise ValidationError({'admin_remarks': 'Admin remarks are required when sending a report back for correction.'})
        self.status = self.Status.DRAFT
        self.reviewed_by = reviewed_by
        self.reviewed_at = timezone.now()
        self.admin_remarks = admin_remarks
        self.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'admin_remarks', 'updated_at'])
        logger.info('DSR %s sent back for correction by %s', self.dsr_number, reviewed_by.employee_id)

    def can_edit(self, user):
        """True only if `user` owns this DSR AND it is currently editable (DRAFT/REJECTED)."""
        return self.employee_id == user.pk and self.status in (self.Status.DRAFT, self.Status.REJECTED)


def dsr_attachment_upload_path(instance, filename):
    return f'dsr_attachments/{instance.dsr.dsr_number}/{filename}'


class DSRAttachment(models.Model):
    class Category(models.TextChoices):
        PROJECT_PHOTO = 'PROJECT_PHOTO', 'Project Photo'
        ATTACHMENT = 'ATTACHMENT', 'Attachment'

    dsr = models.ForeignKey(DSR, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to=dsr_attachment_upload_path, max_length=255, validators=[validate_dsr_attachment])
    original_filename = models.CharField(max_length=255)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.ATTACHMENT)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['uploaded_at']

    def __str__(self):
        return self.original_filename

    @property
    def is_pdf(self):
        return self.file.name.lower().endswith('.pdf')
