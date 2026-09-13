import { Stack } from 'expo-router';

import { useTheme } from '@/hooks/use-theme';

export default function PropertiesLayout() {
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
      <Stack.Screen name="index" options={{ title: 'Properties', headerShown: false }} />
      <Stack.Screen name="property-detail" options={{ title: 'Property' }} />
      <Stack.Screen name="new-property" options={{ title: 'New Property' }} />
    </Stack>
  );
}