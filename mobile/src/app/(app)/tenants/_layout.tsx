import { Stack } from 'expo-router';

import { useTheme } from '@/hooks/use-theme';

export default function TenantsLayout() {
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
      <Stack.Screen name="index" options={{ title: 'Tenants', headerShown: false }} />
      <Stack.Screen name="tenant-detail" options={{ title: 'Tenant' }} />
      <Stack.Screen name="invite" options={{ title: 'Invite Tenant' }} />
    </Stack>
  );
}