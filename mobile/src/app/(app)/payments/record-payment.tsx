import { useCallback, useEffect, useState } from 'react';
import { Alert, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Picker } from '@react-native-picker/picker';

import { cancelPayment, createPayment, getPayment, listRentSchedules } from '@/api/payments';
import { listLeases } from '@/api/leases';
import { listTenants } from '@/api/tenants';
import { ApiRequestError } from '@/api/client';
import type { Lease, Payment, RentScheduleItem, TenantUser } from '@/api/types';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { ErrorState, LoadingState, Screen } from '@/components/ui/screen';
import { TextField } from '@/components/ui/text-field';
import { useTheme } from '@/hooks/use-theme';

export default function RecordPaymentScreen() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const existingId = id ? Number(id) : null;

  if (existingId) {
    return <ExistingPayment paymentId={existingId} />;
  }
  return <NewPaymentForm />;
}

function ExistingPayment({ paymentId }: { paymentId: number }) {
  const theme = useTheme();
  const [payment, setPayment] = useState<Payment | null>(null);
  const [loading, setLoading] = useState(true);
  const [cancelling, setCancelling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setPayment(await getPayment(paymentId));
    } catch (err) {
      if (err instanceof ApiRequestError) setError(err.message);
      else setError('Unable to load payment.');
    } finally {
      setLoading(false);
    }
  }, [paymentId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <LoadingState />;
  if (error && !payment) return <ErrorState message={error} onRetry={() => void load()} />;
  if (!payment) return null;

  const onCancel = () => {
    Alert.alert('Cancel payment', 'Cancel this payment record?', [
      { text: 'No', style: 'cancel' },
      {
        text: 'Cancel payment',
        style: 'destructive',
        onPress: async () => {
          setCancelling(true);
          try {
            await cancelPayment(payment.id);
            Alert.alert('Done', 'Payment cancelled.');
            await load();
          } catch (err) {
            const msg = err instanceof ApiRequestError ? err.message : 'Unable to cancel payment.';
            Alert.alert('Failed', msg);
          } finally {
            setCancelling(false);
          }
        },
      },
    ]);
  };

  return (
    <Screen title={`Payment #${payment.id}`}>
      <Card>
        <Text style={[styles.kv, { color: theme.text }]}>
          Amount: <Text style={{ color: theme.primary }}>₦{Number(payment.amount).toLocaleString()}</Text>
        </Text>
        <Text style={[styles.kv, { color: theme.textSecondary }]}>Status: {payment.status}</Text>
        <Text style={[styles.kv, { color: theme.textSecondary }]}>
          Date: {payment.payment_date.slice(0, 10)}
        </Text>
        <Text style={[styles.kv, { color: theme.textSecondary }]}>
          Method: {payment.payment_method}
        </Text>
        <Text style={[styles.kv, { color: theme.textSecondary }]}>
          Reference: {payment.reference || '—'}
        </Text>
        {payment.notes ? (
          <Text style={[styles.kv, { color: theme.textSecondary }]}>Notes: {payment.notes}</Text>
        ) : null}
        {payment.verified ? (
          <Text style={[styles.kv, { color: theme.success }]}>Verified by gateway</Text>
        ) : null}
      </Card>
      {payment.status !== 'CANCELLED' ? (
        <Button title="Cancel payment" variant="danger" onPress={onCancel} loading={cancelling} />
      ) : null}
    </Screen>
  );
}

function NewPaymentForm() {
  const router = useRouter();
  const theme = useTheme();

  const [tenants, setTenants] = useState<TenantUser[]>([]);
  const [leases, setLeases] = useState<Lease[]>([]);
  const [schedules, setSchedules] = useState<RentScheduleItem[]>([]);

  const [tenantId, setTenantId] = useState<number | ''>('');
  const [leaseId, setLeaseId] = useState<number | ''>('');
  const [periodId, setPeriodId] = useState<number | ''>('');
  const [amount, setAmount] = useState('');
  const [currency, setCurrency] = useState('NGN');
  const [paymentDate, setPaymentDate] = useState('');
  const [paymentMethod, setPaymentMethod] = useState('BANK_TRANSFER');
  const [reference, setReference] = useState('');
  const [notes, setNotes] = useState('');

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void listTenants()
      .then((r) => setTenants(r.results))
      .catch(() => {});
  }, []);

  const loadLeases = useCallback(async (tenantId: number) => {
    setLeaseId('');
    setPeriodId('');
    setSchedules([]);
    try {
      const r = await listLeases();
      setLeases(r.results.filter((l) => l.tenant === tenantId && l.status === 'ACTIVE'));
    } catch {
      setLeases([]);
    }
  }, []);

  const loadSchedules = useCallback(async (leaseId: number) => {
    setPeriodId('');
    setSchedules([]);
    try {
      const r = await listRentSchedules({ lease: leaseId });
      setSchedules(r.results);
    } catch {
      setSchedules([]);
    }
  }, []);

  const onSubmit = async () => {
    if (tenantId === '' || leaseId === '') {
      setError('Select a tenant and their active lease.');
      return;
    }
    if (!amount || Number.isNaN(Number(amount))) {
      setError('Enter a valid amount.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const key =
        typeof crypto !== 'undefined' && 'randomUUID' in crypto
          ? crypto.randomUUID()
          : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
      await createPayment(
        {
          tenant: tenantId,
          lease: leaseId,
          rent_period: periodId === '' ? null : periodId,
          amount: String(Number(amount)),
          currency,
          payment_date: paymentDate || new Date().toISOString().slice(0, 10),
          payment_method: paymentMethod,
          reference,
          notes,
          status: 'PAID',
        },
        key,
      );
      Alert.alert('Recorded', 'Payment recorded successfully.', [
        { text: 'OK', onPress: () => router.replace('/(app)/payments') },
      ]);
    } catch (err) {
      const msg = err instanceof ApiRequestError ? err.message : 'Unable to record payment.';
      setError(msg);
      Alert.alert('Failed', msg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Screen title="Record Payment">
      {error ? <Text style={styles.error}>{error}</Text> : null}

      <View style={styles.field}>
        <Text style={[styles.label, { color: theme.textSecondary }]}>Tenant *</Text>
        <Picker
          selectedValue={tenantId}
          onValueChange={(v) => {
            setTenantId(v);
            if (v !== '') void loadLeases(Number(v));
          }}
          style={[styles.picker, { color: theme.text }]}
        >
          <Picker.Item label="Select tenant…" value="" />
          {tenants.map((t) => (
            <Picker.Item key={t.id} label={t.full_name} value={t.id} />
          ))}
        </Picker>
      </View>

      {tenantId !== '' ? (
        <View style={styles.field}>
          <Text style={[styles.label, { color: theme.textSecondary }]}>Lease *</Text>
          <Picker
            selectedValue={leaseId}
            onValueChange={(v) => {
              setLeaseId(v);
              if (v !== '') void loadSchedules(Number(v));
            }}
            style={[styles.picker, { color: theme.text }]}
          >
            <Picker.Item label="Select lease…" value="" />
            {leases.map((l) => (
              <Picker.Item
                key={l.id}
                label={`#${l.id} ${l.property_name} – ${l.unit_name}`}
                value={l.id}
              />
            ))}
          </Picker>
          {leases.length === 0 ? (
            <Text style={{ color: theme.textSecondary }}>
              No active leases for this tenant.
            </Text>
          ) : null}
        </View>
      ) : null}

      {leaseId !== '' ? (
        <View style={styles.field}>
          <Text style={[styles.label, { color: theme.textSecondary }]}>Rent period (optional)</Text>
          <Picker
            selectedValue={periodId}
            onValueChange={setPeriodId}
            style={[styles.picker, { color: theme.text }]}
          >
            <Picker.Item label="Auto-match to period…" value="" />
            {schedules.map((s) => (
              <Picker.Item
                key={s.id}
                label={`${s.period_start.slice(0, 10)} (₦${Number(s.amount).toLocaleString()}, ${s.status})`}
                value={s.id}
              />
            ))}
          </Picker>
        </View>
      ) : null}

      <TextField
        label="Amount *"
        value={amount}
        onChangeText={setAmount}
        placeholder="300000"
        keyboardType="numeric"
      />
      <TextField label="Currency" value={currency} onChangeText={setCurrency} />
      <TextField
        label="Payment date"
        value={paymentDate}
        onChangeText={setPaymentDate}
        placeholder="YYYY-MM-DD (default today)"
        autoCapitalize="none"
      />

      <View style={styles.field}>
        <Text style={[styles.label, { color: theme.textSecondary }]}>Method</Text>
        <Picker
          selectedValue={paymentMethod}
          onValueChange={setPaymentMethod}
          style={[styles.picker, { color: theme.text }]}
        >
          <Picker.Item label="Bank transfer" value="BANK_TRANSFER" />
          <Picker.Item label="Cash" value="CASH" />
          <Picker.Item label="Card" value="CARD" />
          <Picker.Item label="Other" value="OTHER" />
        </Picker>
      </View>

      <TextField label="Reference" value={reference} onChangeText={setReference} autoCapitalize="none" />
      <TextField label="Notes" value={notes} onChangeText={setNotes} multiline />

      <Button title="Record payment" onPress={onSubmit} loading={saving} />
    </Screen>
  );
}

const styles = StyleSheet.create({
  error: { color: '#d32f2f', fontSize: 14 },
  field: { gap: 4 },
  label: { fontSize: 13, fontWeight: '600' },
  picker: { height: 60, fontSize: 16 },
  kv: { fontSize: 14, marginBottom: 6 },
});