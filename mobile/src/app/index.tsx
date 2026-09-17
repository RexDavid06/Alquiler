import { Redirect, useRouter } from 'expo-router';
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/button';
import { ThreeDHero } from '@/components/three-d-hero';
import { Spacing } from '@/constants/theme';
import { useAuth } from '@/context/auth-context';
import { useTheme } from '@/hooks/use-theme';

export default function LandingScreen() {
  const router = useRouter();
  const { user, initializing } = useAuth();
  const theme = useTheme();

  if (initializing) {
    return (
      <View style={[styles.center, { backgroundColor: theme.background }]}>
        <ActivityIndicator size="large" color={theme.primary} />
      </View>
    );
  }

  if (user) {
    return <Redirect href="/(app)/home" />;
  }

  return (
    <SafeAreaView
      style={[styles.safe, { backgroundColor: theme.background }]}
      edges={['top', 'bottom']}
    >
      <View
        style={[styles.glowTop, { backgroundColor: `${theme.primary}22` }]}
        pointerEvents="none"
      />
      <View
        style={[styles.glowBottom, { backgroundColor: `${theme.primary}14` }]}
        pointerEvents="none"
      />

      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <View style={styles.brand}>
          <Text style={[styles.logo, { color: theme.primary }]}>Alquiler</Text>
          <Text style={[styles.tagline, { color: theme.textSecondary }]}>
            Landlord workspace
          </Text>
        </View>

        <ThreeDHero />

        <View style={styles.copy}>
          <Text style={[styles.headline, { color: theme.text }]}>Rent, tracked beautifully.</Text>
          <Text style={[styles.body, { color: theme.textSecondary }]}>
            Properties, tenants, leases and payments — managed from one calm, modern workspace.
          </Text>
        </View>

        <View style={styles.actions}>
          <Button title="Get started" onPress={() => router.push('/(auth)/register')} />
          <Button
            title="I already have an account"
            variant="secondary"
            onPress={() => router.push('/(auth)/login')}
          />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
  },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  glowTop: {
    position: 'absolute',
    top: -120,
    right: -100,
    width: 280,
    height: 280,
    borderRadius: 140,
  },
  glowBottom: {
    position: 'absolute',
    bottom: -140,
    left: -120,
    width: 320,
    height: 320,
    borderRadius: 160,
  },
  content: {
    flexGrow: 1,
    justifyContent: 'center',
    paddingHorizontal: Spacing.four,
    paddingVertical: Spacing.five,
    gap: Spacing.four,
  },
  brand: {
    alignItems: 'center',
    gap: Spacing.one,
  },
  logo: {
    fontSize: 32,
    fontWeight: '800',
  },
  tagline: {
    fontSize: 14,
  },
  copy: {
    gap: Spacing.two,
    alignItems: 'center',
  },
  headline: {
    fontSize: 26,
    fontWeight: '800',
    textAlign: 'center',
  },
  body: {
    fontSize: 15,
    lineHeight: 22,
    textAlign: 'center',
  },
  actions: {
    gap: Spacing.two,
  },
});
