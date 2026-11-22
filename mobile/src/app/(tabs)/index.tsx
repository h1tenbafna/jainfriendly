import Ionicons from '@expo/vector-icons/Ionicons';
import { useEffect, useMemo, useState } from 'react';
import { FlatList, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ProductCard } from '@/components/ProductCard';
import { Button, Chip, Loading, Message } from '@/components/ui';
import { CatalogFacets, ProductQuery, ProductSummary } from '@/lib/api';
import { useDietQuery, usePrefs } from '@/lib/prefs';
import { colors, radius, space } from '@/lib/theme';

const PAGE = 30;

export default function Browse() {
  const { api } = usePrefs();
  const dq = useDietQuery();
  const [q, setQ] = useState('');
  const [debouncedQ, setDebouncedQ] = useState('');
  const [category, setCategory] = useState<string | undefined>();
  const [onlyFriendly, setOnlyFriendly] = useState(true);
  const [strict, setStrict] = useState(false);
  const [madeInIndia, setMadeInIndia] = useState(false);
  const [facets, setFacets] = useState<CatalogFacets | null>(null);
  const [nonce, setNonce] = useState(0);
  const [result, setResult] = useState<{
    query: ProductQuery | null;
    items: ProductSummary[];
    total: number;
    attribution: string;
    error?: string;
  }>({ query: null, items: [], total: 0, attribution: '' });
  const [loadingMore, setLoadingMore] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q.trim()), 300);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => {
    api.catalog().then(setFacets).catch(() => {});
  }, [api]);

  // "Only friendly" applies the diet, the user's extra restrictions and their allergies.
  const query = useMemo<ProductQuery>(
    () => ({
      q: debouncedQ || undefined,
      diet: onlyFriendly ? [dq.diet] : undefined,
      avoid: onlyFriendly && dq.avoid.length ? dq.avoid : undefined,
      free_from: onlyFriendly ? dq.allergies : undefined,
      category,
      strict: onlyFriendly && strict ? true : undefined,
      made_in_india: madeInIndia ? true : undefined,
      limit: PAGE,
    }),
    // nonce: "Retry" creates a new query object and so refetches.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [debouncedQ, onlyFriendly, dq.diet, dq.avoid, dq.allergies, category, strict, madeInIndia, nonce],
  );

  useEffect(() => {
    let cancelled = false;
    api
      .products({ ...query, offset: 0 })
      .then((res) => !cancelled && setResult({ query, items: res.items, total: res.total, attribution: res.attribution }))
      .catch((e) => !cancelled && setResult({ query, items: [], total: 0, attribution: '', error: e.message ?? String(e) }));
    return () => {
      cancelled = true;
    };
  }, [api, query]);

  const current = result.query === query;
  const items = current ? result.items : [];
  const total = current ? result.total : 0;
  const error = current ? result.error : undefined;
  const attribution = result.attribution;
  const loading = !current || loadingMore;

  const loadMore = () => {
    if (loading || items.length >= total) return;
    setLoadingMore(true);
    api
      .products({ ...query, offset: items.length })
      .then((res) =>
        setResult((r) => (r.query === query ? { ...r, items: [...r.items, ...res.items], total: res.total } : r)),
      )
      .catch(() => {})
      .finally(() => setLoadingMore(false));
  };

  const header = (
    <View>
      <View style={s.top}>
        <Text style={s.logo}>JainFriendly</Text>
        <Text style={s.dietTag}>
          {dq.dietName}
          {dq.customised ? ' · custom' : ''}
          {dq.allergies.length ? ` · ${dq.allergies.length} allerg${dq.allergies.length > 1 ? 'ies' : 'y'}` : ''}
        </Text>
      </View>
      <View style={s.search}>
        <Ionicons name="search" size={18} color={colors.textFaint} />
        <TextInput
          value={q}
          onChangeText={setQ}
          placeholder="Search namkeen, biscuits, brands…"
          placeholderTextColor={colors.textFaint}
          style={s.input}
          returnKeyType="search"
          autoCorrect={false}
          clearButtonMode="while-editing"
        />
      </View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.chipRow}>
        <Chip
          label={`${dq.dietName}-friendly`}
          icon="leaf-outline"
          active={onlyFriendly}
          onPress={() => setOnlyFriendly(!onlyFriendly)}
        />
        {onlyFriendly ? (
          <Chip label="Verified only" icon="shield-checkmark-outline" active={strict} onPress={() => setStrict(!strict)} />
        ) : null}
        <Chip label="Made in India" active={madeInIndia} onPress={() => setMadeInIndia(!madeInIndia)} />
      </ScrollView>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.chipRow}>
        <Chip label="All" active={!category} onPress={() => setCategory(undefined)} />
        {facets?.categories.map((c) => (
          <Chip
            key={c.name}
            label={c.name}
            active={category === c.name}
            onPress={() => setCategory(category === c.name ? undefined : c.name)}
          />
        ))}
      </ScrollView>
      {!error ? (
        <Text style={s.count}>
          {loading && !items.length ? 'Loading…' : `${total} product${total === 1 ? '' : 's'}`}
          {onlyFriendly ? (strict ? ' verified friendly' : ' friendly or likely friendly') : ''}
        </Text>
      ) : null}
    </View>
  );

  return (
    <SafeAreaView edges={['top']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <FlatList
        data={error ? [] : items}
        keyExtractor={(p) => String(p.id)}
        renderItem={({ item }) => <ProductCard item={item} diet={dq.diet} allergies={dq.allergies} />}
        ListHeaderComponent={header}
        contentContainerStyle={s.list}
        ItemSeparatorComponent={() => <View style={{ height: space(2) }} />}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="on-drag"
        onEndReachedThreshold={0.5}
        onEndReached={loadMore}
        ListEmptyComponent={
          error ? (
            <Message
              icon="cloud-offline-outline"
              title="Couldn't load products"
              body={error}
              action={<Button title="Retry" kind="secondary" onPress={() => setNonce((n) => n + 1)} />}
            />
          ) : loading ? (
            <Loading />
          ) : (
            <Message icon="search-outline" title="Nothing matches" body="Try another search or fewer filters." />
          )
        }
        ListFooterComponent={
          items.length ? (
            <View>
              {loading ? <Loading /> : null}
              <Text style={s.attribution}>{attribution}</Text>
            </View>
          ) : undefined
        }
      />
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  list: { padding: space(4), paddingBottom: space(10) },
  top: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: space(3) },
  logo: { color: colors.accent, fontWeight: '800', fontSize: 20 },
  dietTag: { color: colors.textMuted, fontSize: 13 },
  search: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space(2),
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: space(3),
  },
  input: { flex: 1, color: colors.text, fontSize: 15, paddingVertical: 12 },
  chipRow: { gap: space(2), paddingVertical: space(2) },
  count: { color: colors.textMuted, fontSize: 12, marginTop: space(1), marginBottom: space(3) },
  attribution: { color: colors.textFaint, fontSize: 11, textAlign: 'center', marginTop: space(6) },
});
