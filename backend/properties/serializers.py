"""Serializers for Property and Unit resources."""

from rest_framework import serializers

from .models import Property, Unit


class PropertySerializer(serializers.ModelSerializer):
    landlord = serializers.PrimaryKeyRelatedField(read_only=True)
    landlord_name = serializers.CharField(source='landlord.full_name', read_only=True)
    unit_count = serializers.IntegerField(read_only=True)
    occupied_units = serializers.IntegerField(read_only=True)
    vacant_units = serializers.IntegerField(read_only=True)

    class Meta:
        model = Property
        fields = [
            'id', 'landlord', 'landlord_name', 'name', 'property_type', 'address',
            'city', 'state', 'country', 'description', 'currency', 'status',
            'unit_count', 'occupied_units', 'vacant_units',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'landlord', 'landlord_name', 'created_at', 'updated_at']

    def create(self, validated_data):
        # landlord is supplied by the view (always the authenticated user).
        property = Property(**validated_data)
        property.full_clean()
        property.save()
        return property

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.full_clean()
        instance.save()
        return instance


class UnitSerializer(serializers.ModelSerializer):
    property_name = serializers.CharField(source='property.name', read_only=True)
    property_address = serializers.CharField(source='property.address', read_only=True)
    # Occupancy is controlled by the lease lifecycle - read-only to clients.
    status = serializers.ChoiceField(choices=Unit.status.field.choices, read_only=True)

    class Meta:
        model = Unit
        fields = [
            'id', 'property', 'property_name', 'property_address', 'name',
            'description', 'status', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'property', 'status', 'created_at', 'updated_at']

    def _get_property(self):
        """The owning property is injected by the view (URL), never the body."""
        property = self.context.get('property')
        if property is None:
            raise serializers.ValidationError(
                'A valid property context is required.', code='property_required',
            )
        return property

    def validate_name(self, value):
        property = self._get_property()
        value = value.strip()
        qs = Unit.objects.filter(property=property, name__iexact=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                f'A unit named "{value}" already exists in this property.',
                code='duplicate_unit_name',
            )
        return value

    def create(self, validated_data):
        # The URL property always wins over anything in the payload/save
        # kwargs; it is the authenticated landlord's own property.
        property = self._get_property()
        validated_data['property'] = property
        unit = Unit(**validated_data)
        unit.full_clean()
        unit.save()
        return unit

    def update(self, instance, validated_data):
        validated_data.pop('property', None)  # property is not editable via body
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.full_clean()
        instance.save()
        return instance