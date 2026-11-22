import Ionicons from '@expo/vector-icons/Ionicons';
import { Redirect, Tabs } from 'expo-router';

import { usePrefs } from '@/lib/prefs';
import { colors } from '@/lib/theme';

type IconName = React.ComponentProps<typeof Ionicons>['name'];
function icon(name: IconName) {
  return function TabIcon({ color, size }: { color: unknown; size: number }) {
    return <Ionicons name={name} color={String(color)} size={size} />;
  };
}

export default function TabsLayout() {
  const { prefs, loaded } = usePrefs();
  if (!loaded) return null;
  if (!prefs.onboarded) return <Redirect href="/onboarding" />;
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        sceneStyle: { backgroundColor: colors.bg },
        tabBarStyle: { backgroundColor: colors.surface, borderTopColor: colors.border },
        tabBarActiveTintColor: colors.accent,
        tabBarInactiveTintColor: colors.textFaint,
      }}
    >
      <Tabs.Screen
        name="index"
        options={{ title: 'Browse', tabBarIcon: icon("search") }}
      />
      <Tabs.Screen
        name="scan"
        options={{ title: 'Scan', tabBarIcon: icon("barcode-outline") }}
      />
      <Tabs.Screen
        name="you"
        options={{ title: 'You', tabBarIcon: icon("person-circle-outline") }}
      />
    </Tabs>
  );
}
