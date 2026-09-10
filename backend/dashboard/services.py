"""Dashboard analytics services.

Pure read-only aggregation functions.  No data mutation.
All queries are scoped to the requesting user's data.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from core.models import AccountStatus, User, Role
from leases.models import Lease, LeaseStatus
from payments.models import Payment, PaymentStatus, RentSchedule
from payments.services import period_status, RentPeriodStatus
from properties.models import Property, Unit, UnitStatus
from subscriptions.models import PlanTier, Subscription, SubscriptionStatus


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
        'collected_rent': {
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
        'collected_rent': revenue,
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
# Admin dashboard — comprehensive platform analytics
# ---------------------------------------------------------------------------

def admin_metrics(start_date=None, end_date=None):
    """Return platform-wide KPIs for the admin dashboard.

    Provides comprehensive business intelligence including:
    - User counts by role and status
    - Unit occupancy breakdown
    - Lease status breakdown
    - Payment/revenue with period comparison
    - Outstanding and overdue rent
    - Subscription distribution by plan tier
    - 12-month growth trends
    - System health
    """
    today = timezone.localdate()
    today_dt = timezone.now()

    # =========================================================================
    # USER KPIs
    # =========================================================================
    total_landlords = User.objects.filter(role=Role.LANDLORD).count()
    total_tenants = User.objects.filter(role=Role.TENANT).count()
    total_admins = User.objects.filter(role=Role.PLATFORM_ADMIN).count()
    total_users = total_landlords + total_tenants + total_admins

    active_landlords = User.objects.filter(
        role=Role.LANDLORD, status=AccountStatus.ACTIVE,
    ).count()
    suspended_landlords = User.objects.filter(
        role=Role.LANDLORD, status=AccountStatus.SUSPENDED,
    ).count()
    active_tenants = User.objects.filter(
        role=Role.TENANT, status=AccountStatus.ACTIVE,
    ).count()
    suspended_tenants = User.objects.filter(
        role=Role.TENANT, status=AccountStatus.SUSPENDED,
    ).count()

    # =========================================================================
    # PROPERTY & UNIT KPIs (with occupancy)
    # =========================================================================
    total_properties = Property.objects.count()
    total_units = Unit.objects.count()
    occupied_units = Unit.objects.filter(status=UnitStatus.OCCUPIED).count()
    vacant_units = Unit.objects.filter(status=UnitStatus.VACANT).count()
    occupancy_rate = (
        round(occupied_units / total_units * 100, 1) if total_units > 0 else 0
    )

    # =========================================================================
    # LEASE KPIs (status breakdown)
    # =========================================================================
    total_leases = Lease.objects.count()
    active_leases = Lease.objects.filter(status=LeaseStatus.ACTIVE).count()
    expiring_leases = Lease.objects.filter(status=LeaseStatus.EXPIRING).count()
    expired_leases = Lease.objects.filter(status=LeaseStatus.EXPIRED).count()
    terminated_leases = Lease.objects.filter(
        status=LeaseStatus.TERMINATED,
    ).count()
    future_leases = Lease.objects.filter(status=LeaseStatus.FUTURE).count()

    # =========================================================================
    # PAYMENT / REVENUE KPIs
    # =========================================================================
    all_paid = Payment.objects.filter(status=PaymentStatus.PAID)

    # Total revenue (all-time)
    total_revenue = all_paid.aggregate(
        total=Sum('amount'),
    )['total'] or Decimal('0')
    total_payments_count = all_paid.count()

    # Current period (date-filtered) revenue
    period_qs = all_paid
    if start_date:
        period_qs = period_qs.filter(payment_date__gte=start_date)
    if end_date:
        period_qs = period_qs.filter(payment_date__lte=end_date)
    period_revenue = period_qs.aggregate(
        total=Sum('amount'),
    )['total'] or Decimal('0')
    period_payments_count = period_qs.count()

    # Previous period (same duration, before the current period)
    previous_revenue = Decimal('0')
    previous_payments_count = 0
    if start_date and end_date:
        duration = (end_date - start_date).days
        prev_start = start_date - timedelta(days=duration + 1)
        prev_end = start_date - timedelta(days=1)
        prev_qs = all_paid.filter(
            payment_date__gte=prev_start,
            payment_date__lte=prev_end,
        )
        previous_revenue = prev_qs.aggregate(
            total=Sum('amount'),
        )['total'] or Decimal('0')
        previous_payments_count = prev_qs.count()
    elif start_date:
        prev_qs = all_paid.filter(payment_date__lt=start_date)
        previous_revenue = prev_qs.aggregate(
            total=Sum('amount'),
        )['total'] or Decimal('0')
        previous_payments_count = prev_qs.count()

    # Revenue growth (percentage)
    revenue_growth = None
    if previous_revenue > 0:
        revenue_growth = round(
            float((period_revenue - previous_revenue) / previous_revenue * 100), 1,
        )

    # =========================================================================
    # OUTSTANDING & OVERDUE RENT (annotated — single query, no N+1)
    # =========================================================================
    overdue_periods_qs = (
        RentSchedule.objects
        .filter(due_date__lt=today)
        .annotate(
            _paid=Sum(
                'payments__amount',
                filter=Q(payments__status=PaymentStatus.PAID),
                default=Decimal('0'),
            ),
        )
    )

    outstanding_total = Decimal('0')
    outstanding_count = 0
    overdue_total = Decimal('0')
    overdue_count = 0

    for period in overdue_periods_qs:
        paid = period._paid
        if paid >= period.amount:
            continue
        remaining = period.amount - paid
        outstanding_total += remaining
        outstanding_count += 1
        if paid == 0:
            overdue_total += remaining
            overdue_count += 1

    # =========================================================================
    # SUBSCRIPTION KPIs (with plan tier breakdown)
    # =========================================================================
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
    past_due_subscriptions = Subscription.objects.filter(
        status=SubscriptionStatus.PAST_DUE,
    ).count()
    expired_subscriptions = Subscription.objects.filter(
        status=SubscriptionStatus.EXPIRED,
    ).count()

    # Plan tier breakdown
    free_count = Subscription.objects.filter(
        plan__tier=PlanTier.FREE,
    ).count()
    professional_count = Subscription.objects.filter(
        plan__tier=PlanTier.PROFESSIONAL,
    ).count()
    business_count = Subscription.objects.filter(
        plan__tier=PlanTier.BUSINESS,
    ).count()

    # =========================================================================
    # GROWTH TRENDS (last 12 months)
    # =========================================================================
    twelve_months_ago = today - timedelta(days=365)
    growth_trends = _compute_growth_trends(twelve_months_ago)

    # =========================================================================
    # SYSTEM HEALTH
    # =========================================================================
    health = _system_health()

    return {
        'users': {
            'total': total_users,
            'landlords': total_landlords,
            'tenants': total_tenants,
            'admins': total_admins,
            'active_landlords': active_landlords,
            'suspended_landlords': suspended_landlords,
            'active_tenants': active_tenants,
            'suspended_tenants': suspended_tenants,
        },
        'properties': {
            'total': total_properties,
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
            'future': future_leases,
        },
        'collected_rent': {
            'total': str(total_revenue),
            'payment_count': total_payments_count,
            'period_total': str(period_revenue),
            'period_payments': period_payments_count,
            'previous_total': str(previous_revenue),
            'previous_payments': previous_payments_count,
            'rent_growth': revenue_growth,
        },
        'outstanding_rent': {
            'total': str(outstanding_total),
            'period_count': outstanding_count,
        },
        'overdue_rent': {
            'total': str(overdue_total),
            'period_count': overdue_count,
        },
        'subscriptions': {
            'total': total_subscriptions,
            'active': active_subscriptions,
            'trial': trial_subscriptions,
            'cancelled': cancelled_subscriptions,
            'past_due': past_due_subscriptions,
            'expired': expired_subscriptions,
            'free': free_count,
            'professional': professional_count,
            'business': business_count,
        },
        'growth_trends': growth_trends,
        'system_health': health,
    }


def _compute_growth_trends(since_date):
    """Compute 12-month growth trends for users, properties, units, leases, payments.

    Returns monthly aggregated counts grouped by month.
    Uses database-level TruncMonth for efficiency.
    """
    # User growth by role and month
    landlord_growth = list(
        User.objects.filter(
            role=Role.LANDLORD,
            created_at__date__gte=since_date,
        ).annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )

    tenant_growth = list(
        User.objects.filter(
            role=Role.TENANT,
            created_at__date__gte=since_date,
        ).annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )

    # Property growth
    property_growth = list(
        Property.objects.filter(
            created_at__date__gte=since_date,
        ).annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )

    # Unit growth
    unit_growth = list(
        Unit.objects.filter(
            created_at__date__gte=since_date,
        ).annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )

    # Lease growth
    lease_growth = list(
        Lease.objects.filter(
            created_at__date__gte=since_date,
        ).annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )

    # Payment volume growth (PAID only)
    payment_growth = list(
        Payment.objects.filter(
            status=PaymentStatus.PAID,
            created_at__date__gte=since_date,
        ).annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(count=Count('id'), total=Sum('amount'))
        .order_by('month')
    )

    # Subscription growth
    subscription_growth = list(
        Subscription.objects.filter(
            created_at__date__gte=since_date,
        ).annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )

    # Serialize datetime to string for JSON
    def _serialize_monthly(items):
        return [
            {
                'month': item['month'].strftime('%Y-%m'),
                'count': item['count'],
                **({k: str(v) for k, v in item.items() if k not in ('month', 'count')}),
            }
            for item in items
        ]

    return {
        'landlords': _serialize_monthly(landlord_growth),
        'tenants': _serialize_monthly(tenant_growth),
        'properties': _serialize_monthly(property_growth),
        'units': _serialize_monthly(unit_growth),
        'leases': _serialize_monthly(lease_growth),
        'payments': _serialize_monthly(payment_growth),
        'subscriptions': _serialize_monthly(subscription_growth),
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
