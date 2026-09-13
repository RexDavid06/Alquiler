import { Stack } from 'expo-router';

import { useTheme } from '@/hooks/use-theme';

export default function PaymentsLayout() {
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
      <Stack.Screen name="index" options={{ title: 'Payments' }} />
      <Stack.Screen name="record-payment" options={{ title: 'Record Payment' }} />
    </Stack>
  );
}