import { ApiRequestError } from './client';
import { cacheGet, cacheSet } from '@/utils/cache';

// Read-through offline cache wrapper.
// - Online: returns fresh data and silently refreshes the cache entry.
// - Offline (network error, status 0): returns the newest cached snapshot
//   if one exists; otherwise rethrows the original network error.

export async function withCache<T>(key: string, fetcher: () => Promise<T>): Promise<T> {
  try {
    const data = await fetcher();
    await cacheSet(key, data);
    return data;
  } catch (err) {
    if (err instanceof ApiRequestError && err.status === 0) {
      const cached = await cacheGet<T>(key);
      if (cached !== null) return cached;
    }
    throw err;
  }
}