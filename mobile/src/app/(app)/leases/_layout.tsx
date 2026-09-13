import { Stack } from 'expo-router';

import { useTheme } from '@/hooks/use-theme';

export default function LeasesLayout() {
  const theme = useTheme();
  return (
    <Stack
      screenOptions={{
        headerShown: true,
        headerTitleAlign: 'center',
        headerStyle: { backgroundColor: theme.background },
        headerTintColor: theme.text,
        headerShadowVisible: false,
      }}
    >
      <Stack.Screen name="index" options={{ title: 'Leases', headerShown: false }} />
      <Stack.Screen name="lease-detail" options={{ title: 'Lease' }} />
      <Stack.Screen name="new-lease" options={{ title: 'New Lease' }} />
    </Stack>
  );
}