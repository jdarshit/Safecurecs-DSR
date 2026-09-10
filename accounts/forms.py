import os

from django import forms
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, SetPasswordForm
from django.db.models import Q

User = get_user_model()


def _apply_bootstrap_classes(fields):
    """Shared widget-styling pass: Select -> form-select, checkboxes ->
    form-check-input, everything else -> form-control. Mirrors the pattern
    already established in dsr.forms.DSRForm."""
    for field in fields.values():
        widget_type = field.widget.__class__.__name__
        if widget_type in ('Select', 'SelectMultiple'):
            css = 'form-select'
        elif widget_type == 'CheckboxInput':
            css = 'form-check-input'
        else:
            css = 'form-control'
        existing = field.widget.attrs.get('class', '')
        field.widget.attrs['class'] = (existing + ' ' + css).strip()

ALLOWED_PHOTO_EXTENSIONS = ('.jpg', '.jpeg', '.png')


class EmployeeAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label='Employee ID or Email',
        widget=forms.TextInput(attrs={'autofocus': True, 'class': 'form-control', 'placeholder': 'Employee ID or Email'}),
    )
    password = forms.CharField(
        label='Password',
        strip=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}),
    )

    error_messages = {
        'invalid_login': 'Please enter a correct Employee ID/Email and password.',
        'inactive': 'This account is inactive. Please contact your administrator.',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # AuthenticationForm.__init__ forces the username field's max_length
        # (and the rendered maxlength attribute) to USERNAME_FIELD's model
        # max_length - employee_id is only 20 chars, but this field must also
        # accept emails (up to 254). Reset both after the base class runs.
        self.fields['username'].max_length = 254
        self.fields['username'].widget.attrs['maxlength'] = 254

    def clean(self):
        identifier = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if identifier and password:
            existing_user = User.objects.filter(
                Q(employee_id=identifier) | Q(email__iexact=identifier)
            ).first()
            if existing_user and not existing_user.is_active:
                raise forms.ValidationError(self.error_messages['inactive'], code='inactive')

            self.user_cache = authenticate(self.request, username=identifier, password=password)
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data


class StyledPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')


class StyledSetPasswordForm(SetPasswordForm):
    """Django's own SetPasswordForm (validators + set_password on save),
    reused as-is for the admin 'Reset Password' action - only the widget
    styling is added, mirroring StyledPasswordChangeForm above."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')


class ProfileUpdateForm(forms.ModelForm):
    """Only the fields an employee may self-edit. Everything else (employee_id,
    name, department, designation, role) is intentionally absent here so it
    cannot be changed via POST regardless of what a client sends."""

    class Meta:
        model = User
        fields = ['profile_photo', 'email', 'mobile_number']
        widgets = {
            'profile_photo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'mobile_number': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.exclude(pk=self.instance.pk).filter(email__iexact=email).exists():
            raise forms.ValidationError('This email is already in use.')
        return email

    def clean_profile_photo(self):
        photo = self.cleaned_data.get('profile_photo')
        if photo and hasattr(photo, 'content_type'):
            ext = os.path.splitext(photo.name)[1].lower()
            if ext not in ALLOWED_PHOTO_EXTENSIONS:
                raise forms.ValidationError('Only JPG, JPEG, and PNG files are allowed.')
            max_bytes = settings.MAX_PROFILE_PHOTO_SIZE_MB * 1024 * 1024
            if photo.size > max_bytes:
                raise forms.ValidationError(
                    f'Image size must not exceed {settings.MAX_PROFILE_PHOTO_SIZE_MB} MB.'
                )
        return photo


class EmployeeCreateForm(forms.ModelForm):
    """Admin-facing employee onboarding form. Role/is_staff/is_superuser are
    never fields here - save() calls UserManager.create_user directly, which
    hardcodes role=EMPLOYEE whenever role isn't explicitly passed, so no
    injected POST data for those keys can ever have an effect."""

    password1 = forms.CharField(label='Password', strip=False, widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirm password', strip=False, widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['employee_id', 'email', 'first_name', 'last_name', 'mobile_number', 'department', 'designation']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_bootstrap_classes(self.fields)

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('The two password fields did not match.')
        return password2

    def _post_clean(self):
        # Mirrors django.contrib.auth.forms.UserCreationForm: run the normal
        # ModelForm validation first (so self.instance reflects the other
        # entered fields), then validate the password against that instance -
        # UserAttributeSimilarityValidator compares against employee_id/email/
        # name, not just the password in isolation.
        super()._post_clean()
        password = self.cleaned_data.get('password2')
        if password:
            try:
                password_validation.validate_password(password, self.instance)
            except forms.ValidationError as error:
                self.add_error('password2', error)

    def save(self):
        return User.objects.create_user(
            employee_id=self.cleaned_data['employee_id'],
            email=self.cleaned_data['email'],
            password=self.cleaned_data['password1'],
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            mobile_number=self.cleaned_data.get('mobile_number', ''),
            department=self.cleaned_data.get('department', ''),
            designation=self.cleaned_data.get('designation', ''),
        )


class EmployeeEditForm(forms.ModelForm):
    """Admin-facing employee edit form. employee_id and role are deliberately
    absent (shown read-only in the template instead), so neither can change
    regardless of injected POST data - same principle as ProfileUpdateForm."""

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'mobile_number', 'department', 'designation', 'is_active']
        labels = {'is_active': 'Active - can log in'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_bootstrap_classes(self.fields)

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.exclude(pk=self.instance.pk).filter(email__iexact=email).exists():
            raise forms.ValidationError('This email is already in use.')
        return email


class EmployeeFilterForm(forms.Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Employee ID, name, or email'}),
    )
    is_active = forms.ChoiceField(
        choices=[('', 'All'), ('true', 'Active'), ('false', 'Inactive')],
        required=False, widget=forms.Select(attrs={'class': 'form-select'}),
    )
    department = forms.ChoiceField(choices=[], required=False, widget=forms.Select(attrs={'class': 'form-select'}))

    def __init__(self, *args, department_choices=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['department'].choices = [('', 'All Departments')] + list(department_choices)
