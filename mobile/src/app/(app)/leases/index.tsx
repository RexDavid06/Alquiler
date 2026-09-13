import { useCallback, useState } from 'react';
import { FlatList, RefreshControl, StyleSheet, Text, View } from 'react-native';
import { Link, useFocusEffect } from 'expo-router';

import { listLeases } from '@/api/leases';
import { ApiRequestError } from '@/api/client';
import type { Lease } from '@/api/types';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { EmptyState, ErrorState, LoadingState, Screen } from '@/components/ui/screen';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

export default function LeasesScreen() {
  const theme = useTheme();
  const [leases, setLeases] = useState<Lease[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await listLeases();
      setLeases(res.results);
    } catch (err) {
      if (err instanceof ApiRequestError) setError(err.message);
      else setError('Unable to load leases.');
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
  if (error && leases.length === 0) {
    return <ErrorState message={error} onRetry={() => void load()} />;
  }

  return (
    <Screen
      title="Leases"
      scroll={false}
      headerRight={
        <Link href="/(app)/leases/new-lease" asChild>
          <Button title="New" variant="ghost" onPress={() => {}} />
        </Link>
      }
    >
      <FlatList
        data={leases}
        keyExtractor={(item) => String(item.id)}
        contentContainerStyle={styles.list}
        renderItem={({ item }) => <LeaseRow lease={item} />}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={theme.primary} />
        }
        ListEmptyComponent={
          <EmptyState
            title="No leases yet"
            message="Tap “New” to create a lease agreement."
          />
        }
      />
    </Screen>
  );
}

function LeaseRow({ lease }: { lease: Lease }) {
  const theme = useTheme();
  const statusColor =
    lease.status === 'ACTIVE'
      ? theme.success
      : lease.status === 'EXPIRED' || lease.status === 'TERMINATED'
      ? theme.textSecondary
      : lease.status === 'EXPIRING'
      ? theme.warning
      : theme.text;

  return (
    <Link href={`/(app)/leases/lease-detail?id=${lease.id}`} asChild>
      <Card>
        <View style={styles.rowHeader}>
          <Text style={[styles.name, { color: theme.text }]}>{lease.tenant_name}</Text>
          <Text style={[styles.status, { color: statusColor }]}>{lease.status}</Text>
        </View>
        <Text style={[styles.meta, { color: theme.textSecondary }]}>
          {lease.property_name} – {lease.unit_name}
        </Text>
        <Text style={[styles.meta, { color: theme.textSecondary }]}>
          ₦{Number(lease.rent_amount).toLocaleString()} / {lease.rent_frequency.toLowerCase()}
        </Text>
        <Text style={[styles.meta, { color: theme.textSecondary }]}>
          {lease.start_date.slice(0, 10)} → {lease.expiry_date.slice(0, 10)}
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
    marginBottom: Spacing.one,
  },
  name: { fontSize: 16, fontWeight: '700', flex: 1 },
  status: { fontSize: 13, fontWeight: '600' },
  meta: { fontSize: 14 },
});