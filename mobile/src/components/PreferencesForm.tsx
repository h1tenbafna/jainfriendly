// Diet + personal options + allergies. Used by onboarding and the "You" tab.
import { Pressable, StyleSheet, Switch, Text, View } from 'react-native';

import { Diet, usePrefs } from '@/lib/prefs';
import { colors, radius, space } from '@/lib/theme';
import { Button, Chip, Loading, Message, SectionTitle } from './ui';

const DIETS: { id: Diet; title: string; blurb: string }[] = [
  { id: 'jain', title: 'Jain', blurb: 'No onion, garlic, potato or other root vegetables, honey, mushroom' },
  { id: 'vegetarian', title: 'Vegetarian', blurb: 'No meat, fish, egg or slaughter by-products' },
  { id: 'vegan', title: 'Vegan', blurb: 'No animal products, including milk and honey' },
];

export function PreferencesForm() {
  const { prefs, update, meta, metaError, reloadMeta, api } = usePrefs();
  if (metaError) {
    return (
      <Message
        icon="cloud-offline-outline"
        title="Can't reach the server"
        body={`${metaError}\n\nStart it with scripts/run.sh --host 0.0.0.0 and check the server address in the "You" tab.`}
        action={<Button title="Try again" kind="secondary" onPress={reloadMeta} />}
      />
    );
  }
  if (!meta) return <Loading />;

  const profile = meta.profiles.find((p) => p.id === prefs.diet);
  const allergens = meta.profiles.filter((p) => p.id.startsWith('allergen:'));

  return (
    <View>
      <SectionTitle>Your diet</SectionTitle>
      <View style={{ gap: space(2) }}>
        {DIETS.map((d) => {
          const active = prefs.diet === d.id;
          return (
            <Pressable
              key={d.id}
              onPress={() => update({ diet: d.id, options: {} })}
              style={[s.diet, active && s.dietActive]}
              accessibilityRole="radio"
              accessibilityState={{ checked: active }}
            >
              <View style={[s.radio, active && s.radioActive]} />
              <View style={{ flex: 1 }}>
                <Text style={s.dietTitle}>{d.title}</Text>
                <Text style={s.dietBlurb}>{d.blurb}</Text>
              </View>
            </Pressable>
          );
        })}
      </View>

      {profile?.options.length ? (
        <>
          <SectionTitle>Personal choices</SectionTitle>
          <View style={s.options}>
            {profile.options.map((o, i) => (
              <View key={o.id} style={[s.option, i > 0 && s.optionBorder]}>
                <Text style={s.optionLabel}>{o.label}</Text>
                <Switch
                  value={prefs.options[o.id] ?? o.default}
                  onValueChange={(v) => update({ options: { ...prefs.options, [o.id]: v } })}
                  trackColor={{ true: colors.accent, false: colors.border }}
                  thumbColor="#fff"
                />
              </View>
            ))}
          </View>
        </>
      ) : null}

      <SectionTitle>Allergies</SectionTitle>
      <View style={s.chips}>
        {allergens.map((a) => {
          const id = a.id.slice('allergen:'.length);
          const active = prefs.allergies.includes(id);
          return (
            <Chip
              key={a.id}
              label={a.name}
              active={active}
              onPress={() =>
                update({ allergies: active ? prefs.allergies.filter((x) => x !== id) : [...prefs.allergies, id] })
              }
            />
          );
        })}
      </View>
      <Text style={s.note}>Connected to {api.base}</Text>
    </View>
  );
}

const s = StyleSheet.create({
  diet: {
    flexDirection: 'row',
    gap: space(3),
    alignItems: 'center',
    padding: space(4),
    borderRadius: radius.lg,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  dietActive: { borderColor: colors.accent },
  radio: { width: 20, height: 20, borderRadius: 10, borderWidth: 2, borderColor: colors.textFaint },
  radioActive: { borderColor: colors.accent, backgroundColor: colors.accent },
  dietTitle: { color: colors.text, fontSize: 16, fontWeight: '700' },
  dietBlurb: { color: colors.textMuted, fontSize: 13, marginTop: 2 },
  options: { backgroundColor: colors.surface, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.border },
  option: { flexDirection: 'row', alignItems: 'center', padding: space(4), gap: space(3) },
  optionBorder: { borderTopWidth: 1, borderTopColor: colors.border },
  optionLabel: { color: colors.text, flex: 1, fontSize: 14 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: space(2) },
  note: { color: colors.textFaint, fontSize: 11, marginTop: space(6) },
});
