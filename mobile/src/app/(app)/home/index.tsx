import { useCallback, useEffect, useState } from 'react';
import { RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import Ionicons from '@expo/vector-icons/Ionicons';
import { Link, useFocusEffect } from 'expo-router';

import { getLandlordDashboard } from '@/api/dashboard';
import { getUnreadCount } from '@/api/notifications';
import { ApiRequestError } from '@/api/client';
import type { LandlordDashboard } from '@/api/types';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { ErrorState, LoadingState, Screen } from '@/components/ui/screen';
import { RADIUS, Spacing } from '@/constants/theme';
import { useAuth } from '@/context/auth-context';
import { useTheme } from '@/hooks/use-theme';

function StatCard({
  label,
  value,
  icon,
}: {
  label: string;
  value: string;
  icon: React.ComponentProps<typeof Ionicons>['name'];
}) {
  const theme = useTheme();
  return (
    <Card style={styles.statCard}>
      <View style={[styles.statIcon, { backgroundColor: theme.primary + '22' }]}>
        <Ionicons name={icon} size={18} color={theme.primary} />
      </View>
      <Text style={[styles.statValue, { color: theme.text }]}>{value}</Text>
      <Text style={[styles.statLabel, { color: theme.textSecondary }]}>{label}</Text>
    </Card>
  );
}

export default function DashboardScreen() {
  const { user, refreshUser } = useAuth();
  const theme = useTheme();
  const [data, setData] = useState<LandlordDashboard | null>(null);
  const [unread, setUnread] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [dash, unreadRes] = await Promise.all([
        getLandlordDashboard(),
        getUnreadCount().catch(() => ({ unread_count: 0 })),
      ]);
      setData(dash);
      setUnread(unreadRes.unread_count);
    } catch (err) {
      if (err instanceof ApiRequestError) {
        setError(err.message);
      } else {
        setError('Unable to load your dashboard.');
      }
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );

  const onRefresh = async () => {
    setRefreshing(true);
    await Promise.all([load(), refreshUser()]);
    setRefreshing(false);
  };

  if (error && !data) {
    return (
      <Screen title="Home">
        <ErrorState message={error} onRetry={() => void load()} />
      </Screen>
    );
  }

  const money = (v: unknown) =>
    typeof v === 'string' || typeof v === 'number' ? Number(v).toLocaleString() : '0';

  return (
    <Screen
      title={`Hi, ${user?.first_name || 'there'}`}
      subtitle="Your rental overview"
      scroll={false}
    >
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={theme.primary} />
        }
      >
        <View style={styles.quickActions}>
          <Link href="/(app)/payments/record-payment" asChild>
            <Button title="Record payment" variant="primary" onPress={() => {}} />
          </Link>
          <Link href="/(app)/leases/new-lease" asChild>
            <Button title="New lease" variant="secondary" onPress={() => {}} />
          </Link>
          <Link href="/(app)/tenants/invite" asChild>
            <Button title="Invite tenant" variant="secondary" onPress={() => {}} />
          </Link>
        </View>

        {!data ? (
          <LoadingState />
        ) : (
          <>
            <View style={styles.grid}>
              <StatCard
                label="Properties"
                value={String(data.properties?.total ?? 0)}
                icon="business"
              />
              <StatCard
                label="Units"
                value={String(data.units?.total ?? 0)}
                icon="home"
              />
              <StatCard
                label="Active leases"
                value={String(data.leases?.active ?? 0)}
                icon="document-text"
              />
              <StatCard
                label="Occupancy"
                value={`${data.units?.occupancy_rate ?? 0}%`}
                icon="pulse"
              />
            </View>

            <Card>
              <Text style={[styles.cardTitle, { color: theme.text }]}>Rent collected</Text>
              <Text style={[styles.amount, { color: theme.primary }]}>
                ₦{money(data.collected_rent?.total)}
              </Text>
              <Text style={[styles.cardSub, { color: theme.textSecondary }]}>
                {data.collected_rent?.payment_count ?? 0} payments
              </Text>
            </Card>

            <View style={styles.twoCol}>
              <Card style={styles.flexCol}>
                <Text style={[styles.cardTitle, { color: theme.text }]}>Overdue</Text>
                <Text style={[styles.smallAmount, { color: theme.danger }]}>
                  ₦{money(data.overdue_rent?.total)}
                </Text>
                <Text style={[styles.cardSub, { color: theme.textSecondary }]}>
                  {data.overdue_rent?.period_count ?? 0} periods
                </Text>
              </Card>
              <Card style={styles.flexCol}>
                <Text style={[styles.cardTitle, { color: theme.text }]}>Upcoming</Text>
                <Text style={[styles.smallAmount, { color: theme.warning }]}>
                  ₦{money(data.upcoming_rent?.total)}
                </Text>
                <Text style={[styles.cardSub, { color: theme.textSecondary }]}>
                  {data.upcoming_rent?.period_count ?? 0} periods
                </Text>
              </Card>
            </View>

            <Card style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
              <Link href="/(app)/home/notifications" style={{ flex: 1 }}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: Spacing.two }}>
                  <Ionicons name="notifications" size={20} color={theme.primary} />
                  <Text style={{ color: theme.text, fontSize: 15, fontWeight: '600' }}>
                    Notifications
                  </Text>
                </View>
              </Link>
              {unread > 0 ? (
                <View style={[styles.badge, { backgroundColor: theme.danger }]}>
                  <Text style={styles.badgeText}>{unread}</Text>
                </View>
              ) : null}
            </Card>

            <Card style={{ flexDirection: 'row', alignItems: 'center' }}>
              <Link href="/(app)/home/settings" style={{ flex: 1 }}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: Spacing.two }}>
                  <Ionicons name="settings" size={20} color={theme.primary} />
                  <Text style={{ color: theme.text, fontSize: 15, fontWeight: '600' }}>
                    Account & settings
                  </Text>
                </View>
              </Link>
            </Card>
          </>
        )}
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: {
    padding: Spacing.three,
    paddingBottom: Spacing.six,
    gap: Spacing.three,
  },
  quickActions: {
    flexDirection: 'row',
    gap: Spacing.two,
    flexWrap: 'wrap',
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.two,
  },
  statCard: {
    width: '48%',
    minWidth: '48%',
    gap: Spacing.one,
  },
  statIcon: {
    width: 32,
    height: 32,
    borderRadius: RADIUS.small,
    alignItems: 'center',
    justifyContent: 'center',
  },
  statValue: {
    fontSize: 22,
    fontWeight: '800',
  },
  statLabel: {
    fontSize: 13,
  },
  cardTitle: {
    fontSize: 14,
    fontWeight: '700',
  },
  cardSub: {
    fontSize: 13,
  },
  amount: {
    fontSize: 30,
    fontWeight: '800',
  },
  smallAmount: {
    fontSize: 20,
    fontWeight: '800',
  },
  twoCol: {
    flexDirection: 'row',
    gap: Spacing.two,
  },
  flexCol: {
    flex: 1,
  },
  badge: {
    minWidth: 22,
    height: 22,
    borderRadius: RADIUS.round,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: Spacing.one,
  },
  badgeText: {
    color: '#ffffff',
    fontSize: 12,
    fontWeight: '700',
  },
});