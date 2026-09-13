import { useCallback, useState } from 'react';
import { RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';

import {
  listNotifications,
  markRead,
  markAllRead,
} from '@/api/notifications';
import { ApiRequestError } from '@/api/client';
import type { Notification } from '@/api/types';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { EmptyState, ErrorState, LoadingState, Screen } from '@/components/ui/screen';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

function timeAgo(iso: string | null): string {
  if (!iso) return '';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export default function NotificationsScreen() {
  const theme = useTheme();
  const [items, setItems] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [markingAll, setMarkingAll] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await listNotifications();
      setItems(res.results);
    } catch (err) {
      if (err instanceof ApiRequestError) setError(err.message);
      else setError('Unable to load notifications.');
    } finally {
      setLoading(false);
    }
  }, []);

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const onMarkRead = async (n: Notification) => {
    if (n.is_read) return;
    setItems((prev) => prev.map((x) => (x.id === n.id ? { ...x, is_read: true } : x)));
    try {
      await markRead(n.id);
    } catch {
      await load();
    }
  };

  const onMarkAll = async () => {
    setMarkingAll(true);
    try {
      await markAllRead();
      setItems((prev) => prev.map((x) => ({ ...x, is_read: true })));
    } finally {
      setMarkingAll(false);
    }
  };

  return (
    <Screen title="Notifications" scroll={false}>
      {loading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={error} onRetry={() => void load()} />
      ) : items.length === 0 ? (
        <EmptyState title="No notifications" message="New updates appear here as they happen." />
      ) : (
        <ScrollView
          contentContainerStyle={styles.list}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={theme.primary} />
          }
        >
          <Button title="Mark all read" variant="ghost" onPress={onMarkAll} loading={markingAll} />
          {items.map((n) => (
            <Card
              key={n.id}
              onPress={() => onMarkRead(n)}
              style={[
                !n.is_read
                  ? { borderColor: theme.primary, borderWidth: 2 }
                  : undefined,
              ]}
            >
              <View style={styles.row}>
                <View style={styles.rowText}>
                  <Text style={[styles.title, { color: theme.text }]}>{n.title}</Text>
                  <Text style={[styles.message, { color: theme.textSecondary }]}>{n.message}</Text>
                  <Text style={[styles.meta, { color: theme.textSecondary }]}>
                    {n.notification_type_display} · {timeAgo(n.created_at)}
                  </Text>
                </View>
                {!n.is_read ? <View style={[styles.dot, { backgroundColor: theme.primary }]} /> : null}
              </View>
            </Card>
          ))}
        </ScrollView>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  list: {
    padding: Spacing.three,
    gap: Spacing.two,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
  },
  rowText: {
    flex: 1,
    gap: Spacing.half,
  },
  title: {
    fontSize: 15,
    fontWeight: '700',
  },
  message: {
    fontSize: 14,
  },
  meta: {
    fontSize: 12,
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
});