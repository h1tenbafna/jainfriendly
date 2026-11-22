import { useState } from 'react';
import { ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { PreferencesForm } from '@/components/PreferencesForm';
import { Button, SectionTitle } from '@/components/ui';
import { defaultApiUrl } from '@/lib/api';
import { usePrefs } from '@/lib/prefs';
import { colors, radius, space } from '@/lib/theme';

export default function You() {
  const { prefs, update, reloadMeta } = usePrefs();
  const [url, setUrl] = useState(prefs.apiUrl ?? '');

  return (
    <SafeAreaView edges={['top']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScrollView contentContainerStyle={s.content} keyboardShouldPersistTaps="handled">
        <Text style={s.title}>Your preferences</Text>
        <Text style={s.lead}>Verdicts across the app follow these choices.</Text>
        <PreferencesForm />

        <SectionTitle>Server</SectionTitle>
        <Text style={s.help}>
          Leave empty to use {defaultApiUrl()} (the computer running the app in development).
        </Text>
        <TextInput
          value={url}
          onChangeText={setUrl}
          placeholder={defaultApiUrl()}
          placeholderTextColor={colors.textFaint}
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="url"
          style={s.input}
        />
        <View style={{ marginTop: space(2) }}>
          <Button
            title="Save server address"
            kind="secondary"
            onPress={() => {
              update({ apiUrl: url.trim() || null });
              reloadMeta();
            }}
          />
        </View>

        <Text style={s.disclaimer}>
          Results come from the ingredient list printed on the pack. Manufacturers don’t have to list
          everything inside compound ingredients under 5%, so when it matters, check the pack or ask the
          manufacturer.
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  content: { padding: space(4), paddingBottom: space(12) },
  title: { color: colors.text, fontSize: 22, fontWeight: '800' },
  lead: { color: colors.textMuted, fontSize: 14, marginTop: space(1) },
  help: { color: colors.textMuted, fontSize: 13, marginBottom: space(2) },
  input: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    color: colors.text,
    paddingHorizontal: space(3),
    paddingVertical: 12,
    fontSize: 15,
  },
  disclaimer: { color: colors.textFaint, fontSize: 12, lineHeight: 18, marginTop: space(8) },
});
