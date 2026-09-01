"""Rent schedule and rent-status domain services.

Rent is modelled as defined periods (RentSchedule rows) that are separate
from lease expiry. Due dates are generated from the lease's start date, rent
frequency and rent_due_day. Status (PAID/NOT_DUE/UPCOMING/DUE/OVERDUE) is
computed per period from the due date and whether a PAID payment covers it -
never inferred from payment records alone.
"""

from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from core.exceptions import DomainError

from .models import RentPeriodStatus, RentSchedule

FREQUENCY_MONTHS = {
    'MONTHLY': 1,
    'QUARTERLY': 3,
    'BI_ANNUALLY': 6,
    'ANNUALLY': 12,
}


def _next_month_date(base_date, months):
    return base_date + relativedelta(months=months)


def _normalize_due_day(month_date, due_day):
    """Clamp due_day to the last valid day of `month_date`'s month."""
    import calendar
    last_day = calendar.monthrange(month_date.year, month_date.month)[1]
    return date(
        month_date.year,
        month_date.month,
        min(due_day, last_day),
    )


def generate_schedule(lease):
    """Create the full RentSchedule for a lease if not already present.

    Periods are generated from start_date forward per rent_frequency,
    using the lease's rent_due_day (clamped to month length). Generation is
    idempotent: existing (lease, due_date) pairs are preserved.
    """
    frequency = lease.rent_frequency
    if frequency not in FREQUENCY_MONTHS:
        raise DomainError(f'Unsupported rent frequency: {frequency}.')

    months = FREQUENCY_MONTHS[frequency]
    created = []
    period_start = lease.start_date
    due_day = lease.rent_due_day

    # The first due date is the start date (or the clamped due day in the
    # lease start month). We anchor the first period at start_date.
    loop_date = period_start
    while loop_date <= lease.expiry_date:
        period_end = period_start + relativedelta(months=months, days=-1)
        if period_end > lease.expiry_date:
            period_end = lease.expiry_date
        due_date = _normalize_due_day(loop_date, due_day)
        # Avoid duplicate (lease, due_date) rows on idempotent regeneration.
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
        # Advance.
        period_start = period_end + timedelta(days=1)
        loop_date = _next_month_date(loop_date, months)
    return created


def period_status(rent_period, today=None):
    """Compute status for a single rent period (Billing-derived, not payment
    -only. A PAID payment associated with the period yields PAID; otherwise
    the period is classified against today's date.):
    """
    today = today or date.today()
    payment = rent_period.payment
    if payment is not None and payment.status == 'PAID':
        return RentPeriodStatus.PAID
    if rent_period.due_date > today:
        return RentPeriodStatus.UPCOMING
    if rent_period.due_date == today:
        return RentPeriodStatus.DUE
    return RentPeriodStatus.OVERDUE


def annotate_statuses(rent_periods, today=None):
    today = today or date.today()
    for period in rent_periods:
        period.status = period_status(period, today)
    return rent_periods


def next_due(lease, today=None):
    """Return the next unpaid rent period (due today or later), or None."""
    today = today or date.today()
    periods = lease.rent_schedule.filter(due_date__gte=today)
    for period in annotate_statuses(periods):
        if period.status == RentPeriodStatus.PAID:
            continue
        return period
    return None


def overdue_periods(lease, today=None):
    today = today or date.today()
    periods = lease.rent_schedule.filter(due_date__lt=today)
    return [
        p for p in annotate_statuses(periods)
        if p.status == RentPeriodStatus.OVERDUE
    ]


def unpaid_periods(lease, today=None):
    today = today or date.today()
    periods = lease.rent_schedule.all()
    return [
        p for p in annotate_statuses(periods)
        if p.status in (RentPeriodStatus.UPCOMING, RentPeriodStatus.DUE,
                        RentPeriodStatus.OVERDUE)
    ]


def settle_period(rent_period, payment):
    """Mark a rent period as settled by a PAID payment."""
    if payment.status != 'PAID':
        raise DomainError('Only PAID payments can settle a rent period.')
    rent_period.payment = payment
    rent_period.save(update_fields=['payment', 'updated_at'])
    return rent_period
