import io

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from accounts.mixins import AdminRequiredMixin, EmployeeRequiredMixin

from .exceptions import InvalidStatusTransition
from .exports import build_dsr_excel_workbook
from .forms import DSRFilterForm, DSRForm
from .mixins import AdminDSRFilterMixin
from .models import DSR, DSRAttachment
from .pdf import render_pdf
from .validators import validate_dsr_attachment

User = get_user_model()


def _validate_uploaded_files(files):
    """Validate raw request.FILES uploads before anything is persisted, so a
    bad file in one input doesn't leave a half-saved DSR behind."""
    errors = []
    for f in files:
        try:
            validate_dsr_attachment(f)
        except ValidationError as exc:
            errors.append(f'{f.name}: {" ".join(exc.messages)}')
    return errors


class DSRFormMixin:
    model = DSR
    form_class = DSRForm
    template_name = 'dsr/dsr_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['mode'] = 'submit' if self.request.POST.get('action') == 'submit' else 'draft'
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = getattr(self, 'object', None)
        if obj and obj.pk:
            context['project_photos'] = obj.attachments.filter(category=DSRAttachment.Category.PROJECT_PHOTO)
            context['other_attachments'] = obj.attachments.filter(category=DSRAttachment.Category.ATTACHMENT)
            context['can_edit'] = obj.can_edit(self.request.user)
        else:
            context['project_photos'] = DSRAttachment.objects.none()
            context['other_attachments'] = DSRAttachment.objects.none()
            context['can_edit'] = True
        context['max_attachment_size_mb'] = settings.MAX_DSR_ATTACHMENT_SIZE_MB
        return context

    def form_valid(self, form):
        action = self.request.POST.get('action')
        photo_files = self.request.FILES.getlist('project_photos')
        attachment_files = self.request.FILES.getlist('attachments')

        file_errors = _validate_uploaded_files(photo_files) + _validate_uploaded_files(attachment_files)
        if file_errors:
            for err in file_errors:
                form.add_error(None, err)
            return self.form_invalid(form)

        try:
            with transaction.atomic():
                if form.instance.pk is None and not form.instance.employee_id:
                    form.instance.employee = self.request.user

                if action == 'save_draft':
                    # Saving a REJECTED report as a draft keeps it REJECTED (still
                    # visible in the admin's rejected queue while corrections are
                    # in progress) - only new/already-DRAFT reports get DRAFT set.
                    if not (form.instance.pk and form.instance.status == DSR.Status.REJECTED):
                        form.instance.status = DSR.Status.DRAFT
                    self.object = form.save()
                else:
                    self.object = form.save()
                    self.object.submit()

                for f in photo_files:
                    DSRAttachment.objects.create(
                        dsr=self.object, file=f, original_filename=f.name,
                        category=DSRAttachment.Category.PROJECT_PHOTO,
                    )
                for f in attachment_files:
                    DSRAttachment.objects.create(
                        dsr=self.object, file=f, original_filename=f.name,
                        category=DSRAttachment.Category.ATTACHMENT,
                    )
        except InvalidStatusTransition as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)
        except ValidationError as exc:
            form.add_error(None, ' '.join(exc.messages))
            return self.form_invalid(form)

        if action == 'save_draft':
            messages.success(self.request, f'Draft saved ({self.object.dsr_number}).')
        else:
            messages.success(self.request, f'{self.object.dsr_number} submitted for review.')
        return redirect('dsr:detail', pk=self.object.pk)


class DSRCreateView(EmployeeRequiredMixin, DSRFormMixin, CreateView):
    pass


class DSRUpdateView(EmployeeRequiredMixin, DSRFormMixin, UpdateView):
    def get_queryset(self):
        return DSR.objects.filter(employee=self.request.user)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.can_edit(request.user):
            messages.error(request, 'This report can no longer be edited.')
            return redirect('dsr:detail', pk=self.object.pk)
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.can_edit(request.user):
            messages.error(request, 'This report can no longer be edited.')
            return redirect('dsr:detail', pk=self.object.pk)
        return super().post(request, *args, **kwargs)


class DSRDetailView(EmployeeRequiredMixin, DetailView):
    model = DSR
    template_name = 'dsr/dsr_detail.html'

    def get_queryset(self):
        return DSR.objects.filter(employee=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['project_photos'] = self.object.attachments.filter(category=DSRAttachment.Category.PROJECT_PHOTO)
        context['other_attachments'] = self.object.attachments.filter(category=DSRAttachment.Category.ATTACHMENT)
        context['can_edit'] = self.object.can_edit(self.request.user)
        return context


class DSRListView(EmployeeRequiredMixin, ListView):
    model = DSR
    template_name = 'dsr/dsr_list.html'
    context_object_name = 'dsrs'
    paginate_by = 15

    def get_queryset(self):
        queryset = DSR.objects.filter(employee=self.request.user)
        self.filter_form = DSRFilterForm(self.request.GET or None)
        if self.filter_form.is_valid():
            data = self.filter_form.cleaned_data
            if data.get('status'):
                queryset = queryset.filter(status=data['status'])
            if data.get('date_from'):
                queryset = queryset.filter(visit_date__gte=data['date_from'])
            if data.get('date_to'):
                queryset = queryset.filter(visit_date__lte=data['date_to'])
            if data.get('q'):
                q = data['q']
                queryset = queryset.filter(
                    Q(dsr_number__icontains=q) | Q(client_name__icontains=q)
                    | Q(company_name__icontains=q) | Q(project_name__icontains=q)
                )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = self.filter_form
        params = self.request.GET.copy()
        params.pop('page', None)
        context['querystring'] = params.urlencode()
        return context


class DSRAttachmentDeleteView(EmployeeRequiredMixin, View):
    def post(self, request, pk, attachment_pk):
        dsr = get_object_or_404(DSR, pk=pk, employee=request.user)
        if not dsr.can_edit(request.user):
            messages.error(request, 'This report can no longer be edited.')
            return redirect('dsr:detail', pk=dsr.pk)
        attachment = get_object_or_404(DSRAttachment, pk=attachment_pk, dsr=dsr)
        attachment.file.delete(save=False)
        attachment.delete()
        messages.success(request, 'Attachment removed.')
        return redirect('dsr:edit', pk=dsr.pk)


STATUS_TABS = [
    ('', 'All'),
    (DSR.Status.SUBMITTED, 'Submitted'),
    (DSR.Status.APPROVED, 'Approved'),
    (DSR.Status.REJECTED, 'Rejected'),
    (DSR.Status.DRAFT, 'Draft'),
]


class AdminDSRListView(AdminRequiredMixin, AdminDSRFilterMixin, ListView):
    model = DSR
    template_name = 'dsr/admin_dsr_list.html'
    context_object_name = 'dsrs'
    paginate_by = 20

    def get_queryset(self):
        return self.get_filtered_dsr_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = self.filter_form
        params = self.request.GET.copy()
        params.pop('page', None)
        context['querystring'] = params.urlencode()

        # One aggregate query for tab counts - deliberately computed over the
        # whole (unfiltered) DSR table, not recombined with the active filters,
        # so the tabs stay simple "quick jump" shortcuts rather than needing a
        # second filtered-minus-status query.
        counts = dict(DSR.objects.values_list('status').annotate(count=Count('pk')))
        total = sum(counts.values())
        current_status = self.request.GET.get('status', '')
        context['status_tabs'] = [
            {
                'value': value,
                'label': label,
                'count': total if value == '' else counts.get(value, 0),
                'active': current_status == value,
            }
            for value, label in STATUS_TABS
        ]
        return context


class AdminDSRReviewView(AdminRequiredMixin, DetailView):
    model = DSR
    template_name = 'dsr/admin_dsr_review.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['project_photos'] = self.object.attachments.filter(category=DSRAttachment.Category.PROJECT_PHOTO)
        context['other_attachments'] = self.object.attachments.filter(category=DSRAttachment.Category.ATTACHMENT)
        context['can_review'] = self.object.status == DSR.Status.SUBMITTED
        context.setdefault('submitted_remarks', self.object.admin_remarks)
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        action = request.POST.get('action')
        remarks = request.POST.get('admin_remarks', '').strip()

        if self.object.status != DSR.Status.SUBMITTED:
            messages.error(request, 'This report is not awaiting review.')
            return redirect('dsr:review', pk=self.object.pk)

        try:
            if action == 'approve':
                self.object.approve(request.user, remarks)
            elif action == 'reject':
                self.object.reject(request.user, remarks)
            elif action == 'send_back':
                self.object.send_back(request.user, remarks)
            else:
                messages.error(request, 'Unknown action.')
                return redirect('dsr:review', pk=self.object.pk)
        except (InvalidStatusTransition, ValidationError) as exc:
            error_message = str(exc) if isinstance(exc, InvalidStatusTransition) else ' '.join(exc.messages)
            context = self.get_context_data()
            context['review_error'] = error_message
            context['submitted_remarks'] = remarks
            return self.render_to_response(context)

        action_labels = {'approve': 'approved', 'reject': 'rejected', 'send_back': 'sent back for correction'}
        messages.success(request, f'{self.object.dsr_number} {action_labels.get(action, "updated")}.')
        return redirect('dsr:review', pk=self.object.pk)


class AdminDSRExcelExportView(AdminRequiredMixin, AdminDSRFilterMixin, View):
    def get(self, request, *args, **kwargs):
        queryset = self.get_filtered_dsr_queryset()
        wb = build_dsr_excel_workbook(queryset)
        buf = io.BytesIO()
        wb.save(buf)

        filename = f"DSR_Reports_{timezone.localtime().strftime('%Y%m%d-%H%M')}.xlsx"
        response = HttpResponse(
            buf.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class AdminDSRPDFExportView(AdminRequiredMixin, AdminDSRFilterMixin, View):
    def get(self, request, *args, **kwargs):
        queryset = self.get_filtered_dsr_queryset()
        context = {
            'dsrs': queryset,
            'generated_at': timezone.localtime(),
            'filters_summary': self.get_applied_filters_summary(),
            'total_count': queryset.count(),
        }
        pdf_bytes = render_pdf('dsr/pdf/dsr_list_pdf.html', context)

        filename = f"DSR_Reports_{timezone.localtime().strftime('%Y%m%d-%H%M')}.pdf"
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class DSRSinglePDFExportView(LoginRequiredMixin, View):
    """Deliberate exception to admin-only exports: an employee may download
    the PDF for their OWN report, but only once it's APPROVED (the final,
    signed-off version). Cross-user access still 404s (existing ownership
    convention); own-but-not-yet-approved redirects with a message, matching
    how can_edit()-blocked access is handled elsewhere - the report is
    theirs, so a bare 404 would be the wrong signal."""

    def get(self, request, pk):
        if request.user.role == User.Role.ADMIN:
            dsr = get_object_or_404(DSR, pk=pk)
        else:
            dsr = get_object_or_404(DSR, pk=pk, employee=request.user)
            if dsr.status != DSR.Status.APPROVED:
                messages.error(request, 'PDF download is only available once a report is approved.')
                return redirect('dsr:detail', pk=dsr.pk)

        project_photos = []
        for photo in dsr.attachments.filter(category=DSRAttachment.Category.PROJECT_PHOTO):
            try:
                file_exists = bool(photo.file) and photo.file.storage.exists(photo.file.name)
            except Exception:
                file_exists = False
            if file_exists:
                project_photos.append(photo)
        photo_rows = [project_photos[i:i + 2] for i in range(0, len(project_photos), 2)]

        other_attachments = dsr.attachments.filter(category=DSRAttachment.Category.ATTACHMENT)

        context = {
            'dsr': dsr,
            'photo_rows': photo_rows,
            'other_attachments': other_attachments,
            'generated_at': timezone.localtime(),
        }
        pdf_bytes = render_pdf('dsr/pdf/dsr_single_pdf.html', context)

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{dsr.dsr_number}.pdf"'
        return response


class DSRAttachmentDownloadView(LoginRequiredMixin, View):
    """Serves a DSR attachment through Django (owner or admin only) instead of
    letting the web server expose the dsr_attachments directory directly -
    those files contain private client data. Profile photos are unaffected
    and remain on direct /media/ serving (see CLAUDE.md)."""

    def get(self, request, pk):
        attachment = get_object_or_404(DSRAttachment, pk=pk)
        dsr = attachment.dsr
        is_owner = dsr.employee_id == request.user.pk
        is_admin = request.user.role == User.Role.ADMIN
        if not (is_owner or is_admin):
            raise Http404

        if not attachment.file or not attachment.file.storage.exists(attachment.file.name):
            raise Http404

        return FileResponse(
            attachment.file.open('rb'),
            filename=attachment.original_filename,
            as_attachment=False,
        )
