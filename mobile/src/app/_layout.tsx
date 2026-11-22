import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';

import { PrefsProvider } from '@/lib/prefs';
import { colors } from '@/lib/theme';

export default function RootLayout() {
  return (
    <PrefsProvider>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: colors.bg },
          headerTintColor: colors.text,
          headerTitleStyle: { color: colors.text },
          headerShadowVisible: false,
          headerTransparent: false,
          contentStyle: { backgroundColor: colors.bg },
        }}
      >
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="onboarding" options={{ headerShown: false, gestureEnabled: false }} />
        <Stack.Screen name="product/[id]" options={{ title: '', headerBackTitle: 'Back' }} />
      </Stack>
    </PrefsProvider>
  );
}
