from django.db import OperationalError, transaction
from django.utils import timezone

# When many concurrent transactions race to INSERT the very first sequence row
# for a brand-new day, InnoDB's gap-locking can produce a genuine deadlock
# (error 1213) even though select_for_update() correctly serializes access once
# the row exists. A bounded retry is the standard, documented way to handle this
# MySQL behavior - the failed transaction is fully rolled back, so retrying is safe.
_MAX_ATTEMPTS = 5


def generate_dsr_number():
    """Race-safe daily-resetting DSR number: DSR-YYYYMMDD-XXXX.

    Uses select_for_update() on a per-day counter row so concurrent creations
    serialize on that single row (InnoDB row lock) instead of racing on a
    COUNT()-then-insert against the DSR table itself.
    """
    from .models import DSRDailySequence

    today = timezone.localdate()
    last_error = None
    for _ in range(_MAX_ATTEMPTS):
        try:
            with transaction.atomic():
                seq, _created = DSRDailySequence.objects.select_for_update().get_or_create(
                    date=today, defaults={'last_number': 0}
                )
                seq.last_number += 1
                seq.save(update_fields=['last_number'])
                return f'DSR-{today.strftime("%Y%m%d")}-{seq.last_number:04d}'
        except OperationalError as exc:
            last_error = exc
    raise last_error
