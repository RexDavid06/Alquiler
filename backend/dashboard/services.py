"""Dashboard analytics services.

Pure read-only aggregation functions.  No data mutation.
All queries are scoped to the requesting user's data.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone

from core.models import User, Role
from leases.models import Lease, LeaseStatus
from payments.models import Payment, PaymentStatus, RentSchedule
from payments.services import period_status, RentPeriodStatus
from properties.models import Property, Unit, UnitStatus
from subscriptions.models import Subscription, SubscriptionStatus


def _parse_date(date_str):
    """Parse YYYY-MM-DD or return None."""
    if not date_str:
        return None
    try:
        return date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return None


def _validate_range(start_date, end_date):
    """Validate date range. Returns (start, end) or raises ValueError."""
    start = _parse_date(start_date)
    end = _parse_date(end_date)
    if start and end and start > end:
        raise ValueError('start_date must not be after end_date.')
    return start, end


# ---------------------------------------------------------------------------
# Landlord dashboard
# ---------------------------------------------------------------------------

def landlord_metrics(landlord, start_date=None, end_date=None):
    """Return aggregated KPIs for a landlord's dashboard.

    All data is scoped to the authenticated landlord.
    """
    today = timezone.localdate()

    # Property counts
    properties_qs = Property.objects.filter(landlord=landlord)
    total_properties = properties_qs.count()
    active_properties = properties_qs.filter(status='ACTIVE').count()

    # Unit counts
    unit_qs = Unit.objects.filter(property__landlord=landlord)
    total_units = unit_qs.count()
    occupied_units = unit_qs.filter(status=UnitStatus.OCCUPIED).count()
    vacant_units = total_units - occupied_units
    occupancy_rate = (
        round(occupied_units / total_units * 100, 1) if total_units > 0 else 0
    )

    # Lease counts
    lease_qs = Lease.objects.filter(landlord=landlord)
    total_leases = lease_qs.count()
    active_leases = lease_qs.filter(status=LeaseStatus.ACTIVE).count()
    expiring_leases = lease_qs.filter(status=LeaseStatus.EXPIRING).count()
    expired_leases = lease_qs.filter(status=LeaseStatus.EXPIRED).count()
    terminated_leases = lease_qs.filter(status=LeaseStatus.TERMINATED).count()

    # Revenue (PAID payments only)
    payment_qs = Payment.objects.filter(
        landlord=landlord, status=PaymentStatus.PAID,
    )
    if start_date:
        payment_qs = payment_qs.filter(payment_date__gte=start_date)
    if end_date:
        payment_qs = payment_qs.filter(payment_date__lte=end_date)
    total_revenue = payment_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    total_payments_count = payment_qs.count()

    # Overdue rent (all periods, not just date-filtered)
    overdue_total = Decimal('0')
    overdue_count = 0
    overdue_periods = RentSchedule.objects.filter(
        lease__landlord=landlord,
        due_date__lt=today,
    )
    for period in overdue_periods:
        ps = period_status(period, today)
        if ps in (RentPeriodStatus.OVERDUE, RentPeriodStatus.PARTIALLY_PAID):
            from payments.services import remaining_amount
            overdue_total += remaining_amount(period)
            overdue_count += 1

    # Upcoming rent (due today or later, not yet paid)
    upcoming_total = Decimal('0')
    upcoming_count = 0
    upcoming_periods = RentSchedule.objects.filter(
        lease__landlord=landlord,
        due_date__gte=today,
    )
    for period in upcoming_periods:
        ps = period_status(period, today)
        if ps in (RentPeriodStatus.UPCOMING, RentPeriodStatus.DUE):
            upcoming_total += period.amount
            upcoming_count += 1

    # Lease expiry alerts (next 30 days)
    expiry_horizon = today + timedelta(days=30)
    expiring_soon = lease_qs.filter(
        expiry_date__gt=today,
        expiry_date__lte=expiry_horizon,
        status__in=[LeaseStatus.ACTIVE, LeaseStatus.EXPIRING],
    ).select_related('tenant', 'property', 'unit').values(
        'id', 'tenant__email', 'property__name', 'unit__name',
        'expiry_date', 'rent_amount',
    )

    return {
        'properties': {
            'total': total_properties,
            'active': active_properties,
        },
        'units': {
            'total': total_units,
            'occupied': occupied_units,
            'vacant': vacant_units,
            'occupancy_rate': occupancy_rate,
        },
        'leases': {
            'total': total_leases,
            'active': active_leases,
            'expiring': expiring_leases,
            'expired': expired_leases,
            'terminated': terminated_leases,
        },
        'revenue': {
            'total': str(total_revenue),
            'payment_count': total_payments_count,
        },
        'overdue_rent': {
            'total': str(overdue_total),
            'period_count': overdue_count,
        },
        'upcoming_rent': {
            'total': str(upcoming_total),
            'period_count': upcoming_count,
        },
        'lease_expiry_alerts': [
            {k: str(v) if k == 'expiry_date' else v for k, v in row.items()}
            for row in expiring_soon
        ],
    }


def landlord_export_data(landlord):
    """Return all data needed for the landlord CSV export."""
    today = timezone.localdate()

    # Properties
    properties = list(
        Property.objects.filter(landlord=landlord).values_list(
            'name', 'property_type', 'address', 'city', 'status',
        )
    )

    # Units with occupancy
    units = list(
        Unit.objects.filter(property__landlord=landlord).values_list(
            'property__name', 'name', 'status',
        )
    )

    # Leases
    leases = list(
        Lease.objects.filter(landlord=landlord).values_list(
            'tenant__email', 'property__name', 'unit__name',
            'start_date', 'expiry_date', 'rent_amount', 'rent_frequency',
            'status',
        )
    )

    # Revenue
    revenue = Payment.objects.filter(
        landlord=landlord, status=PaymentStatus.PAID,
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

    # Overdue
    overdue_total = Decimal('0')
    overdue_count = 0
    for period in RentSchedule.objects.filter(
        lease__landlord=landlord, due_date__lt=today,
    ):
        ps = period_status(period, today)
        if ps in (RentPeriodStatus.OVERDUE, RentPeriodStatus.PARTIALLY_PAID):
            from payments.services import remaining_amount
            overdue_total += remaining_amount(period)
            overdue_count += 1

    # Upcoming
    upcoming_total = Decimal('0')
    upcoming_count = 0
    for period in RentSchedule.objects.filter(
        lease__landlord=landlord, due_date__gte=today,
    ):
        ps = period_status(period, today)
        if ps in (RentPeriodStatus.UPCOMING, RentPeriodStatus.DUE):
            upcoming_total += period.amount
            upcoming_count += 1

    # Lease expiry alerts (30 days)
    expiry_horizon = today + timedelta(days=30)
    expiry_alerts = list(
        Lease.objects.filter(
            landlord=landlord,
            expiry_date__gt=today,
            expiry_date__lte=expiry_horizon,
            status__in=[LeaseStatus.ACTIVE, LeaseStatus.EXPIRING],
        ).values_list(
            'tenant__email', 'property__name', 'unit__name',
            'expiry_date', 'rent_amount',
        )
    )

    return {
        'properties': properties,
        'units': units,
        'leases': leases,
        'revenue': revenue,
        'overdue_total': overdue_total,
        'overdue_count': overdue_count,
        'upcoming_total': upcoming_total,
        'upcoming_count': upcoming_count,
        'expiry_alerts': expiry_alerts,
    }


# ---------------------------------------------------------------------------
# Tenant dashboard
# ---------------------------------------------------------------------------

def tenant_metrics(tenant, start_date=None, end_date=None):
    """Return aggregated KPIs for a tenant's dashboard."""
    today = timezone.localdate()

    # Active leases
    active_leases_qs = Lease.objects.filter(
        tenant=tenant,
        status__in=[LeaseStatus.ACTIVE, LeaseStatus.EXPIRING],
    ).select_related('property', 'unit').values(
        'id', 'property__name', 'unit__name',
        'rent_amount', 'rent_frequency', 'expiry_date',
    )
    active_leases = [
        {k: str(v) if k == 'expiry_date' else v for k, v in row.items()}
        for row in active_leases_qs
    ]

    # Next rent due
    next_due = None
    for lease in Lease.objects.filter(
        tenant=tenant,
        status__in=[LeaseStatus.ACTIVE, LeaseStatus.EXPIRING],
    ):
        from payments.services import next_due as get_next_due
        nd = get_next_due(lease, today)
        if nd is not None:
            next_due = {
                'lease_id': lease.id,
                'property_name': lease.property.name,
                'unit_name': lease.unit.name,
                'period_id': nd.id,
                'due_date': str(nd.due_date),
                'amount': str(nd.amount),
                'currency': nd.currency,
            }
            break

    # Payment history
    payment_qs = Payment.objects.filter(
        tenant=tenant, status=PaymentStatus.PAID,
    ).select_related('lease__property', 'lease__unit')
    if start_date:
        payment_qs = payment_qs.filter(payment_date__gte=start_date)
    if end_date:
        payment_qs = payment_qs.filter(payment_date__lte=end_date)
    payment_history = [
        {k: str(v) if k == 'payment_date' else v for k, v in row.items()}
        for row in payment_qs.values(
            'id', 'amount', 'currency', 'payment_date',
            'payment_method', 'lease__property__name', 'lease__unit__name',
        )[:50]
    ]

    # Unread notifications
    from notifications.models import Notification
    unread_count = Notification.objects.filter(
        recipient=tenant, is_read=False,
    ).count()

    return {
        'active_leases': list(active_leases),
        'next_rent_due': next_due,
        'payment_history': payment_history,
        'unread_notifications': unread_count,
    }


# ---------------------------------------------------------------------------
# Admin dashboard
# ---------------------------------------------------------------------------

def admin_metrics(start_date=None, end_date=None):
    """Return platform-wide KPIs for the admin dashboard."""
    # User counts
    total_landlords = User.objects.filter(role=Role.LANDLORD).count()
    total_tenants = User.objects.filter(role=Role.TENANT).count()
    total_admins = User.objects.filter(role=Role.PLATFORM_ADMIN).count()
    total_users = total_landlords + total_tenants + total_admins

    # Subscription counts
    total_subscriptions = Subscription.objects.count()
    active_subscriptions = Subscription.objects.filter(
        status__in=[SubscriptionStatus.TRIAL, SubscriptionStatus.ACTIVE],
    ).count()
    trial_subscriptions = Subscription.objects.filter(
        status=SubscriptionStatus.TRIAL,
    ).count()
    cancelled_subscriptions = Subscription.objects.filter(
        status=SubscriptionStatus.CANCELLED,
    ).count()

    # Property/Unit/Lease counts
    total_properties = Property.objects.count()
    total_units = Unit.objects.count()
    total_leases = Lease.objects.count()

    # Revenue
    payment_qs = Payment.objects.filter(status=PaymentStatus.PAID)
    if start_date:
        payment_qs = payment_qs.filter(payment_date__gte=start_date)
    if end_date:
        payment_qs = payment_qs.filter(payment_date__lte=end_date)
    total_revenue = payment_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    total_payments = payment_qs.count()

    # System health
    health = _system_health()

    return {
        'users': {
            'total': total_users,
            'landlords': total_landlords,
            'tenants': total_tenants,
            'admins': total_admins,
        },
        'subscriptions': {
            'total': total_subscriptions,
            'active': active_subscriptions,
            'trial': trial_subscriptions,
            'cancelled': cancelled_subscriptions,
        },
        'properties': {
            'total': total_properties,
        },
        'units': {
            'total': total_units,
        },
        'leases': {
            'total': total_leases,
        },
        'revenue': {
            'total': str(total_revenue),
            'payment_count': total_payments,
        },
        'system_health': health,
    }


def admin_export_data(start_date=None, end_date=None):
    """Return all data needed for the admin CSV export."""
    metrics = admin_metrics(start_date=start_date, end_date=end_date)
    return metrics


def _system_health():
    """Run safe read-only health checks."""
    checks = {}

    # Database connectivity
    try:
        User.objects.only('id').first()
        checks['database'] = 'healthy'
    except Exception as e:
        checks['database'] = f'unhealthy: {type(e).__name__}'

    # Django system check (read-only)
    try:
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command('check', stdout=out, stderr=out)
        output = out.getvalue()
        if 'System check identified no issues' in output:
            checks['django_check'] = 'healthy'
        else:
            checks['django_check'] = f'issues found: {output.strip()[:200]}'
    except Exception as e:
        checks['django_check'] = f'unhealthy: {type(e).__name__}'

    # Migration state
    try:
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command('showmigrations', '--plan', stdout=out)
        output = out.getvalue()
        if '[ ]' in output:
            checks['migrations'] = 'pending migrations detected'
        else:
            checks['migrations'] = 'all applied'
    except Exception as e:
        checks['migrations'] = f'unhealthy: {type(e).__name__}'

    return checks
