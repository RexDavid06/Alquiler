import { useCallback, useState } from 'react';
import { Alert, FlatList, StyleSheet, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';

import { getProperty, listUnits } from '@/api/properties';
import { ApiRequestError } from '@/api/client';
import type { Property, Unit } from '@/api/types';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { ErrorState, LoadingState, Screen } from '@/components/ui/screen';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

export default function PropertyDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const propertyId = Number(id);
  const theme = useTheme();
  const router = useRouter();

  const [property, setProperty] = useState<Property | null>(null);
  const [units, setUnits] = useState<Unit[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [p, u] = await Promise.all([getProperty(propertyId), listUnits(propertyId)]);
      setProperty(p);
      setUnits(u.results);
    } catch (err) {
      if (err instanceof ApiRequestError) setError(err.message);
      else setError('Unable to load property.');
    } finally {
      setLoading(false);
    }
  }, [propertyId]);

  if (loading) return <LoadingState />;
  if (error && !property) return <ErrorState message={error} onRetry={() => void load()} />;
  if (!property) return null;

  const statusColor = property.status === 'ACTIVE' ? theme.success : theme.textSecondary;

  return (
    <Screen title={property.name} subtitle={`${property.property_type}`} scroll={false}>
      <View style={styles.summaryWrap}>
        <Card>
          <Text style={[styles.address, { color: theme.textSecondary }]}>
            {property.address}
          </Text>
          <Text style={[styles.address, { color: theme.textSecondary }]}>
            {property.city}, {property.state} {property.country}
          </Text>
          {property.description ? (
            <Text style={[styles.address, { color: theme.textSecondary }]}>
              {property.description}
            </Text>
          ) : null}
          <View style={styles.metricsRow}>
            <Metric label="Units" value={String(property.unit_count)} />
            <Metric label="Occupied" value={String(property.occupied_units)} />
            <Metric label="Vacant" value={String(property.vacant_units)} />
            <View style={styles.metric}>
              <Text style={[styles.metricValue, { color: statusColor }]}>{property.status}</Text>
              <Text style={[styles.metricLabel, { color: theme.textSecondary }]}>Status</Text>
            </View>
          </View>
        </Card>
      </View>

      <View style={styles.unitsHeader}>
        <Text style={[styles.unitsTitle, { color: theme.text }]}>Units</Text>
        <Button
          title="Add unit"
          variant="ghost"
          onPress={() => {
            Alert.alert('Coming soon', 'Unit creation from mobile is coming soon.');
          }}
        />
      </View>

      <FlatList
        data={units}
        keyExtractor={(item) => String(item.id)}
        contentContainerStyle={styles.unitsList}
        renderItem={({ item }) => <UnitRow unit={item} />}
        ListEmptyComponent={
          <Card>
            <Text style={{ color: theme.textSecondary }}>
              No units on this property yet. Use the web app to add units for now.
            </Text>
          </Card>
        }
      />
    </Screen>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  const theme = useTheme();
  return (
    <View style={styles.metric}>
      <Text style={[styles.metricValue, { color: theme.text }]}>{value}</Text>
      <Text style={[styles.metricLabel, { color: theme.textSecondary }]}>{label}</Text>
    </View>
  );
}

function UnitRow({ unit }: { unit: Unit }) {
  const theme = useTheme();
  return (
    <Card>
      <View style={styles.unitRow}>
        <Text style={[styles.unitName, { color: theme.text }]}>{unit.name}</Text>
        <Text style={[styles.status, { color: theme.textSecondary }]}>{unit.status}</Text>
      </View>
      <Text style={[styles.unitMeta, { color: theme.textSecondary }]}>
        {unit.description || 'No description'}
      </Text>
    </Card>
  );
}

const styles = StyleSheet.create({
  summaryWrap: { paddingHorizontal: Spacing.three, paddingTop: Spacing.three },
  address: { fontSize: 14, marginBottom: Spacing.half },
  metricsRow: {
    flexDirection: 'row',
    marginTop: Spacing.two,
    justifyContent: 'space-between',
  },
  metric: { alignItems: 'flex-start', gap: Spacing.half },
  metricValue: { fontSize: 16, fontWeight: '800' },
  metricLabel: { fontSize: 12 },
  unitsHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing.three,
    paddingTop: Spacing.three,
  },
  unitsTitle: { fontSize: 17, fontWeight: '700' },
  unitsList: { padding: Spacing.three, gap: Spacing.two },
  unitRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: Spacing.half },
  unitName: { fontSize: 15, fontWeight: '700' },
  unitMeta: { fontSize: 13 },
  status: { fontSize: 13 },
});