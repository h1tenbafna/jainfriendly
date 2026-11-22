// User preferences (diet, personal options, allergies, server URL), persisted on device.
import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import * as Storage from './storage';
import { Api, defaultApiUrl, makeApi, ProfileInfo, TagsInfo } from './api';

export type Diet = 'jain' | 'vegetarian' | 'vegan';

export interface Prefs {
  onboarded: boolean;
  diet: Diet;
  /** Option overrides for the chosen diet, e.g. { dried_rhizomes: true }. Missing = profile default. */
  options: Record<string, boolean>;
  /** Allergen ids without the "allergen:" prefix, e.g. ["peanut", "milk"]. */
  allergies: string[];
  /** null = use the development default (the machine serving the JS bundle). */
  apiUrl: string | null;
}

const DEFAULTS: Prefs = { onboarded: false, diet: 'jain', options: {}, allergies: [], apiUrl: null };
const KEY = 'prefs.v1';

export interface Meta {
  profiles: ProfileInfo[];
  tags: TagsInfo['tags'];
}

interface PrefsContextValue {
  prefs: Prefs;
  loaded: boolean;
  update: (patch: Partial<Prefs>) => void;
  api: Api;
  meta: Meta | null;
  metaError: string | null;
  reloadMeta: () => void;
}

const PrefsContext = createContext<PrefsContextValue | null>(null);

export function PrefsProvider({ children }: { children: ReactNode }) {
  const [prefs, setPrefs] = useState<Prefs>(DEFAULTS);
  const [loaded, setLoaded] = useState(false);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [metaError, setMetaError] = useState<string | null>(null);
  const [metaNonce, setMetaNonce] = useState(0);

  useEffect(() => {
    Storage.getItem(KEY)
      .then((raw) => raw && setPrefs({ ...DEFAULTS, ...JSON.parse(raw) }))
      .catch(() => {})
      .finally(() => setLoaded(true));
  }, []);

  const update = useCallback((patch: Partial<Prefs>) => {
    setPrefs((prev) => {
      const next = { ...prev, ...patch };
      Storage.setItem(KEY, JSON.stringify(next)).catch(() => {});
      return next;
    });
  }, []);

  const api = useMemo(() => makeApi(prefs.apiUrl || defaultApiUrl()), [prefs.apiUrl]);

  useEffect(() => {
    if (!loaded) return;
    let cancelled = false;
    Promise.all([api.profiles(), api.tags()])
      .then(([profiles, tags]) => {
        if (cancelled) return;
        setMeta({ profiles, tags: tags.tags });
        setMetaError(null);
      })
      .catch((e) => !cancelled && setMetaError(String(e.message ?? e)));
    return () => {
      cancelled = true;
    };
  }, [api, loaded, metaNonce]);

  const value = useMemo(
    () => ({ prefs, loaded, update, api, meta, metaError, reloadMeta: () => {
        setMetaError(null);
        setMetaNonce((n) => n + 1);
      } }),
    [prefs, loaded, update, api, meta, metaError],
  );
  return <PrefsContext.Provider value={value}>{children}</PrefsContext.Provider>;
}

export function usePrefs(): PrefsContextValue {
  const ctx = useContext(PrefsContext);
  if (!ctx) throw new Error('usePrefs must be used inside PrefsProvider');
  return ctx;
}

/** Everything derived from preferences that screens need to query and evaluate. */
export function useDietQuery() {
  const { prefs, meta } = usePrefs();
  return useMemo(() => {
    const profile = meta?.profiles.find((p) => p.id === prefs.diet);
    const options: Record<string, boolean> = {};
    for (const o of profile?.options ?? []) options[o.id] = prefs.options[o.id] ?? o.default;

    // The catalogue's stored verdicts use default options. When the user switches an extra
    // restriction ON, exclude its tags in the list too. (Switching one OFF only makes the
    // list stricter than needed; the product screen re-evaluates with the exact options.)
    const extraTargets = (profile?.options ?? []).filter((o) => options[o.id] && !o.default).flatMap((o) => o.targets);
    const avoid = new Set<string>();
    for (const t of extraTargets) {
      const [kind, id] = t.split(':');
      if (kind === 'tag') avoid.add(id);
      else for (const tag of meta?.tags ?? []) if (tag.groups.includes(id)) avoid.add(tag.id);
    }
    const customised = (profile?.options ?? []).some((o) => options[o.id] !== o.default);
    return {
      diet: prefs.diet,
      dietName: profile?.name ?? prefs.diet,
      options,
      customised,
      avoid: [...avoid].sort(),
      allergies: prefs.allergies,
      profileSpecs: [
        { id: prefs.diet, options },
        ...prefs.allergies.map((a) => ({ id: `allergen:${a}`, options: {} })),
      ],
    };
  }, [prefs, meta]);
}
