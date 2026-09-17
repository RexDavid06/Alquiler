import { useCallback, useState } from 'react';
import { Alert, StyleSheet, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Picker } from '@react-native-picker/picker';

import { getLease, renewLease } from '@/api/leases';
import { ApiRequestError } from '@/api/client';
import type { LeaseDetail, RentFrequency } from '@/api/types';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { ErrorState, LoadingState, Screen } from '@/components/ui/screen';
import { TextField } from '@/components/ui/text-field';
import { useTheme } from '@/hooks/use-theme';

function nextDay(iso: string): string {
  const d = new Date(`${iso.slice(0, 10)}T00:00:00`);
  d.setDate(d.getDate() + 1);
  return d.toISOString().slice(0, 10);
}

export default function RenewLeaseScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const leaseId = Number(id);
  const router = useRouter();
  const theme = useTheme();

  const [lease, setLease] = useState<LeaseDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [startDate, setStartDate] = useState('');
  const [expiryDate, setExpiryDate] = useState('');
  const [rentAmount, setRentAmount] = useState('');
  const [currency, setCurrency] = useState('NGN');
  const [rentFrequency, setRentFrequency] = useState<RentFrequency>('MONTHLY');
  const [rentDueDay, setRentDueDay] = useState('1');
  const [notes, setNotes] = useState('');

  const [saving, setSaving] = useState(false);
  const [savedId, setSavedId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await getLease(leaseId);
      setLease(data);
      setStartDate(nextDay(data.expiry_date));
      setExpiryDate('');
      setRentAmount(String(Number(data.rent_amount)));
      setCurrency(data.currency);
      setRentFrequency(data.rent_frequency);
      setRentDueDay(String(data.rent_due_day));
      setNotes(data.notes);
    } catch (err) {
      if (err instanceof ApiRequestError) setError(err.message);
      else setError('Unable to load lease.');
    } finally {
      setLoading(false);
    }
  }, [leaseId]);

  if (loading) return <LoadingState />;
  if (error && !lease) return <ErrorState message={error} onRetry={() => void load()} />;
  if (!lease) return null;

  const onSubmit = async () => {
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
      const renewed = await renewLease(lease.id, {
        start_date: startDate,
        expiry_date: expiryDate,
        rent_amount: String(Number(rentAmount)),
        currency,
        rent_frequency: rentFrequency,
        rent_due_day: Number(rentDueDay) || 1,
        notes,
      });
      setSavedId(renewed.id);
      Alert.alert('Lease renewed', `New lease #${renewed.id} created.`, [
        { text: 'OK', onPress: () => router.replace(`/(app)/leases/lease-detail?id=${renewed.id}`) },
      ]);
    } catch (err) {
      const msg = err instanceof ApiRequestError ? err.message : 'Unable to renew lease.';
      setError(msg);
      Alert.alert('Failed', msg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Screen title="Renew Lease" subtitle={`Extend tenancy for #${lease.id}`}>
      {error ? <Text style={styles.error}>{error}</Text> : null}

      <Card>
        <Text style={[styles.summaryLabel, { color: theme.textSecondary }]}>Tenant</Text>
        <Text style={[styles.summaryValue, { color: theme.text }]}>{lease.tenant_name}</Text>
        <Text style={[styles.summaryLabel, { color: theme.textSecondary }]}>Unit</Text>
        <Text style={[styles.summaryValue, { color: theme.text }]}>
          {lease.property_name} – {lease.unit_name}
        </Text>
        <Text style={[styles.summaryLabel, { color: theme.textSecondary }]}>Previous period</Text>
        <Text style={[styles.summaryValue, { color: theme.text }]}>
          {lease.start_date.slice(0, 10)} → {lease.expiry_date.slice(0, 10)}
        </Text>
      </Card>

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

      <View style={styles.field}>
        <Text style={[styles.label, { color: theme.textSecondary }]}>Rent frequency *</Text>
        <Picker
          selectedValue={rentFrequency}
          onValueChange={(v) => setRentFrequency(v as RentFrequency)}
          style={[styles.picker, { color: theme.text }]}
        >
          <Picker.Item label="Monthly" value="MONTHLY" />
          <Picker.Item label="Quarterly" value="QUARTERLY" />
          <Picker.Item label="Annually" value="ANNUALLY" />
        </Picker>
      </View>

      <TextField
        label="Rent due day of month *"
        value={rentDueDay}
        onChangeText={setRentDueDay}
        placeholder="1"
        keyboardType="numeric"
      />
      <TextField label="Notes" value={notes} onChangeText={setNotes} multiline />

      <Button title="Renew lease" onPress={onSubmit} loading={saving || savedId !== null} />
    </Screen>
  );
}

const styles = StyleSheet.create({
  error: { color: '#d32f2f', fontSize: 14 },
  field: { gap: 4 },
  label: { fontSize: 13, fontWeight: '600' },
  picker: { height: 60, fontSize: 16 },
  summaryLabel: { fontSize: 12, fontWeight: '600', marginTop: 2 },
  summaryValue: { fontSize: 15, fontWeight: '700' },
});