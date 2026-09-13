import { useCallback, useState } from 'react';
import { FlatList, StyleSheet, Text, View } from 'react-native';
import { useLocalSearchParams } from 'expo-router';

import { getTenant } from '@/api/tenants';
import { ApiRequestError } from '@/api/client';
import type { TenantDetail, TenantLeaseSummary } from '@/api/types';
import { Card } from '@/components/ui/card';
import { ErrorState, LoadingState, Screen } from '@/components/ui/screen';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

export default function TenantDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const tenantId = Number(id);
  const theme = useTheme();

  const [tenant, setTenant] = useState<TenantDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setTenant(await getTenant(tenantId));
    } catch (err) {
      if (err instanceof ApiRequestError) setError(err.message);
      else setError('Unable to load tenant.');
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  if (loading) return <LoadingState />;
  if (error && !tenant) return <ErrorState message={error} onRetry={() => void load()} />;
  if (!tenant) return null;

  return (
    <Screen title={tenant.full_name} subtitle={tenant.email} scroll={false}>
      <View style={styles.summaryWrap}>
        <Card>
          <Text style={[styles.row, { color: theme.text }]}>
            Status: <Text style={{ color: theme.textSecondary }}>{tenant.status}</Text>
          </Text>
          {tenant.phone ? (
            <Text style={[styles.row, { color: theme.text }]}>
              Phone: <Text style={{ color: theme.textSecondary }}>{tenant.phone}</Text>
            </Text>
          ) : null}
          <Text style={[styles.row, { color: theme.text }]}>
            Leases: <Text style={{ color: theme.textSecondary }}>{tenant.total_leases}</Text>
            {'  ·  '}Active:{' '}
            <Text style={{ color: theme.textSecondary }}>{tenant.active_leases}</Text>
          </Text>
        </Card>
      </View>

      <Text style={[styles.leasesTitle, { color: theme.text }]}>Leases</Text>
      <FlatList
        data={tenant.leases}
        keyExtractor={(item) => String(item.id)}
        contentContainerStyle={styles.list}
        renderItem={({ item }) => <LeaseRow lease={item} />}
        ListEmptyComponent={
          <Card>
            <Text style={{ color: theme.textSecondary }}>No leases yet.</Text>
          </Card>
        }
      />
    </Screen>
  );
}

function LeaseRow({ lease }: { lease: TenantLeaseSummary }) {
  const theme = useTheme();
  return (
    <Card>
      <View style={styles.rowHeader}>
        <Text style={[styles.leaseName, { color: theme.text }]}>{lease.property_name}</Text>
        <Text style={[styles.leaseStatus, { color: theme.textSecondary }]}>{lease.status}</Text>
      </View>
      <Text style={[styles.row, { color: theme.textSecondary }]}>
        Unit: {lease.unit_name}
      </Text>
      <Text style={[styles.row, { color: theme.textSecondary }]}>
        ₦{Number(lease.rent_amount).toLocaleString()} / {lease.rent_frequency.toLowerCase()}
      </Text>
      <Text style={[styles.row, { color: theme.textSecondary }]}>
        {lease.start_date.slice(0, 10)} → {lease.expiry_date.slice(0, 10)}
      </Text>
    </Card>
  );
}

const styles = StyleSheet.create({
  summaryWrap: { paddingHorizontal: Spacing.three, paddingTop: Spacing.three },
  row: { fontSize: 14, marginBottom: Spacing.half },
  leasesTitle: {
    fontSize: 17,
    fontWeight: '700',
    paddingHorizontal: Spacing.three,
    paddingTop: Spacing.three,
  },
  list: { padding: Spacing.three, gap: Spacing.two },
  rowHeader: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: Spacing.half },
  leaseName: { fontSize: 15, fontWeight: '700', flex: 1 },
  leaseStatus: { fontSize: 13 },
});