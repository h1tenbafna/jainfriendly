// Web (development preview) storage: expo-sqlite on web needs WASM + cross-origin isolation.
export const getItem = async (key: string) => window.localStorage.getItem(key);
export const setItem = async (key: string, value: string) => window.localStorage.setItem(key, value);
