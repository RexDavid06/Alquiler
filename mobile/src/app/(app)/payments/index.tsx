import { useCallback, useState } from 'react';
import { Alert, FlatList, RefreshControl, StyleSheet, Text, View } from 'react-native';
import { Link, useFocusEffect } from 'expo-router';

import { listPayments } from '@/api/payments';
import { ApiRequestError } from '@/api/client';
import type { Payment } from '@/api/types';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { EmptyState, ErrorState, LoadingState, Screen } from '@/components/ui/screen';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

export default function PaymentsScreen() {
  const theme = useTheme();
  const [payments, setPayments] = useState<Payment[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await listPayments();
      setPayments(res.results);
    } catch (err) {
      if (err instanceof ApiRequestError) setError(err.message);
      else setError('Unable to load payments.');
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  if (loading) return <LoadingState />;
  if (error && payments.length === 0) {
    return <ErrorState message={error} onRetry={() => void load()} />;
  }

  return (
    <Screen
      title="Payments"
      scroll={false}
      headerRight={
        <Link href="/(app)/payments/record-payment" asChild>
          <Button title="Record" variant="ghost" onPress={() => {}} />
        </Link>
      }
    >
      <FlatList
        data={payments}
        keyExtractor={(item) => String(item.id)}
        contentContainerStyle={styles.list}
        renderItem={({ item }) => <PaymentRow payment={item} />}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={theme.primary} />
        }
        ListEmptyComponent={
          <EmptyState
            title="No payments yet"
            message="Tap “Record” to log the first rent payment."
          />
        }
      />
    </Screen>
  );
}

function PaymentRow({ payment }: { payment: Payment }) {
  const theme = useTheme();
  const statusColor =
    payment.status === 'PAID'
      ? theme.success
      : payment.status === 'CANCELLED' || payment.status === 'FAILED'
      ? theme.danger
      : theme.warning;

  return (
    <Link href={`/(app)/payments/record-payment?id=${payment.id}`} asChild>
      <Card>
        <View style={styles.rowHeader}>
          <Text style={[styles.amount, { color: theme.text }]}>
            ₦{Number(payment.amount).toLocaleString()}
          </Text>
          <Text style={[styles.status, { color: statusColor }]}>{payment.status}</Text>
        </View>
        <Text style={[styles.meta, { color: theme.textSecondary }]}>
          {payment.notes || `Rent payment #${payment.id}`}
        </Text>
        <Text style={[styles.meta, { color: theme.textSecondary }]}>
          {payment.payment_date.slice(0, 10)} · {payment.payment_method}
        </Text>
        <Text style={[styles.meta, { color: theme.textSecondary }]}>
          Ref: {payment.reference || '—'}
        </Text>
      </Card>
    </Link>
  );
}

const styles = StyleSheet.create({
  list: {
    padding: Spacing.three,
    gap: Spacing.two,
  },
  rowHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: Spacing.half,
  },
  amount: { fontSize: 18, fontWeight: '800' },
  status: { fontSize: 13, fontWeight: '700' },
  meta: { fontSize: 14 },
});