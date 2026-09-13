import { useState } from 'react';
import { Alert, Pressable, ScrollView, StyleSheet, Switch, Text, View } from 'react-native';
import { useRouter } from 'expo-router';

import { changePassword } from '@/api/auth';
import { ApiRequestError } from '@/api/client';
import { listPlans, getSubscription, subscribeToPlan, getUsage } from '@/api/subscriptions';
import { getPreferences, updatePreferences } from '@/api/notifications';
import type { NotificationPreference, Plan, Subscription, SubscriptionUsage } from '@/api/types';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Screen } from '@/components/ui/screen';
import { TextField } from '@/components/ui/text-field';
import { Spacing } from '@/constants/theme';
import { useAuth } from '@/context/auth-context';
import { useTheme } from '@/hooks/use-theme';

export default function SettingsScreen() {
  const { user, logout, refreshUser } = useAuth();
  const theme = useTheme();
  const router = useRouter();

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [savingPassword, setSavingPassword] = useState(false);

  const [prefs, setPrefs] = useState<NotificationPreference | null>(null);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [usage, setUsage] = useState<SubscriptionUsage | null>(null);

  const load = async () => {
    try {
      const [p, planList, sub, usg] = await Promise.all([
        getPreferences(),
        listPlans().then((r) => r.results ?? []),
        getSubscription().catch(() => null),
        getUsage().catch(() => null),
      ]);
      setPrefs(p);
      setPlans(planList);
      setSubscription(sub);
      setUsage(usg);
    } catch {
      // Non-critical informational loads; leave empty.
    }
  };

  if (!prefs) {
    void load();
  }

  const onChangePassword = async () => {
    if (newPassword.length < 8) {
      Alert.alert('Password too short', 'Use at least 8 characters.');
      return;
    }
    if (newPassword !== confirmPassword) {
      Alert.alert('Passwords do not match', 'Please re-enter your new password.');
      return;
    }
    setSavingPassword(true);
    try {
      await changePassword(currentPassword, newPassword);
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      Alert.alert('Success', 'Password updated.');
    } catch (err) {
      const msg =
        err instanceof ApiRequestError ? err.message : 'Unable to change password.';
      Alert.alert('Failed', msg);
    } finally {
      setSavingPassword(false);
    }
  };

  const onTogglePref = async (key: 'email_enabled' | 'in_app_enabled', value: boolean) => {
    if (!prefs) return;
    const next = { ...prefs, [key]: value };
    setPrefs(next);
    try {
      setPrefs(await updatePreferences({ [key]: value }));
    } catch {
      setPrefs(prefs);
      Alert.alert('Failed', 'Could not update notification settings.');
    }
  };

  const onSubscribe = async (planId: number) => {
    try {
      await subscribeToPlan(planId);
      Alert.alert('Success', 'Subscription updated.');
      await load();
      await refreshUser();
    } catch (err) {
      const msg = err instanceof ApiRequestError ? err.message : 'Unable to update subscription.';
      Alert.alert('Failed', msg);
    }
  };

  const onLogout = () => {
    Alert.alert('Log out', 'Are you sure you want to log out?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Log out', style: 'destructive', onPress: () => void logout() },
    ]);
  };

  return (
    <Screen title="Settings" scroll={false}>
      <ScrollView contentContainerStyle={styles.content} style={{ flex: 1 }}>
        <Card>
          <Text style={[styles.sectionTitle, { color: theme.text }]}>Profile</Text>
          <Text style={[styles.profileRow, { color: theme.text }]}>
            {user?.first_name} {user?.last_name}
          </Text>
          <Text style={[styles.profileRow, { color: theme.textSecondary }]}>{user?.email}</Text>
          <Text style={[styles.profileRow, { color: theme.textSecondary }]}>
            {user?.phone ? `Phone: ${user.phone}` : 'No phone on file'}
          </Text>
          <Text style={[styles.profileRow, { color: theme.textSecondary }]}>
            {user?.role}
          </Text>
        </Card>

        <Card>
          <Text style={[styles.sectionTitle, { color: theme.text }]}>Change password</Text>
          <TextField
            label="Current password"
            secureTextEntry
            value={currentPassword}
            onChangeText={setCurrentPassword}
            placeholder="••••••••"
          />
          <TextField
            label="New password"
            secureTextEntry
            value={newPassword}
            onChangeText={setNewPassword}
            placeholder="At least 8 characters"
          />
          <TextField
            label="Confirm new password"
            secureTextEntry
            value={confirmPassword}
            onChangeText={setConfirmPassword}
            placeholder="Repeat new password"
          />
          <Button title="Update password" onPress={onChangePassword} loading={savingPassword} />
        </Card>

        {prefs ? (
          <Card>
            <Text style={[styles.sectionTitle, { color: theme.text }]}>Notifications</Text>
            <ToggleRow
              label="Email notifications"
              value={prefs.email_enabled}
              onChange={(v) => onTogglePref('email_enabled', v)}
            />
            <ToggleRow
              label="In-app notifications"
              value={prefs.in_app_enabled}
              onChange={(v) => onTogglePref('in_app_enabled', v)}
            />
          </Card>
        ) : null}

        <Card>
          <Text style={[styles.sectionTitle, { color: theme.text }]}>Subscription</Text>
          {subscription ? (
            <>
              <Text style={[styles.profileRow, { color: theme.text }]}>
                Plan: {usage?.plan_name ?? '—'}
              </Text>
              <Text style={[styles.profileRow, { color: theme.textSecondary }]}>
                Status: {subscription.status}
              </Text>
              {subscription.current_period_end ? (
                <Text style={[styles.profileRow, { color: theme.textSecondary }]}>
                  Renews: {new Date(subscription.current_period_end).toLocaleDateString()}
                </Text>
              ) : null}
            </>
          ) : (
            <Text style={[styles.profileRow, { color: theme.textSecondary }]}>
              No active subscription.
            </Text>
          )}
          {usage ? (
            <Text style={[styles.profileRow, { color: theme.textSecondary }]}>
              Usage: {usage?.active_tenants ?? 0}/{usage?.max_active_tenants ?? '∞'} tenants ·{' '}
              {usage?.properties ?? 0}/{usage?.max_properties ?? '∞'} properties
            </Text>
          ) : null}
          {plans.length > 0 && !subscription ? (
            <View style={{ gap: Spacing.two, marginTop: Spacing.two }}>
              {plans.map((p) => (
                <Button
                  key={p.id}
                  title={`${p.name} — ${p.price_ngn} NGN/mo`}
                  variant="secondary"
                  onPress={() => onSubscribe(p.id)}
                />
              ))}
            </View>
          ) : null}
        </Card>

        <Button title="Log out" variant="danger" onPress={onLogout} />
      </ScrollView>
    </Screen>
  );
}

function ToggleRow({
  label,
  value,
  onChange,
}: {
  label: string;
  value: boolean;
  onChange: (v: boolean) => void;
}) {
  const theme = useTheme();
  return (
    <Pressable
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        paddingVertical: Spacing.two,
      }}
      onPress={() => onChange(!value)}
    >
      <Text style={{ color: theme.text, fontSize: 15 }}>{label}</Text>
      <Switch
        value={value}
        onValueChange={onChange}
        trackColor={{ true: theme.primary }}
      />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  content: {
    padding: Spacing.three,
    gap: Spacing.three,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '800',
    marginBottom: Spacing.one,
  },
  profileRow: {
    fontSize: 14,
    marginBottom: Spacing.half,
  },
});