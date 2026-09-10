from django import forms
from django.contrib.auth import get_user_model

from .models import DSR


class DSRForm(forms.ModelForm):
    """Covers Sections 1-4 of the DSR spec form (auto/review fields are never
    part of this form, so no POST data can ever touch employee/status/dsr_number).

    `mode` controls validation strictness:
    - 'draft': only visit_date + client_name required, everything else optional.
    - 'submit': normal model-derived requiredness, plus work_done forced required
      (the model itself leaves work_done blank=True so drafts can be saved
      incomplete; "required at submit" is a transition-time rule, not a field
      rule, so it's the form/view's job to enforce it here for immediate
      feedback - DSR.submit() also enforces it server-side as the final guard).
    """

    class Meta:
        model = DSR
        fields = [
            'visit_date', 'purpose_of_visit',
            'client_name', 'company_name', 'contact_person', 'contact_number', 'client_email',
            'project_name', 'project_address', 'google_maps_link', 'project_type',
            'building_size', 'built_up_area', 'project_stage',
            'work_done', 'remarks', 'next_followup_date',
        ]
        widgets = {
            'visit_date': forms.DateInput(attrs={'type': 'date'}),
            'next_followup_date': forms.DateInput(attrs={'type': 'date'}),
            'project_address': forms.Textarea(attrs={'rows': 2}),
            'work_done': forms.Textarea(attrs={'rows': 3}),
            'remarks': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, mode='draft', **kwargs):
        self.mode = mode
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            css = field.widget.attrs.get('class', '')
            widget_type = field.widget.__class__.__name__
            base_class = 'form-select' if widget_type in ('Select', 'SelectMultiple') else 'form-control'
            field.widget.attrs['class'] = (css + ' ' + base_class).strip()

        if mode == 'draft':
            always_required = {'visit_date', 'client_name'}
            for name, field in self.fields.items():
                field.required = name in always_required
        else:
            self.fields['work_done'].required = True


class DSRFilterForm(forms.Form):
    status = forms.ChoiceField(
        choices=[('', 'All Statuses')] + DSR.Status.choices, required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'DSR #, client, company, project'}),
    )


class AdminDSRFilterForm(DSRFilterForm):
    """Same status/date-range/search fields as the employee filter form, plus
    the admin-only dimensions: which employee, which project type, and a
    dedicated client-name filter distinct from the general text search."""

    employee = forms.ModelChoiceField(
        queryset=get_user_model().objects.none(), required=False, label='Employee',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    client = forms.CharField(
        required=False, label='Client',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Client name'}),
    )
    project_type = forms.ChoiceField(
        choices=[('', 'All Project Types')] + DSR.ProjectType.choices, required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        User = get_user_model()
        self.fields['employee'].queryset = User.objects.filter(
            role=User.Role.EMPLOYEE, is_active=True,
        ).order_by('first_name', 'last_name')
        self.order_fields(['employee', 'client', 'project_type', 'status', 'date_from', 'date_to', 'q'])
