import { useEffect, useState } from 'react';
import { Alert, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import { Picker } from '@react-native-picker/picker';

import { createLease } from '@/api/leases';
import { listProperties, listUnits } from '@/api/properties';
import { listTenants } from '@/api/tenants';
import { ApiRequestError } from '@/api/client';
import type { Property, TenantUser, Unit } from '@/api/types';
import { Button } from '@/components/ui/button';
import { Screen } from '@/components/ui/screen';
import { TextField } from '@/components/ui/text-field';
import { useTheme } from '@/hooks/use-theme';

export default function NewLeaseScreen() {
  const router = useRouter();
  const theme = useTheme();

  const [tenants, setTenants] = useState<TenantUser[]>([]);
  const [properties, setProperties] = useState<Property[]>([]);
  const [units, setUnits] = useState<Unit[]>([]);

  const [tenantId, setTenantId] = useState<number | ''>('');
  const [propertyId, setPropertyId] = useState<number | ''>('');
  const [unitId, setUnitId] = useState<number | ''>('');

  const [startDate, setStartDate] = useState('');
  const [expiryDate, setExpiryDate] = useState('');
  const [rentAmount, setRentAmount] = useState('');
  const [currency, setCurrency] = useState('NGN');
  const [rentFrequency, setRentFrequency] = useState<'MONTHLY' | 'QUARTERLY' | 'ANNUALLY'>(
    'MONTHLY',
  );
  const [rentDueDay, setRentDueDay] = useState('1');
  const [notes, setNotes] = useState('');

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void Promise.all([listTenants(), listProperties()])
      .then(([t, p]) => {
        setTenants(t.results);
        setProperties(p.results);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    setUnitId('');
    setUnits([]);
    if (propertyId === '') return;
    void listUnits(propertyId)
      .then((res) => {
        setUnits(res.results);
        setUnitId(res.results[0]?.id ?? '');
      })
      .catch(() => setUnits([]));
  }, [propertyId]);

  const onSubmit = async () => {
    if (tenantId === '' || propertyId === '' || unitId === '') {
      setError('Select a tenant, property and unit.');
      return;
    }
    if (!startDate || !expiryDate) {
      setError('Start and expiry dates are required.');
      return;
    }
    if (!rentAmount || Number.isNaN(Number(rentAmount))) {
      setError('Enter a valid rent amount.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const created = await createLease({
        tenant: tenantId,
        property: propertyId,
        unit: unitId,
        start_date: startDate,
        expiry_date: expiryDate,
        rent_amount: String(Number(rentAmount)),
        currency,
        rent_frequency: rentFrequency,
        rent_due_day: Number(rentDueDay) || 1,
        notes,
      });
      router.replace(`/(app)/leases/lease-detail?id=${created.id}`);
    } catch (err) {
      const msg = err instanceof ApiRequestError ? err.message : 'Unable to create lease.';
      setError(msg);
      Alert.alert('Failed', msg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Screen title="New Lease">
      {error ? <Text style={styles.error}>{error}</Text> : null}

      <PickerField
        label="Tenant *"
        value={tenantId}
        onChange={(v) => setTenantId(v === '' ? '' : Number(v))}
        placeholder="Select tenant…"
      >
        {tenants.map((t) => (
          <Picker.Item key={t.id} label={`${t.full_name} (${t.email})`} value={t.id} />
        ))}
      </PickerField>

      <PickerField
        label="Property *"
        value={propertyId}
        onChange={(v) => setPropertyId(v === '' ? '' : Number(v))}
        placeholder="Select property…"
      >
        {properties.map((p) => (
          <Picker.Item key={p.id} label={p.name} value={p.id} />
        ))}
      </PickerField>

      {propertyId !== '' ? (
        <PickerField
          label="Unit *"
          value={unitId}
          onChange={(v) => setUnitId(v === '' ? '' : Number(v))}
          placeholder="Select unit…"
        >
          {units.map((u) => (
            <Picker.Item key={u.id} label={u.name} value={u.id} />
          ))}
        </PickerField>
      ) : null}

      <TextField
        label="Start date *"
        value={startDate}
        onChangeText={setStartDate}
        placeholder="YYYY-MM-DD"
        autoCapitalize="none"
      />
      <TextField
        label="Expiry date *"
        value={expiryDate}
        onChangeText={setExpiryDate}
        placeholder="YYYY-MM-DD"
        autoCapitalize="none"
      />
      <TextField
        label="Rent amount *"
        value={rentAmount}
        onChangeText={setRentAmount}
        placeholder="300000"
        keyboardType="numeric"
      />
      <TextField label="Currency" value={currency} onChangeText={setCurrency} />

      <PickerField
        label="Rent frequency *"
        value={rentFrequency}
        onChange={(v) => setRentFrequency(v as 'MONTHLY' | 'QUARTERLY' | 'ANNUALLY')}
      >
        <Picker.Item label="Monthly" value="MONTHLY" />
        <Picker.Item label="Quarterly" value="QUARTERLY" />
        <Picker.Item label="Annually" value="ANNUALLY" />
      </PickerField>

      <TextField
        label="Rent due day of month *"
        value={rentDueDay}
        onChangeText={setRentDueDay}
        placeholder="1"
        keyboardType="numeric"
      />
      <TextField label="Notes" value={notes} onChangeText={setNotes} multiline />

      <Button title="Create lease" onPress={onSubmit} loading={saving} />
    </Screen>
  );
}

function PickerField({
  label,
  value,
  onChange,
  placeholder,
  children,
}: {
  label: string;
  value: number | string;
  onChange: (v: number | string) => void;
  placeholder?: string;
  children: React.ReactNode;
}) {
  const theme = useTheme();
  return (
    <View style={styles.field}>
      <Text style={[styles.label, { color: theme.textSecondary }]}>{label}</Text>
      <Picker
        selectedValue={value}
        onValueChange={(v) => onChange(v)}
        style={[styles.picker, { color: theme.text }]}
      >
        {placeholder ? <Picker.Item label={placeholder} value="" /> : null}
        {children}
      </Picker>
    </View>
  );
}

const styles = StyleSheet.create({
  error: { color: '#d32f2f', fontSize: 14 },
  field: { gap: 4 },
  label: { fontSize: 13, fontWeight: '600' },
  picker: { height: 60, fontSize: 16 },
});