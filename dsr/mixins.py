from django.db.models import Q

from .forms import AdminDSRFilterForm
from .models import DSR


class AdminDSRFilterMixin:
    """Shared filtered-queryset logic for the All Reports list and both
    list-level exports, so the filtering rules live in exactly one place."""

    def get_filtered_dsr_queryset(self):
        queryset = DSR.objects.select_related('employee', 'reviewed_by')
        self.filter_form = AdminDSRFilterForm(self.request.GET or None)
        if self.filter_form.is_valid():
            data = self.filter_form.cleaned_data
            if data.get('employee'):
                queryset = queryset.filter(employee=data['employee'])
            if data.get('client'):
                queryset = queryset.filter(client_name__icontains=data['client'])
            if data.get('project_type'):
                queryset = queryset.filter(project_type=data['project_type'])
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
                    | Q(employee__first_name__icontains=q) | Q(employee__last_name__icontains=q)
                    | Q(employee__employee_id__icontains=q)
                )
        return queryset

    def get_applied_filters_summary(self):
        """Human-readable summary of active filters, e.g.
        'Status: Submitted | Date: 01/07/2026 - 07/07/2026', for PDF headers."""
        form = getattr(self, 'filter_form', None)
        if not form or not form.is_valid():
            return ''

        data = form.cleaned_data
        parts = []
        if data.get('employee'):
            parts.append(f"Employee: {data['employee'].get_full_name()}")
        if data.get('client'):
            parts.append(f"Client: {data['client']}")
        if data.get('project_type'):
            parts.append(f"Project Type: {dict(DSR.ProjectType.choices).get(data['project_type'], data['project_type'])}")
        if data.get('status'):
            parts.append(f"Status: {dict(DSR.Status.choices).get(data['status'], data['status'])}")
        if data.get('date_from') or data.get('date_to'):
            date_from = data['date_from'].strftime('%d/%m/%Y') if data.get('date_from') else '...'
            date_to = data['date_to'].strftime('%d/%m/%Y') if data.get('date_to') else '...'
            parts.append(f"Date: {date_from} - {date_to}")
        if data.get('q'):
            parts.append(f'Search: "{data["q"]}"')

        return ' | '.join(parts) if parts else 'All Reports (no filters applied)'
