"""Property and Unit domain models.

A landlord (platform customer) can own multiple properties; each property can
contain multiple units. Data isolation is enforced by scoping every query to
the authenticated landlord.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class PropertyType(models.TextChoices):
    APARTMENT = 'APARTMENT', 'Apartment'
    HOUSE = 'HOUSE', 'House'
    DUPLEX = 'DUPLEX', 'Duplex'
    SHOP = 'SHOP', 'Shop'
    OFFICE = 'OFFICE', 'Office'
    WAREHOUSE = 'WAREHOUSE', 'Warehouse'
    OTHER = 'OTHER', 'Other'


class PropertyStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Active'
    ARCHIVED = 'ARCHIVED', 'Archived'


class UnitStatus(models.TextChoices):
    VACANT = 'VACANT', 'Vacant'
    OCCUPIED = 'OCCUPIED', 'Occupied'


class Property(models.Model):
    landlord = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='properties', limit_choices_to={'role': 'LANDLORD'},
    )
    name = models.CharField(max_length=200)
    property_type = models.CharField(
        max_length=20, choices=PropertyType.choices, default=PropertyType.APARTMENT,
    )
    address = models.CharField(max_length=300)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default='Nigeria')
    description = models.TextField(blank=True)
    currency = models.CharField(max_length=3, default='NGN')
    status = models.CharField(
        max_length=20, choices=PropertyStatus.choices, default=PropertyStatus.ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['landlord', 'status']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(currency__regex=r'^[A-Z]{3}$'),
                name='property_currency_iso3',
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def unit_count(self):
        return self.units.count()

    @property
    def vacant_units(self):
        return self.units.filter(status=UnitStatus.VACANT).count()

    @property
    def occupied_units(self):
        return self.units.filter(status=UnitStatus.OCCUPIED).count()


class Unit(models.Model):
    property = models.ForeignKey(
        Property, on_delete=models.CASCADE, related_name='units',
    )
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=UnitStatus.choices, default=UnitStatus.VACANT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['property', 'name']
        unique_together = [('property', 'name')]
        indexes = [
            models.Index(fields=['property', 'status']),
        ]

    def __str__(self):
        return f'{self.property.name} — {self.name}'

    def set_status(self, status):
        self.status = status
        self.save(update_fields=['status', 'updated_at'])
