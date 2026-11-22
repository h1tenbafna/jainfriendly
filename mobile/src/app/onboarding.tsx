import { router } from 'expo-router';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { PreferencesForm } from '@/components/PreferencesForm';
import { Button } from '@/components/ui';
import { usePrefs } from '@/lib/prefs';
import { colors, space } from '@/lib/theme';

export default function Onboarding() {
  const { update, meta } = usePrefs();
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScrollView contentContainerStyle={s.content}>
        <Text style={s.logo}>JainFriendly</Text>
        <Text style={s.title}>Know what’s inside before you buy.</Text>
        <Text style={s.lead}>
          We read the ingredient list of packaged food and tell you what it contains, what might be hidden
          inside, and the evidence for each. Tell us how you eat.
        </Text>
        <PreferencesForm />
      </ScrollView>
      <View style={s.footer}>
        <Button
          title="Continue"
          disabled={!meta}
          onPress={() => {
            update({ onboarded: true });
            router.replace('/');
          }}
        />
        <Text style={s.small}>You can change this any time in the “You” tab.</Text>
      </View>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  content: { padding: space(5), paddingBottom: space(10) },
  logo: { color: colors.accent, fontWeight: '800', fontSize: 15, letterSpacing: 0.5 },
  title: { color: colors.text, fontSize: 28, fontWeight: '800', marginTop: space(3), lineHeight: 34 },
  lead: { color: colors.textMuted, fontSize: 15, lineHeight: 22, marginTop: space(3) },
  footer: { padding: space(5), gap: space(2), borderTopWidth: 1, borderTopColor: colors.border },
  small: { color: colors.textFaint, fontSize: 12, textAlign: 'center' },
});
