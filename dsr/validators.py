import os

from django.conf import settings
from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError

ALLOWED_ATTACHMENT_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.pdf')
PDF_MAGIC_BYTES = b'%PDF'


def validate_dsr_attachment(file):
    """Extension allowlist + size cap + real content sniff.

    Skips already-committed FieldFiles on resave. Note this deliberately checks
    `_committed` rather than `hasattr(file, 'content_type')`: when this validator
    runs as a model-field validator (attached via `FileField(validators=[...])`),
    Django's FileField descriptor has already wrapped any newly-assigned file into
    a FieldFile by the time full_clean()/run_validators() sees it, and FieldFile
    never exposes `.content_type` (that only exists on the raw UploadedFile) even
    for a brand-new, not-yet-saved upload — so a `content_type` check would always
    skip validation here. `_committed` correctly distinguishes "freshly assigned,
    not yet saved" (False) from "already stored" (True) in both this
    model-validator context and a plain UploadedFile passed in directly."""
    if getattr(file, '_committed', False):
        return

    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_ATTACHMENT_EXTENSIONS:
        raise ValidationError('Only JPG, JPEG, PNG, and PDF files are allowed.')

    max_bytes = settings.MAX_DSR_ATTACHMENT_SIZE_MB * 1024 * 1024
    if file.size > max_bytes:
        raise ValidationError(f'File size must not exceed {settings.MAX_DSR_ATTACHMENT_SIZE_MB} MB.')

    file.seek(0)
    try:
        if ext == '.pdf':
            if file.read(4) != PDF_MAGIC_BYTES:
                raise ValidationError('File does not appear to be a valid PDF.')
        else:
            try:
                Image.open(file).verify()
            except (UnidentifiedImageError, OSError):
                raise ValidationError('File does not appear to be a valid image.')
    finally:
        file.seek(0)
