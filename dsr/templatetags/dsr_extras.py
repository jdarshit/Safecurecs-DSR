from django import template

from dsr.models import DSR

register = template.Library()

_BADGE_CLASSES = {
    DSR.Status.DRAFT: 'secondary',
    DSR.Status.SUBMITTED: 'primary',
    DSR.Status.APPROVED: 'success',
    DSR.Status.REJECTED: 'danger',
}


@register.filter
def status_badge_class(status):
    return _BADGE_CLASSES.get(status, 'secondary')


@register.simple_tag
def pending_dsr_count():
    """Count of reports awaiting admin review. Deliberately a template tag
    (not a context processor) so the query only runs when the admin sidebar
    branch is actually rendered, not on every page load sitewide. Still runs
    once per admin page view - acceptable at current volume; revisit (e.g.
    caching) if this becomes a measurable cost."""
    return DSR.objects.filter(status=DSR.Status.SUBMITTED).count()
