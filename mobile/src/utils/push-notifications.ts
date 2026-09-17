import { Platform } from 'react-native';
import Constants from 'expo-constants';
import * as Notifications from 'expo-notifications';
import { router, type Href } from 'expo-router';
import { useEffect } from 'react';

import api from '@/api/client';
import { storage } from '@/utils/storage';

// =============================================================================
// Push notification scaffold (Phase 11).
//
// Sets up the foreground notification handler, an Android notification
// channel, and the notification-permission flow.  Registers the device's
// push token with the backend (POST /notifications/register-push-device/)
// and clears it on logout.
//
// Actual delivery requires push credentials (FCM/APNs + EAS projectId),
// which are intentionally out of scope here; the scaffold degrades to a
// no-op when the projectId is unavailable.
// =============================================================================

const PUSH_TOKEN_KEY = 'alquiler_push_token';
const PUSH_CHANNEL_ID = 'alquiler-default';

// Shows banners while the app is foregrounded.
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: false,
    shouldSetBadge: false,
  }),
});

export function resolveProjectId(): string | null {
  const config = Constants.expoConfig ?? Constants.easConfig;
  const projectId = config?.extra?.eas?.projectId ?? (Constants.easConfig as { projectId?: string } | null)?.projectId;
  return typeof projectId === 'string' && projectId.length > 0 ? projectId : null;
}

async function ensureAndroidChannel(): Promise<void> {
  if (Platform.OS !== 'android') return;
  await Notifications.setNotificationChannelAsync(PUSH_CHANNEL_ID, {
    name: 'Alquiler',
    importance: Notifications.AndroidImportance.DEFAULT,
    vibrationPattern: [0, 250, 250, 250],
    sound: 'default',
  });
}

async function requestPermission(): Promise<boolean> {
  const existing = await Notifications.getPermissionsAsync();
  let status = existing.status;
  if (status !== 'granted') {
    const requested = await Notifications.requestPermissionsAsync();
    status = requested.status;
  }
  return status === 'granted';
}

async function getPushToken(): Promise<string | null> {
  const projectId = resolveProjectId();
  try {
    if (projectId) {
      const token = await Notifications.getExpoPushTokenAsync({ projectId });
      return token.data;
    }
    // No EAS projectId: fall back to the native device token (FCM/APNs).
    const device = await Notifications.getDevicePushTokenAsync();
    return typeof device.data === 'string' ? device.data : null;
  } catch {
    return null;
  }
}

export async function currentPushToken(): Promise<string | null> {
  return storage.getItemAsync(PUSH_TOKEN_KEY);
}

// Called after login/register and on cold start once authenticated.
export async function registerForPushNotificationsAs(): Promise<string | null> {
  await ensureAndroidChannel();
  const granted = await requestPermission();
  if (!granted) return null;

  const token = await getPushToken();
  if (!token) return null;

  try {
    await api.post('/notifications/register-push-device/', {
      token,
      platform: Platform.OS === 'ios' ? 'IOS' : Platform.OS === 'web' ? 'WEB' : 'ANDROID',
    });
    await storage.setItemAsync(PUSH_TOKEN_KEY, token);
    return token;
  } catch {
    return null;
  }
}

// Called on logout: unregister the active token (idempotent on the backend).
export async function unregisterPushNotifications(): Promise<void> {
  const token = await storage.getItemAsync(PUSH_TOKEN_KEY);
  await storage.deleteItemAsync(PUSH_TOKEN_KEY);
  if (!token) return;
  try {
    await api.post('/notifications/unregister-push-device/', { token });
  } catch {
    // Backend may be unreachable during logout — local token is already gone.
  }
}

// Deep links: redirect to a URL carried in a tapped notification's `data.url`.
// Mirrors Expo Router's recommended pattern (see SDK 57 docs).
export function useNotificationObserver() {
  useEffect(() => {
    function redirect(notification: Notifications.Notification) {
      const url = notification.request.content.data?.url;
      if (typeof url === 'string') {
        router.push(url as Href);
      }
    }

    Notifications.getLastNotificationResponseAsync()
      .then((response) => {
        if (response?.notification) {
          redirect(response.notification);
        }
      })
      .catch(() => {});

    const subscription = Notifications.addNotificationResponseReceivedListener((response) => {
      redirect(response.notification);
    });

    return () => subscription.remove();
  }, []);
}