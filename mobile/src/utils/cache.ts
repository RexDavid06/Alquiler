import AsyncStorage from '@react-native-async-storage/async-storage';

// =============================================================================
// Read-only offline cache (AsyncStorage-backed).
//
// Stores the last successful JSON payload per key and serves it back only
// when the network request fails (offline / no connectivity). Screen data is
// "stale-while-offline": online fetches always return fresh data and refresh
// the cache; offline requests fall back to the newest snapshot.
// =============================================================================

const CACHE_PREFIX = 'alquiler_cache:';

interface CacheEntry {
  savedAt: number;
  value: unknown;
}

export async function cacheGet<T>(key: string): Promise<T | null> {
  const raw = await AsyncStorage.getItem(CACHE_PREFIX + key);
  if (!raw) return null;
  try {
    const entry = JSON.parse(raw) as CacheEntry;
    return (entry.value as T) ?? null;
  } catch {
    return null;
  }
}

export async function cacheSet(key: string, value: unknown): Promise<void> {
  try {
    const entry: CacheEntry = { savedAt: Date.now(), value };
    await AsyncStorage.setItem(CACHE_PREFIX + key, JSON.stringify(entry));
  } catch {
    // Cache is best-effort; storage failures never break network reads.
  }
}

export async function cacheClear(): Promise<void> {
  try {
    const keys = await AsyncStorage.getAllKeys();
    const ours = keys.filter((k) => k.startsWith(CACHE_PREFIX));
    if (ours.length) {
      await AsyncStorage.multiRemove(ours);
    }
  } catch {
    // Best-effort cleanup.
  }
}

export function cacheKey(...parts: (string | number | boolean | undefined | null)[]): string {
  return parts.filter((p) => p !== undefined && p !== null).join(':');
}