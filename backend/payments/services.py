"""Rent schedule and payment domain services.

All financial business logic lives here.  Views and serializers never
compute balances or mutate payment state directly.

Rent-period status is derived from:

    paid_amount = SUM(Payment.amount WHERE rent_period = period
                      AND status = PAID)

and compared to the period's ``amount``.  This is the single source of
truth -- no redundant balance fields are stored.

Concurrency: payment creation / update / cancellation lock the affected
rent-period rows (``select_for_update``) inside a ``transaction.atomic``
block so that simultaneous operations against the same period cannot
produce inconsistent balances.
"""

from datetime import date, timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from core.exceptions import ConflictError, DomainError

from .models import (
    Payment,
    PaymentMethod,
    PaymentStatus,
    RentPeriodStatus,
    RentSchedule,
)

FREQUENCY_MONTHS = {
    'MONTHLY': 1,
    'QUARTERLY': 3,
    'BI_ANNUALLY': 6,
    'ANNUALLY': 12,
}

# Only these payment statuses financially count toward a rent period.
FINANCIALLY_VALID_STATUSES = {PaymentStatus.PAID}


# ---------------------------------------------------------------------------
# Schedule generation
# ---------------------------------------------------------------------------

def _next_month_date(base_date, months):
    return base_date + relativedelta(months=months)


def _normalize_due_day(month_date, due_day):
    """Clamp due_day to the last valid day of ``month_date``'s month."""
    import calendar
    last_day = calendar.monthrange(month_date.year, month_date.month)[1]
    return date(month_date.year, month_date.month, min(due_day, last_day))


def generate_schedule(lease):
    """Create the full RentSchedule for a lease if not already present.

    Periods are generated from ``start_date`` forward per
    ``rent_frequency``, using the lease's ``rent_due_day`` (clamped to
    month length).  Generation is idempotent: existing
    ``(lease, due_date)`` pairs are preserved.
    """
    frequency = lease.rent_frequency
    if frequency not in FREQUENCY_MONTHS:
        raise DomainError(f'Unsupported rent frequency: {frequency}.')

    months = FREQUENCY_MONTHS[frequency]
    created = []
    period_start = lease.start_date
    due_day = lease.rent_due_day

    loop_date = period_start
    while loop_date <= lease.expiry_date:
        period_end = period_start + relativedelta(months=months, days=-1)
        if period_end > lease.expiry_date:
            # The natural period end exceeds the lease expiry.
            # Do not create a partial/clamped residual period.
            break
        due_date = _normalize_due_day(loop_date, due_day)
        if not RentSchedule.objects.filter(lease=lease, due_date=due_date).exists():
            rent = RentSchedule.objects.create(
                lease=lease,
                period_start=period_start,
                period_end=period_end,
                due_date=due_date,
                amount=lease.rent_amount,
                currency=lease.currency,
            )
            created.append(rent)
        period_start = period_end + timedelta(days=1)
        loop_date = _next_month_date(loop_date, months)
    return created


# ---------------------------------------------------------------------------
# Period status derivation
# ---------------------------------------------------------------------------

def _paid_amount_for_period(rent_period):
    """Aggregate of financially valid payments for a rent period.

    Only payments with status PAID are counted.  This is the single
    source of truth for how much has been paid toward a period.
    """
    result = Payment.objects.filter(
        rent_period=rent_period,
        status=PaymentStatus.PAID,
    ).aggregate(total=Sum('amount'))
    return result['total'] or Decimal('0')


def period_status(rent_period, today=None):
    """Derive the lifecycle status for a single rent period.

    Precedence (evaluated in order):

    1. paid >= amount  →  PAID
    2. 0 < paid < amount  →  PARTIALLY_PAID
    3. paid == 0 and due_date > today  →  UPCOMING
    4. paid == 0 and due_date == today  →  DUE
    5. paid == 0 and due_date < today  →  OVERDUE
    """
    today = today or timezone.localdate()
    paid = _paid_amount_for_period(rent_period)
    if paid >= rent_period.amount:
        return RentPeriodStatus.PAID
    if paid > 0:
        return RentPeriodStatus.PARTIALLY_PAID
    if rent_period.due_date > today:
        return RentPeriodStatus.UPCOMING
    if rent_period.due_date == today:
        return RentPeriodStatus.DUE
    return RentPeriodStatus.OVERDUE


def paid_amount(rent_period):
    """Public accessor for the aggregate paid amount of a period."""
    return _paid_amount_for_period(rent_period)


def remaining_amount(rent_period):
    """Amount still owed on a rent period (never negative)."""
    paid = _paid_amount_for_period(rent_period)
    leftover = rent_period.amount - paid
    return leftover if leftover > 0 else Decimal('0')


def annotate_statuses(rent_periods, today=None):
    """Attach a ``status`` attribute to each rent period in the list."""
    today = today or timezone.localdate()
    for period in rent_periods:
        period.status = period_status(period, today)
    return rent_periods


def next_due(lease, today=None):
    """Return the next unpaid rent period (due today or later), or None."""
    today = today or timezone.localdate()
    periods = lease.rent_schedule.filter(due_date__gte=today)
    for period in annotate_statuses(periods):
        if period.status == RentPeriodStatus.PAID:
            continue
        return period
    return None


def overdue_periods(lease, today=None):
    today = today or timezone.localdate()
    periods = lease.rent_schedule.filter(due_date__lt=today)
    return [
        p for p in annotate_statuses(periods)
        if p.status in (RentPeriodStatus.OVERDUE, RentPeriodStatus.PARTIALLY_PAID)
    ]


def unpaid_periods(lease, today=None):
    today = today or timezone.localdate()
    periods = lease.rent_schedule.all()
    return [
        p for p in annotate_statuses(periods)
        if p.status in (
            RentPeriodStatus.UPCOMING, RentPeriodStatus.DUE,
            RentPeriodStatus.OVERDUE, RentPeriodStatus.PARTIALLY_PAID,
        )
    ]


# ---------------------------------------------------------------------------
# Period lock helpers
# ---------------------------------------------------------------------------

def _lock_period(period_id):
    """Select-for-update a rent period row.  Returns the locked instance."""
    return (
        RentSchedule.objects
        .select_for_update()
        .get(pk=period_id)
    )


def _lock_two_periods(id_a, id_b):
    """Lock two rent-period rows in deterministic (ascending PK) order.

    Returns ``(locked_a, locked_b)`` in the *original* argument order.
    """
    if id_a == id_b:
        return _lock_period(id_a), None
    first_id, second_id = sorted((id_a, id_b))
    first = _lock_period(first_id)
    second = _lock_period(second_id)
    if first_id == id_a:
        return first, second
    return second, first


# ---------------------------------------------------------------------------
# Payment CRUD
# ---------------------------------------------------------------------------

def _validate_payment_lease_match(lease, tenant, rent_period=None):
    """Ensure the lease/tenant/period relationships are consistent."""
    if lease.tenant_id != tenant.id:
        raise ConflictError(
            'The specified tenant does not belong to this lease.',
            code='tenant_lease_mismatch',
        )
    if rent_period is not None:
        if rent_period.lease_id != lease.id:
            raise ConflictError(
                'The specified rent period does not belong to this lease.',
                code='period_lease_mismatch',
            )


@transaction.atomic
def record_payment(*, landlord, tenant, lease, rent_period=None,
                   amount, currency='NGN', payment_date,
                   payment_method=PaymentMethod.BANK_TRANSFER,
                   reference='', notes='', status=PaymentStatus.PAID,
                   recorded_by=None):
    """Create a payment record and recalculate the affected rent period.

    Row-level locking (``select_for_update``) on the rent period prevents
    concurrent payments from producing an inconsistent aggregate.
    """
    _validate_payment_lease_match(lease, tenant, rent_period)

    if rent_period is not None:
        locked = _lock_period(rent_period.pk)
    else:
        locked = None

    payment = Payment.objects.create(
        landlord=landlord,
        tenant=tenant,
        lease=lease,
        rent_period=locked,
        amount=amount,
        currency=currency,
        payment_date=payment_date,
        payment_method=payment_method,
        reference=reference,
        notes=notes,
        status=status,
        recorded_by=recorded_by,
    )
    return payment


@transaction.atomic
def update_payment(payment, *, amount=None, currency=None,
                   payment_date=None, payment_method=None,
                   reference=None, notes=None, status=None,
                   rent_period=None):
    """Update a payment and recalculate affected rent period(s).

    If the rent_period FK changes, both the old and new periods are
    locked in deterministic order (ascending PK) to prevent deadlocks.
    Locks are acquired BEFORE the payment is modified/saved so that
    concurrent operations against the same periods cannot observe
    inconsistent state.
    """
    old_period_id = payment.rent_period_id
    new_period_id = rent_period.pk if rent_period is not None else payment.rent_period_id

    # --- Acquire locks BEFORE modifying the payment ---
    affected_ids = {old_period_id, new_period_id} - {None}
    if affected_ids:
        sorted_ids = sorted(affected_ids)
        for pid in sorted_ids:
            RentSchedule.objects.select_for_update().get(pk=pid)

    # --- Now safe to modify the payment ---
    if amount is not None:
        payment.amount = amount
    if currency is not None:
        payment.currency = currency
    if payment_date is not None:
        payment.payment_date = payment_date
    if payment_method is not None:
        payment.payment_method = payment_method
    if reference is not None:
        payment.reference = reference
    if notes is not None:
        payment.notes = notes
    if status is not None:
        payment.status = status

    if rent_period is not None:
        payment.rent_period = rent_period

    payment.full_clean()
    payment.save()

    return payment


@transaction.atomic
def cancel_payment(payment):
    """Cancel a payment by setting status to CANCELLED.

    The rent-period aggregate is recalculated (derived from payment records)
    so the cancelled payment no longer counts toward the balance.
    Lock is acquired before modifying the payment.
    """
    if payment.status == PaymentStatus.CANCELLED:
        raise DomainError('Payment is already cancelled.', code='already_cancelled')

    # Lock the rent period row before changing payment status.
    period_id = payment.rent_period_id
    if period_id is not None:
        RentSchedule.objects.select_for_update().get(pk=period_id)

    payment.status = PaymentStatus.CANCELLED
    payment.save(update_fields=['status', 'updated_at'])
    return payment
