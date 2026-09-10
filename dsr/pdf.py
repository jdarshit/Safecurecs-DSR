"""PDF rendering for DSR reports via xhtml2pdf (chosen over WeasyPrint,
which requires GTK/Pango native libraries not available on this Windows
machine - confirmed by a failed runtime import before this choice was made).
"""

import io
import os

from django.conf import settings
from django.template.loader import render_to_string
from xhtml2pdf import pisa


def _link_callback(uri, rel):
    """Resolves MEDIA_URL-prefixed <img> URLs to absolute filesystem paths so
    xhtml2pdf can embed project photos. This is the standard, documented
    xhtml2pdf + Django integration recipe."""
    if uri.startswith(settings.MEDIA_URL):
        return os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, '', 1))
    return uri


def render_pdf(template_name, context):
    html = render_to_string(template_name, context)
    buf = io.BytesIO()
    pisa_status = pisa.CreatePDF(html, dest=buf, link_callback=_link_callback)
    if pisa_status.err:
        raise ValueError(f'Error generating PDF from template {template_name}')
    return buf.getvalue()
