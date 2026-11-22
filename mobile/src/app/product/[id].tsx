import Ionicons from '@expo/vector-icons/Ionicons';
import { Image } from 'expo-image';
import { Stack, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { Linking, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { Button, Card, Loading, Message, SectionTitle, StoreBadge, VerdictPill } from '@/components/ui';
import { BriefTag, ProductDetail, ProfileResult, TagResult } from '@/lib/api';
import { useDietQuery, usePrefs } from '@/lib/prefs';
import { colors, radius, space, verdictStyle } from '@/lib/theme';

const OTHER_DIETS = [
  { id: 'jain', name: 'Jain' },
  { id: 'vegetarian', name: 'Vegetarian' },
  { id: 'vegan', name: 'Vegan' },
];

function sourceLabel(source: string | null): string {
  if (!source) return 'unknown source';
  if (source === 'openfoodfacts') return 'Open Food Facts (crowd-sourced)';
  if (source.startsWith('ocr')) return 'read from the label photo (OCR, may contain errors)';
  if (source.startsWith('feed:')) return `product feed (${source.slice(5)})`;
  return source;
}

export default function ProductScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { api } = usePrefs();
  const dq = useDietQuery();
  const [nonce, setNonce] = useState(0);
  const [loaded, setLoaded] = useState<{ key: string; product?: ProductDetail; error?: string }>({ key: '' });
  // Only needed when the user changed their diet options: stored verdicts use the defaults.
  const [custom, setCustom] = useState<{ key: unknown; results?: ProfileResult[]; error?: string }>({ key: null });

  const key = `${api.base}|${id}|${nonce}`;
  useEffect(() => {
    let cancelled = false;
    api
      .product(id)
      .then((product) => !cancelled && setLoaded({ key, product }))
      .catch((e) => !cancelled && setLoaded({ key, error: e.message ?? String(e) }));
    return () => {
      cancelled = true;
    };
  }, [api, id, key]);

  const product = loaded.key === key ? loaded.product : undefined;
  const error = loaded.key === key ? loaded.error : undefined;
  const needsCustom = !!product?.has_ingredients && dq.customised;
  const customKey = needsCustom ? dq.profileSpecs : null;

  useEffect(() => {
    if (!product || !customKey) return;
    let cancelled = false;
    api
      .evaluate(product.id, customKey)
      .then((r) => !cancelled && setCustom({ key: customKey, results: r.profiles }))
      .catch((e) => !cancelled && setCustom({ key: customKey, error: e.message ?? String(e) }));
    return () => {
      cancelled = true;
    };
  }, [api, product, customKey]);

  if (error) {
    return (
      <Message
        icon="alert-circle-outline"
        title="Couldn’t load this product"
        body={error}
        action={<Button title="Retry" kind="secondary" onPress={() => setNonce((n) => n + 1)} />}
      />
    );
  }
  if (!product) return <Loading />;

  const stored = product.analysis?.profiles ?? {};
  const customReady = custom.key === customKey;
  const results: ProfileResult[] | null = needsCustom
    ? customReady && custom.results
      ? custom.results
      : null
    : [stored[dq.diet], ...dq.allergies.map((a) => stored[`allergen:${a}`])].filter((r) => r !== undefined);
  const main = results?.find((r) => r.profile === dq.diet);
  const allergyResults = results?.filter((r) => r.profile.startsWith('allergen:')) ?? [];
  const customError = needsCustom && customReady ? custom.error : undefined;
  const tags = product.analysis?.tags ?? [];
  const present = tags.filter((t) => t.status === 'present');
  const possible = tags.filter((t) => t.status === 'possible');
  const traces = tags.filter((t) => t.status === 'trace');

  return (
    <>
      <Stack.Screen options={{ title: product.brand ?? '' }} />
      <ScrollView contentContainerStyle={s.content} contentInsetAdjustmentBehavior="automatic">
        <View style={s.hero}>
          <View style={s.heroImg}>
            {product.image_url ? (
              <Image source={product.image_url} style={{ width: '100%', height: '100%' }} contentFit="contain" />
            ) : (
              <Ionicons name="cube-outline" size={40} color="#999" />
            )}
          </View>
          <View style={{ flex: 1, gap: 4 }}>
            <Text style={s.brand}>{product.brand}</Text>
            <Text style={s.name}>{product.name}</Text>
            <Text style={s.meta}>
              {[product.quantity, product.made_in_india ? 'Made in India' : null, product.gtin]
                .filter(Boolean)
                .join(' · ')}
            </Text>
          </View>
        </View>

        {/* Your verdict */}
        {!product.has_ingredients ? (
          <Card style={{ marginTop: space(5) }}>
            <VerdictPill verdict="no_data" large />
            <Text style={s.cardText}>
              We don’t have this product’s ingredient list yet, so we can’t tell whether it suits you. Please check
              the pack.
            </Text>
          </Card>
        ) : customError ? (
          <Card style={{ marginTop: space(5) }}>
            <Text style={s.cardText}>Couldn’t check this product against your personal choices: {customError}</Text>
          </Card>
        ) : !main ? (
          <Loading />
        ) : (
          <VerdictCard result={main} customised={dq.customised} />
        )}

        {allergyResults.length ? (
          <>
            <SectionTitle>Your allergies</SectionTitle>
            <Card>
              {allergyResults.map((r) => (
                <View key={r.profile} style={s.allergyRow}>
                  <Text style={s.allergyName}>{r.name}</Text>
                  <VerdictPill
                    verdict={r.verdict}
                    label={
                      r.verdict === 'not_friendly'
                        ? 'Contains'
                        : r.verdict === 'unclear'
                          ? 'May contain'
                          : verdictStyle[r.verdict].label
                    }
                  />
                </View>
              ))}
            </Card>
          </>
        ) : null}

        {product.has_ingredients ? (
          <View style={s.otherDiets}>
            {OTHER_DIETS.filter((d) => d.id !== dq.diet).map((d) => (
              <View key={d.id} style={s.otherDiet}>
                <Text style={s.otherDietName}>{d.name}</Text>
                <VerdictPill verdict={product.verdicts[d.id] ?? 'no_data'} />
              </View>
            ))}
          </View>
        ) : null}

        {present.length ? (
          <>
            <SectionTitle>Contains</SectionTitle>
            <Card>
              {present.map((t) => (
                <TagRow key={t.id} tag={t} />
              ))}
            </Card>
          </>
        ) : null}

        {possible.length ? (
          <>
            <SectionTitle>Might contain</SectionTitle>
            <Card>
              {possible.map((t) => (
                <TagRow key={t.id} tag={t} />
              ))}
            </Card>
          </>
        ) : null}

        {traces.length ? (
          <>
            <SectionTitle>May contain traces</SectionTitle>
            <Card>
              {traces.map((t) => (
                <TagRow key={t.id} tag={t} />
              ))}
            </Card>
          </>
        ) : null}

        {product.ingredients_text ? (
          <>
            <SectionTitle>Ingredients</SectionTitle>
            <Card>
              <Text style={s.ingredients}>{product.ingredients_text}</Text>
              <Text style={s.small}>Source: {sourceLabel(product.ingredients_source)}</Text>
              {product.analysis?.unrecognized.length ? (
                <Text style={s.small}>
                  Not recognised yet: {product.analysis.unrecognized.join(', ')}. That’s why we can’t say “friendly”
                  for certain.
                </Text>
              ) : null}
            </Card>
          </>
        ) : null}

        <SectionTitle>Where to buy</SectionTitle>
        {product.offers.length ? (
          <Card style={{ gap: 0, paddingVertical: space(1) }}>
            {product.offers.map((o, i) => (
              <Pressable
                key={`${o.platform}-${o.location ?? ''}`}
                disabled={!o.url}
                onPress={() => o.url && Linking.openURL(o.url)}
                style={({ pressed }) => [s.offer, i > 0 && s.offerBorder, pressed && { opacity: 0.6 }]}
              >
                <StoreBadge platform={o.platform} name={o.platform_name} />
                <View style={{ flex: 1 }}>
                  <Text style={s.offerName}>{o.platform_name}</Text>
                  <Text style={s.small}>
                    {o.in_stock === false ? 'Out of stock' : o.in_stock ? 'In stock' : 'Stock unknown'}
                    {o.location ? ` · ${o.location}` : ''}
                  </Text>
                </View>
                {o.price != null ? (
                  <View style={{ alignItems: 'flex-end' }}>
                    <Text style={s.offerPrice}>₹{o.price}</Text>
                    {o.mrp && o.mrp > o.price ? <Text style={s.mrp}>₹{o.mrp}</Text> : null}
                  </View>
                ) : null}
                {o.url ? <Ionicons name="open-outline" size={16} color={colors.textMuted} /> : null}
              </Pressable>
            ))}
          </Card>
        ) : (
          <Card>
            <Text style={s.cardText}>Store links coming soon.</Text>
          </Card>
        )}

        <Text style={s.footer}>{product.disclaimer}</Text>
        <Text style={s.footer}>{product.attribution}</Text>
      </ScrollView>
    </>
  );
}

function VerdictCard({ result, customised }: { result: ProfileResult; customised: boolean }) {
  const v = verdictStyle[result.verdict];
  return (
    <View style={[s.verdict, { backgroundColor: v.bg, borderColor: v.fg + '55' }]}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: space(2) }}>
        <Ionicons name={v.icon as never} size={28} color={v.fg} />
        <View style={{ flex: 1 }}>
          <Text style={[s.verdictHeadline, { color: v.fg }]}>{result.headline}</Text>
          <Text style={s.small}>
            For {result.name}
            {customised ? ' with your personal choices' : ''}
          </Text>
        </View>
      </View>
      {result.violations.map((t) => (
        <Reason key={t.id} tag={t} icon="close" color={verdictStyle.not_friendly.fg} showReasons={false} />
      ))}
      {result.uncertain.map((t) => (
        <Reason key={t.id} tag={t} icon="help" color={verdictStyle.unclear.fg} showReasons />
      ))}
      {result.caveats.map((c) => (
        <Text key={c} style={s.caveat}>
          • {c}
        </Text>
      ))}
      {result.allowed_by_preference.length ? (
        <Text style={s.small}>
          Allowed by your settings: {result.allowed_by_preference.map((t) => t.label).join(', ')}
        </Text>
      ) : null}
    </View>
  );
}

const MAX_EVIDENCE = 3;

function Reason({ tag, icon, color, showReasons }: { tag: BriefTag; icon: string; color: string; showReasons: boolean }) {
  const more = tag.because.length - MAX_EVIDENCE;
  return (
    <View style={s.reason}>
      <Ionicons name={icon as never} size={16} color={color} style={{ marginTop: 2 }} />
      <View style={{ flex: 1 }}>
        <Text style={s.reasonTitle}>
          {tag.label}
          {tag.likelihood ? <Text style={s.small}> · {tag.likelihood} chance</Text> : null}
        </Text>
        {tag.because.slice(0, MAX_EVIDENCE).map((b) => (
          <Text key={b} style={s.small} numberOfLines={2}>
            from “{b}”
          </Text>
        ))}
        {more > 0 ? <Text style={s.small}>and {more} more (see “Contains” below)</Text> : null}
        {(showReasons ? tag.reasons ?? [] : []).map((r) => (
          <Text key={r} style={s.small}>
            {r}
          </Text>
        ))}
      </View>
    </View>
  );
}

function TagRow({ tag }: { tag: TagResult }) {
  const [open, setOpen] = useState(false);
  return (
    <Pressable onPress={() => setOpen(!open)} style={s.tagRow}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: space(2) }}>
        <Text style={s.tagLabel}>{tag.label}</Text>
        {tag.likelihood ? <Text style={s.small}>{tag.likelihood} chance</Text> : null}
        <View style={{ flex: 1 }} />
        <Ionicons name={open ? 'chevron-up' : 'chevron-down'} size={16} color={colors.textFaint} />
      </View>
      {open
        ? tag.evidence.map((e, i) => (
            <Text key={i} style={s.evidence}>
              “{e.ingredient}” matched {e.matched}
              {e.reason ? ` — ${e.reason}` : ''}
            </Text>
          ))
        : null}
    </Pressable>
  );
}

const s = StyleSheet.create({
  content: { padding: space(4), paddingBottom: space(12) },
  hero: { flexDirection: 'row', gap: space(4), alignItems: 'center' },
  heroImg: {
    width: 104,
    height: 104,
    borderRadius: radius.lg,
    backgroundColor: '#fff',
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
  brand: { color: colors.textMuted, fontSize: 13 },
  name: { color: colors.text, fontSize: 20, fontWeight: '800', lineHeight: 25 },
  meta: { color: colors.textFaint, fontSize: 12 },
  verdict: { marginTop: space(5), borderRadius: radius.lg, borderWidth: 1, padding: space(4), gap: space(3) },
  verdictHeadline: { fontSize: 20, fontWeight: '800' },
  reason: { flexDirection: 'row', gap: space(2) },
  reasonTitle: { color: colors.text, fontWeight: '600', fontSize: 14 },
  caveat: { color: colors.textMuted, fontSize: 13, lineHeight: 18 },
  cardText: { color: colors.text, fontSize: 14, lineHeight: 20 },
  small: { color: colors.textMuted, fontSize: 12, lineHeight: 17 },
  allergyRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  allergyName: { color: colors.text, fontSize: 14 },
  otherDiets: { flexDirection: 'row', gap: space(2), marginTop: space(4) },
  otherDiet: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: space(3),
    gap: space(1),
  },
  otherDietName: { color: colors.textMuted, fontSize: 12 },
  tagRow: { paddingVertical: space(1), gap: space(1) },
  tagLabel: { color: colors.text, fontSize: 14, fontWeight: '600' },
  evidence: { color: colors.textMuted, fontSize: 12, lineHeight: 17, paddingLeft: space(2) },
  ingredients: { color: colors.text, fontSize: 14, lineHeight: 21 },
  offer: { flexDirection: 'row', alignItems: 'center', gap: space(3), paddingVertical: space(3) },
  offerBorder: { borderTopWidth: 1, borderTopColor: colors.border },
  offerName: { color: colors.text, fontWeight: '600', fontSize: 14 },
  offerPrice: { color: colors.text, fontWeight: '700', fontSize: 15 },
  mrp: { color: colors.textFaint, fontSize: 12, textDecorationLine: 'line-through' },
  footer: { color: colors.textFaint, fontSize: 11, lineHeight: 16, marginTop: space(5) },
});
