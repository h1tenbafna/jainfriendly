import { Image } from 'expo-image';
import { router } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { ProductSummary } from '@/lib/api';
import { colors, radius, space } from '@/lib/theme';
import { VerdictPill } from './ui';

export function ProductCard({ item, diet, allergies }: { item: ProductSummary; diet: string; allergies: string[] }) {
  const verdict = item.has_ingredients ? item.verdicts[diet] ?? 'no_data' : 'no_data';
  const allergyHits = allergies.filter((a) => {
    const v = item.verdicts[`allergen:${a}`];
    return v === 'not_friendly' || v === 'unclear';
  });
  const cheapest = item.offers.find((o) => o.price != null);
  const flags = item.contains.slice(0, 3).map((t) => t.label);
  return (
    <Pressable
      onPress={() => router.push(`/product/${item.id}`)}
      accessibilityRole="link"
      style={({ pressed }) => [s.row, pressed && { opacity: 0.75 }]}
    >
      <View style={s.thumb}>
        {item.image_url ? (
          <Image source={item.image_url} style={s.img} contentFit="contain" transition={150} />
        ) : (
          <Text style={s.thumbText}>{(item.brand ?? item.name).slice(0, 2)}</Text>
        )}
      </View>
      <View style={s.body}>
        <Text style={s.brand} numberOfLines={1}>
          {[item.brand, item.quantity].filter(Boolean).join(' · ')}
        </Text>
        <Text style={s.name} numberOfLines={2}>
          {item.name}
        </Text>
        <View style={s.pills}>
          <VerdictPill verdict={verdict} />
          {allergyHits.length ? <VerdictPill verdict="unclear" label={`Allergy: ${allergyHits.join(', ')}`} /> : null}
        </View>
        {flags.length ? (
          <Text style={s.flags} numberOfLines={1}>
            Contains {flags.join(', ')}
          </Text>
        ) : null}
      </View>
      {cheapest ? (
        <View style={s.price}>
          <Text style={s.priceText}>₹{cheapest.price}</Text>
            <Text style={s.priceStore}>{cheapest.platform_name}</Text>
          </View>
        ) : null}
    </Pressable>
  );
}

const s = StyleSheet.create({
  row: {
    flexDirection: 'row',
    gap: space(3),
    padding: space(3),
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  thumb: {
    width: 72,
    height: 72,
    borderRadius: radius.md,
    backgroundColor: '#fff',
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
  img: { width: '100%', height: '100%' },
  thumbText: { color: '#555', fontWeight: '700', fontSize: 18, textTransform: 'uppercase' },
  body: { flex: 1, gap: 4 },
  brand: { color: colors.textMuted, fontSize: 12 },
  name: { color: colors.text, fontSize: 15, fontWeight: '600' },
  pills: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 2 },
  flags: { color: colors.textFaint, fontSize: 12 },
  price: { alignItems: 'flex-end' },
  priceText: { color: colors.text, fontWeight: '700', fontSize: 15 },
  priceStore: { color: colors.textMuted, fontSize: 11 },
});
