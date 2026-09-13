import { useCallback, useState } from 'react';
import { FlatList, RefreshControl, StyleSheet, Text, View } from 'react-native';
import { Link, useFocusEffect } from 'expo-router';

import { listProperties } from '@/api/properties';
import { ApiRequestError } from '@/api/client';
import type { Property } from '@/api/types';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { EmptyState, ErrorState, LoadingState, Screen } from '@/components/ui/screen';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

export default function PropertiesScreen() {
  const theme = useTheme();
  const [properties, setProperties] = useState<Property[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await listProperties();
      setProperties(res.results);
    } catch (err) {
      if (err instanceof ApiRequestError) setError(err.message);
      else setError('Unable to load properties.');
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
  if (error && properties.length === 0) {
    return <ErrorState message={error} onRetry={() => void load()} />;
  }

  return (
    <Screen
      title="Properties"
      scroll={false}
      headerRight={
        <Link href="/(app)/properties/new-property" asChild>
          <Button title="Add" variant="ghost" onPress={() => {}} />
        </Link>
      }
    >
      <FlatList
        data={properties}
        keyExtractor={(item) => String(item.id)}
        contentContainerStyle={styles.list}
        renderItem={({ item }) => <PropertyRow property={item} />}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={theme.primary}
          />
        }
        ListEmptyComponent={
          <EmptyState
            title="No properties yet"
            message="Tap “Add” to register your first property."
          />
        }
      />
    </Screen>
  );
}

function PropertyRow({ property }: { property: Property }) {
  const theme = useTheme();
  return (
    <Link href={`/(app)/properties/property-detail?id=${property.id}`} asChild>
      <Card>
        <View style={styles.rowHeader}>
          <Text style={[styles.name, { color: theme.text }]}>{property.name}</Text>
          <Text style={[styles.meta, { color: theme.textSecondary }]}>
            {property.property_type}
          </Text>
        </View>
        <Text style={[styles.address, { color: theme.textSecondary }]}>
          {property.city}, {property.state}
        </Text>
        <Text style={[styles.meta, { color: theme.textSecondary }]}>
          {property.unit_count} units · {property.occupied_units} occupied ·{' '}
          {property.vacant_units} vacant
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
  address: {
    fontSize: 14,
    marginBottom: Spacing.one,
  },
  meta: {
    fontSize: 13,
  },
});