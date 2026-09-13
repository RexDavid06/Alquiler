import { useCallback, useState } from 'react';
import { FlatList, RefreshControl, StyleSheet, Text, View } from 'react-native';
import { Link, useFocusEffect } from 'expo-router';

import { listTenants } from '@/api/tenants';
import { ApiRequestError } from '@/api/client';
import type { TenantUser } from '@/api/types';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { EmptyState, ErrorState, LoadingState, Screen } from '@/components/ui/screen';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

export default function TenantsScreen() {
  const theme = useTheme();
  const [tenants, setTenants] = useState<TenantUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await listTenants();
      setTenants(res.results);
    } catch (err) {
      if (err instanceof ApiRequestError) setError(err.message);
      else setError('Unable to load tenants.');
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
  if (error && tenants.length === 0) {
    return <ErrorState message={error} onRetry={() => void load()} />;
  }

  return (
    <Screen
      title="Tenants"
      scroll={false}
      headerRight={
        <Link href="/(app)/tenants/invite" asChild>
          <Button title="Invite" variant="ghost" onPress={() => {}} />
        </Link>
      }
    >
      <FlatList
        data={tenants}
        keyExtractor={(item) => String(item.id)}
        contentContainerStyle={styles.list}
        renderItem={({ item }) => <TenantRow tenant={item} />}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={theme.primary} />
        }
        ListEmptyComponent={
          <EmptyState
            title="No tenants yet"
            message="Tap “Invite” to send an email invitation to your first tenant."
          />
        }
      />
    </Screen>
  );
}

function TenantRow({ tenant }: { tenant: TenantUser }) {
  const theme = useTheme();
  return (
    <Link href={`/(app)/tenants/tenant-detail?id=${tenant.id}`} asChild>
      <Card>
        <View style={styles.rowHeader}>
          <Text style={[styles.name, { color: theme.text }]}>{tenant.full_name}</Text>
          <Text
            style={[
              styles.status,
              { color: tenant.status === 'ACTIVE' ? theme.success : theme.textSecondary },
            ]}
          >
            {tenant.status}
          </Text>
        </View>
        <Text style={[styles.email, { color: theme.textSecondary }]}>{tenant.email}</Text>
        <Text style={[styles.meta, { color: theme.textSecondary }]}>
          {tenant.total_leases} leases · {tenant.active_leases} active
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
  name: {
    fontSize: 16,
    fontWeight: '700',
  },
  email: {
    fontSize: 14,
    marginBottom: Spacing.one,
  },
  meta: {
    fontSize: 13,
  },
  status: {
    fontSize: 13,
    fontWeight: '600',
  },
});