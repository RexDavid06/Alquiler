"""Payment (rent) domain models.

MVP uses manual rent payment recording. Paystack is a future feature; the
schema keeps fields (gateway, reference) to extend toward that without
rewrite. Tenant rent payments are kept entirely separate from SaaS
subscription billing.

Payment.rent_period is the single source of truth linking a payment to a
rent obligation.  Rent-period status is derived from the aggregate of valid
payments -- never stored redundantly.
"""

from django.db import models


class PaymentMethod(models.TextChoices):
    BANK_TRANSFER = 'BANK_TRANSFER', 'Bank transfer'
    CASH = 'CASH', 'Cash'
    CARD = 'CARD', 'Card'
    OTHER = 'OTHER', 'Other'


class PaymentStatus(models.TextChoices):
    PAID = 'PAID', 'Paid'
    PENDING = 'PENDING', 'Pending'
    FAILED = 'FAILED', 'Failed'
    CANCELLED = 'CANCELLED', 'Cancelled'


class Payment(models.Model):
    """A single rent payment record, manually entered by the landlord."""

    landlord = models.ForeignKey(
        'core.User', on_delete=models.PROTECT, related_name='recorded_payments',
    )
    tenant = models.ForeignKey(
        'core.User', on_delete=models.PROTECT, related_name='rent_payments',
    )
    lease = models.ForeignKey(
        'leases.Lease', on_delete=models.PROTECT, related_name='payments',
    )
    rent_period = models.ForeignKey(
        'payments.RentSchedule', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='payments',
        help_text='The rent obligation this payment targets.',
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default='NGN')
    payment_date = models.DateField()
    payment_method = models.CharField(
        max_length=20, choices=PaymentMethod.choices,
        default=PaymentMethod.BANK_TRANSFER,
    )
    reference = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PAID,
    )

    # Future Paystack / gateway hooks (not used in MVP).
    gateway = models.CharField(max_length=40, blank=True)
    gateway_reference = models.CharField(max_length=200, blank=True)
    verified = models.BooleanField(default=False)

    recorded_by = models.ForeignKey(
        'core.User', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='payment_records',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-payment_date', '-created_at']
        indexes = [
            models.Index(fields=['landlord', 'payment_date']),
            models.Index(fields=['tenant', 'payment_date']),
            models.Index(fields=['lease', 'payment_date']),
            models.Index(fields=['rent_period', 'status']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(currency__regex=r'^[A-Z]{3}$'),
                name='payment_currency_iso3',
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gte=0),
                name='payment_amount_non_negative',
            ),
        ]

    def __str__(self):
        return f'{self.currency} {self.amount} by {self.tenant.email}'

    @property
    def is_paid(self):
        return self.status == PaymentStatus.PAID


class RentPeriodStatus(models.TextChoices):
    """Rent schedule period status.

    Derived entirely from payment records and due dates.  Never
    client-supplied.
    """

    UPCOMING = 'UPCOMING', 'Upcoming'
    DUE = 'DUE', 'Due today'
    PARTIALLY_PAID = 'PARTIALLY_PAID', 'Partially paid'
    PAID = 'PAID', 'Paid'
    OVERDUE = 'OVERDUE', 'Overdue'


class RentSchedule(models.Model):
    """One rent period for a lease.

    Rent is tracked separately from lease expiry.  Each row is a defined
    rent period (start/end/due date) for a fixed amount.  Outstanding
    balance and status are derived from Payment records that reference
    this period via Payment.rent_period.
    """

    lease = models.ForeignKey(
        'leases.Lease', on_delete=models.CASCADE, related_name='rent_schedule',
    )
    period_start = models.DateField()
    period_end = models.DateField()
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default='NGN')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['due_date']
        unique_together = [('lease', 'due_date')]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(period_end__gte=models.F('period_start')),
                name='rent_period_order',
            ),
            models.CheckConstraint(
                condition=models.Q(currency__regex=r'^[A-Z]{3}$'),
                name='rent_schedule_currency_iso3',
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gte=0),
                name='rent_schedule_amount_non_negative',
            ),
        ]

    def __str__(self):
        return f'Rent period {self.period_start}–{self.period_end} ({self.currency} {self.amount})'