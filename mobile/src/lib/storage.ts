// Native key-value storage (SQLite-backed). The web build uses storage.web.ts instead.
import Storage from 'expo-sqlite/kv-store';

export const getItem = (key: string) => Storage.getItem(key);
export const setItem = (key: string, value: string) => Storage.setItem(key, value);
