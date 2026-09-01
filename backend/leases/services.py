"""Lease domain services.

Encapsulates the transactional business rules around lease lifecycle:
conflict-free unit occupancy, status transitions, renewal, and termination.
These rules are enforced on the backend (never trusted to the frontend).
"""

from django.db import transaction
from django.utils import timezone
from datetime import date

from core.exceptions import ConflictError, DomainError

from properties.models import Unit, UnitStatus

from .models import Lease, LeaseStatus


def _as_date(value, field):
    """Normalize a date-like input (date/str/datetime) to a date object."""
    if isinstance(value, date):
        return value
    if hasattr(value, 'date'):  # datetime
        return value.date()
    if isinstance(value, str):
        from django.utils.dateparse import parse_date
        parsed = parse_date(value)
        if parsed is None:
            raise DomainError(f'Invalid date for {field}: {value!r}.')
        return parsed
    raise DomainError(f'Invalid date for {field}.')


def _overlaps(existing_start, existing_end, start, end):
    """True if the date ranges overlap or touch on the same day."""
    return not (end < existing_start or start > existing_end)


def has_conflicting_active_lease(unit, start_date, expiry_date, exclude_lease=None):
    """Return the conflicting lease on a unit, if any.

    Live leases (FUTURE, ACTIVE and EXPIRING) all block new occupation of an
    overlapping period: a future booking reserves the unit even before it
    starts. Historical EXPIRED and TERMINATED leases never conflict. Renewal
    must not create an overlapping live lease, so this considers date overlap.
    """
    qs = Lease.objects.filter(
        unit=unit,
        status__in=[
            LeaseStatus.FUTURE, LeaseStatus.ACTIVE, LeaseStatus.EXPIRING,
        ],
    )
    if exclude_lease is not None:
        qs = qs.exclude(pk=exclude_lease.pk)
    for existing in qs:
        if _overlaps(existing.start_date, existing.expiry_date,
                     start_date, expiry_date):
            return existing
    return None


@transaction.atomic
def update_lease(lease, *, start_date=None, expiry_date=None, rent_amount=None,
                 currency=None, rent_frequency=None, rent_due_day=None,
                 notes=None):
    """Edit a lease that has not started yet (FUTURE).

    Once a lease is ACTIVE/EXPIRING/EXPIRED/TERMINATED its dates and rent
    terms are immutable so that historical integrity and the rent schedule
    are never corrupted. Editable fields are re-validated exactly like
    creation (dates, currency, due day, unit conflicts) and the rent schedule
    is regenerated from the updated terms.
    """
    if lease.status != LeaseStatus.FUTURE:
        raise DomainError(
            'Only a future (not yet started) lease can be edited. '
            'Active and historical leases are immutable.',
            code='lease_not_editable',
        )

    new_start = start_date if start_date is not None else lease.start_date
    new_expiry = expiry_date if expiry_date is not None else lease.expiry_date
    new_start = _as_date(new_start, 'start_date')
    new_expiry = _as_date(new_expiry, 'expiry_date')
    if new_expiry < new_start:
        raise DomainError('Lease expiry cannot be before its start date.')

    if start_date is not None or expiry_date is not None:
        assert_unit_available(
            lease.unit, new_start, new_expiry, exclude_lease=lease,
        )

    if start_date is not None:
        lease.start_date = new_start
    if expiry_date is not None:
        lease.expiry_date = new_expiry
    if rent_amount is not None:
        lease.rent_amount = rent_amount
    if currency is not None:
        lease.currency = currency
    if rent_frequency is not None:
        lease.rent_frequency = rent_frequency
    if rent_due_day is not None:
        lease.rent_due_day = rent_due_day
    if notes is not None:
        lease.notes = notes

    lease.full_clean()  # CheckConstraints: dates, ISO-3 currency, due-day range
    lease.save()

    # The stored status may change (e.g. start_date now reached).
    lease.refresh_status()
    _sync_unit_occupancy(lease)

    # Regenerate the rent schedule from the updated terms (the schedule holds
    # no period->payment links yet because only FUTURE leases are editable).
    from payments.services import generate_schedule
    lease.rent_schedule.all().delete()
    generate_schedule(lease)
    return lease


def unit_has_active_tenancy(unit):
    """True if the unit currently has an ACTIVE or EXPIRING tenancy.

    Read-only occupancy helper shared by other domain apps (e.g. tenants
    rejection of invitations to occupied units). Does not modify lease state.
    """
    return Lease.objects.filter(
        unit=unit,
        status__in=[LeaseStatus.ACTIVE, LeaseStatus.EXPIRING],
    ).exists()


def assert_unit_available(unit, start_date, expiry_date, exclude_lease=None):
    """Raise if the unit already has an overlapping active/expiring lease."""
    conflicting = has_conflicting_active_lease(
        unit, start_date, expiry_date, exclude_lease=exclude_lease,
    )
    if conflicting is not None:
        raise ConflictError(
            f'Unit "{unit.name}" already has an active tenancy '
            f'({conflicting.tenant.full_name}, '
            f'{conflicting.start_date}–{conflicting.expiry_date}) in that period.',
            code='unit_has_conflicting_lease',
        )


@transaction.atomic
def create_lease(*, landlord, tenant, property, unit, start_date, expiry_date,
                 rent_amount, currency, rent_frequency, rent_due_day=1,
                 notes='', previous_lease=None):
    """Create a lease after validating unit availability and schedule rent."""
    start_date = _as_date(start_date, 'start_date')
    expiry_date = _as_date(expiry_date, 'expiry_date')
    if expiry_date < start_date:
        raise DomainError('Lease expiry cannot be before its start date.')
    assert_unit_available(unit, start_date, expiry_date)

    lease = Lease.objects.create(
        landlord=landlord,
        tenant=tenant,
        property=property,
        unit=unit,
        start_date=start_date,
        expiry_date=expiry_date,
        rent_amount=rent_amount,
        currency=currency,
        rent_frequency=rent_frequency,
        rent_due_day=rent_due_day,
        notes=notes,
        previous_lease=previous_lease,
    )
    lease.refresh_status()
    _sync_unit_occupancy(lease)
    # Generate the rent schedule for this lease.
    from payments.services import generate_schedule
    generate_schedule(lease)
    return lease


@transaction.atomic
def renew_lease(previous_lease, *, start_date, expiry_date, rent_amount,
                currency, rent_frequency, rent_due_day=1, notes=''):
    """Create a new lease that continues a previous tenancy.

    The previous lease is preserved as history; the new lease is linked via
    previous_lease. Renewal refuses to overlap an active tenancy on the unit.
    """
    # A renewal may start immediately after the previous lease; if the
    # previous lease is still ACTIVE/EXPIRING and the new period overlaps, it
    # is disallowed. Termination of the prior lease happens via explicit
    # `terminate_lease`.
    start_date = _as_date(start_date, 'start_date')
    expiry_date = _as_date(expiry_date, 'expiry_date')
    assert_unit_available(
        previous_lease.unit, start_date, expiry_date,
    )
    new_lease = create_lease(
        landlord=previous_lease.landlord,
        tenant=previous_lease.tenant,
        property=previous_lease.property,
        unit=previous_lease.unit,
        start_date=start_date,
        expiry_date=expiry_date,
        rent_amount=rent_amount,
        currency=currency,
        rent_frequency=rent_frequency,
        rent_due_day=rent_due_day,
        notes=notes,
        previous_lease=previous_lease,
    )
    return new_lease


@transaction.atomic
def terminate_lease(lease, at=None):
    """Terminate a tenancy: mark the lease TERMINATED and free the unit."""
    if lease.status == LeaseStatus.TERMINATED:
        raise DomainError('This lease is already terminated.')
    lease.status = LeaseStatus.TERMINATED
    lease.terminated_at = at or timezone.now()
    lease.save(update_fields=['status', 'terminated_at', 'updated_at'])
    _sync_unit_occupancy(lease)
    return lease


def lease_history(lease):
    """Return the tenancy's full lease chain, oldest first, including `lease`.

    Walks `previous_lease` links down to the root tenancy. Chains are
    terminal (SET_NULL) so a deleted predecessor simply ends the walk;
    a visited set guards against corrupt cycles.
    """
    chain = []
    current = lease
    visited = set()
    while current is not None and current.pk not in visited:
        visited.add(current.pk)
        chain.append(current)
        previous = current.previous_lease_id
        if previous is None:
            break
        current = (Lease.objects.filter(pk=previous).select_related(
            'landlord', 'tenant', 'property', 'unit',
        ).first())
    chain.reverse()
    return chain


def _sync_unit_occupancy(lease):
    """Reconcile the unit's VACANT/OCCUPIED status against its leases.

    A unit is OCCUPIED if it has any ACTIVE or EXPIRING lease; otherwise it
    is VACANT. Runs within the lease transaction so partial failures never
    leave an inconsistent occupancy state.
    """
    unit = lease.unit
    active = Lease.objects.filter(
        unit=unit,
        status__in=[LeaseStatus.ACTIVE, LeaseStatus.EXPIRING],
    ).exists()
    unit.set_status(UnitStatus.OCCUPIED if active else UnitStatus.VACANT)
