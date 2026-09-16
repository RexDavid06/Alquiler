import { Platform } from 'react-native';
import * as SecureStore from 'expo-secure-store';

// SecureStore has no web implementation, so use localStorage in the browser.
// Kept behind the same async interface so the rest of the code stays unchanged.

interface KVStorage {
  getItemAsync(key: string): Promise<string | null>;
  setItemAsync(key: string, value: string): Promise<void>;
  deleteItemAsync(key: string): Promise<void>;
}

class LocalStorage implements KVStorage {
  async getItemAsync(key: string): Promise<string | null> {
    if (typeof localStorage !== 'undefined') {
      return localStorage.getItem(key);
    }
    return null;
  }

  async setItemAsync(key: string, value: string): Promise<void> {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(key, value);
    }
  }

  async deleteItemAsync(key: string): Promise<void> {
    if (typeof localStorage !== 'undefined') {
      localStorage.removeItem(key);
    }
  }
}

export const storage: KVStorage =
  Platform.OS === 'web' ? new LocalStorage() : (SecureStore as unknown as KVStorage);