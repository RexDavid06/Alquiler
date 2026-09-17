import { useCallback, useState } from 'react';
import { Alert, FlatList, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Link, useLocalSearchParams } from 'expo-router';

import { getLease, terminateLease } from '@/api/leases';
import { ApiRequestError } from '@/api/client';
import type { LeaseDetail, RentScheduleItem } from '@/api/types';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { ErrorState, LoadingState, Screen } from '@/components/ui/screen';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

export default function LeaseDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const leaseId = Number(id);
  const theme = useTheme();

  const [lease, setLease] = useState<LeaseDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [terminating, setTerminating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setLease(await getLease(leaseId));
    } catch (err) {
      if (err instanceof ApiRequestError) setError(err.message);
      else setError('Unable to load lease.');
    } finally {
      setLoading(false);
    }
  }, [leaseId]);

  const onTerminate = () => {
    if (!lease || lease.status !== 'ACTIVE') return;
    Alert.alert('Terminate lease', `End the lease for ${lease.tenant_name}?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Terminate',
        style: 'destructive',
        onPress: async () => {
          setTerminating(true);
          try {
            await terminateLease(lease.id);
            Alert.alert('Done', 'Lease terminated.');
            await load();
          } catch (err) {
            const msg =
              err instanceof ApiRequestError ? err.message : 'Unable to terminate lease.';
            Alert.alert('Failed', msg);
          } finally {
            setTerminating(false);
          }
        },
      },
    ]);
  };

  if (loading) return <LoadingState />;
  if (error && !lease) return <ErrorState message={error} onRetry={() => void load()} />;
  if (!lease) return null;

  const statusColor =
    lease.status === 'ACTIVE'
      ? theme.success
      : lease.status === 'EXPIRED' || lease.status === 'TERMINATED'
      ? theme.textSecondary
      : lease.status === 'EXPIRING'
      ? theme.warning
      : theme.text;

  return (
    <Screen title="Lease" subtitle={`#${lease.id}`} scroll={false}>
      <ScrollView style={{ flex: 1 }} contentContainerStyle={styles.content}>
        <Card>
          <View style={styles.rowHeader}>
            <Text style={[styles.tenant, { color: theme.text }]}>{lease.tenant_name}</Text>
            <Text style={[styles.status, { color: statusColor }]}>{lease.status}</Text>
          </View>
          <Text style={[styles.meta, { color: theme.textSecondary }]}>{lease.tenant_email}</Text>
          <Text style={[styles.meta, { color: theme.textSecondary }]}>
            {lease.property_name} – {lease.unit_name}
          </Text>
          <Text style={[styles.meta, { color: theme.text }]}>
            ₦{Number(lease.rent_amount).toLocaleString()} / {lease.rent_frequency.toLowerCase()}
          </Text>
          <Text style={[styles.meta, { color: theme.textSecondary }]}>
            {lease.start_date.slice(0, 10)} → {lease.expiry_date.slice(0, 10)}
          </Text>
          {lease.notes ? (
            <Text style={[styles.meta, { color: theme.textSecondary }]}>Notes: {lease.notes}</Text>
          ) : null}
        </Card>

        {lease.status === 'ACTIVE' ? (
          <Button
            title="Terminate lease"
            variant="danger"
            onPress={onTerminate}
            loading={terminating}
          />
        ) : null}

        {lease.status === 'ACTIVE' || lease.status === 'EXPIRING' || lease.status === 'EXPIRED' ? (
          <Link href={`/(app)/leases/renew-lease?id=${lease.id}`} asChild>
            <Button title="Renew lease" variant="secondary" onPress={() => {}} />
          </Link>
        ) : null}

        <Text style={[styles.sectionTitle, { color: theme.text }]}>Rent schedule</Text>
        {lease.rent_schedule.length === 0 ? (
          <Card>
            <Text style={{ color: theme.textSecondary }}>No rent periods generated.</Text>
          </Card>
        ) : (
          <FlatList
            scrollEnabled={false}
            data={lease.rent_schedule}
            keyExtractor={(item) => String(item.id)}
            renderItem={({ item }) => <ScheduleRow item={item} />}
          />
        )}
      </ScrollView>
    </Screen>
  );
}

function ScheduleRow({ item }: { item: RentScheduleItem }) {
  const theme = useTheme();
  return (
    <Card>
      <View style={styles.rowHeader}>
        <Text style={[styles.scheduleTitle, { color: theme.text }]}>
          {item.period_start.slice(0, 10)} → {item.period_end.slice(0, 10)}
        </Text>
        <Text style={[styles.status, { color: theme.textSecondary }]}>{item.status}</Text>
      </View>
      <Text style={[styles.meta, { color: theme.text }]}>
        ₦{Number(item.amount).toLocaleString()}
      </Text>
      <Text style={[styles.meta, { color: theme.textSecondary }]}>
        Due {item.due_date.slice(0, 10)} · Paid ₦{Number(item.paid_amount).toLocaleString()} ·
        Remaining ₦{Number(item.remaining_amount).toLocaleString()}
      </Text>
    </Card>
  );
}

const styles = StyleSheet.create({
  content: { padding: Spacing.three, gap: Spacing.three },
  rowHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: Spacing.half,
  },
  tenant: { fontSize: 17, fontWeight: '700', flex: 1 },
  status: { fontSize: 13, fontWeight: '700' },
  meta: { fontSize: 14, marginBottom: Spacing.half },
  sectionTitle: { fontSize: 17, fontWeight: '700' },
  scheduleTitle: { fontSize: 14, fontWeight: '700', flex: 1 },
});