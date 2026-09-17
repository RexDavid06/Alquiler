import { useEffect } from 'react';
import { DarkTheme, DefaultTheme, Stack, ThemeProvider } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useColorScheme } from 'react-native';

import { AuthProvider, useAuth } from '@/context/auth-context';
import { useNotificationObserver } from '@/utils/push-notifications';

void SplashScreen.preventAutoHideAsync();

function RootNavigator() {
  const { initializing } = useAuth();
  const colorScheme = useColorScheme();
  useNotificationObserver();

  useEffect(() => {
    if (!initializing) {
      void SplashScreen.hideAsync();
    }
  }, [initializing]);

  return (
    <ThemeProvider value={colorScheme === 'dark' ? DarkTheme : DefaultTheme}>
      <StatusBar style="auto" />
      <Stack screenOptions={{ headerShown: false }}>
        <Stack.Screen name="(auth)" />
        <Stack.Screen name="(app)" />
      </Stack>
    </ThemeProvider>
  );
}

export default function RootLayout() {
  return (
    <AuthProvider>
      <RootNavigator />
    </AuthProvider>
  );
}