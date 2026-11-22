// Typed client for the JainFriendly API (jainfriendly/api.py).
import Constants from 'expo-constants';
import { Platform } from 'react-native';

export type Verdict = 'friendly' | 'likely_friendly' | 'unclear' | 'not_friendly' | 'no_data';

export interface TagRef {
  id: string;
  label: string;
  likelihood?: 'low' | 'medium' | 'high';
}

export interface Offer {
  platform: string;
  platform_name: string;
  url: string | null;
  price: number | null;
  mrp: number | null;
  in_stock: boolean | null;
  location: string | null;
  seen_at: string;
}

export interface ProductSummary {
  id: number;
  gtin: string | null;
  name: string;
  brand: string | null;
  quantity: string | null;
  category: string | null;
  image_url: string | null;
  made_in_india: boolean;
  has_ingredients: boolean;
  unrecognized_count: number | null;
  verdicts: Record<string, Verdict>;
  contains: TagRef[];
  may_contain: TagRef[];
  traces: TagRef[];
  offers: Offer[];
}

export interface Evidence {
  status: 'present' | 'possible' | 'trace';
  source: string;
  ingredient: string;
  matched: string;
  likelihood?: string;
  reason?: string;
}

export interface TagResult {
  id: string;
  label: string;
  groups: string[];
  status: 'present' | 'possible' | 'trace';
  likelihood?: 'low' | 'medium' | 'high';
  evidence: Evidence[];
}

export interface BriefTag {
  id: string;
  label: string;
  status: string;
  likelihood?: string;
  because: string[];
  reasons?: string[];
}

export interface ProfileResult {
  profile: string;
  name: string;
  verdict: Verdict;
  headline: string;
  violations: BriefTag[];
  uncertain: BriefTag[];
  caveats: string[];
  allowed_by_preference: BriefTag[];
  options: Record<string, boolean>;
}

export interface Analysis {
  tags: TagResult[];
  unrecognized: string[];
  declared: { contains: string[]; may_contain: string[] };
  warnings: string[];
  profiles: Record<string, ProfileResult>;
}

export interface ProductDetail extends ProductSummary {
  ingredients_text: string | null;
  ingredients_source: string | null;
  analysis: Analysis | null;
  source: { name: string; url: string | null };
  attribution: string;
  disclaimer: string;
}

export interface ProfileInfo {
  id: string;
  name: string;
  description: string;
  options: { id: string; label: string; default: boolean; targets: string[] }[];
}

export interface TagsInfo {
  tags: { id: string; label: string; groups: string[] }[];
}

export interface CatalogFacets {
  products: number;
  categories: { name: string; count: number }[];
  platforms: { id: string; name: string; products: number }[];
}

export interface ProductQuery {
  q?: string;
  diet?: string[];
  free_from?: string[];
  avoid?: string[];
  category?: string;
  platform?: string;
  strict?: boolean;
  made_in_india?: boolean;
  limit?: number;
  offset?: number;
}

/** Where the API probably is during development: the same machine that serves the JS bundle. */
export function defaultApiUrl(): string {
  if (process.env.EXPO_PUBLIC_API_URL) return process.env.EXPO_PUBLIC_API_URL;
  if (Platform.OS === 'web' && typeof window !== 'undefined') {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  const host = Constants.expoConfig?.hostUri?.split(':')[0];
  return host ? `http://${host}:8000` : 'http://localhost:8000';
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

function qs(params: Record<string, unknown>): string {
  const parts: string[] = [];
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === '') continue;
    for (const item of Array.isArray(v) ? v : [v]) {
      parts.push(`${encodeURIComponent(k)}=${encodeURIComponent(String(item))}`);
    }
  }
  return parts.length ? `?${parts.join('&')}` : '';
}

export function makeApi(base: string) {
  const root = base.replace(/\/+$/, '');
  async function req<T>(path: string, init?: RequestInit): Promise<T> {
    let res: Response;
    try {
      res = await fetch(root + path, {
        ...init,
        headers: { Accept: 'application/json', 'Content-Type': 'application/json', ...init?.headers },
      });
    } catch {
      throw new ApiError(0, `Can't reach the JainFriendly server at ${root}`);
    }
    if (!res.ok) {
      let detail = res.statusText;
      try {
        detail = (await res.json()).detail ?? detail;
      } catch {}
      throw new ApiError(res.status, String(detail));
    }
    return res.json() as Promise<T>;
  }
  return {
    base: root,
    products: (q: ProductQuery) =>
      req<{ total: number; items: ProductSummary[]; attribution: string }>(`/v1/products${qs({ ...q })}`),
    product: (id: number | string) => req<ProductDetail>(`/v1/products/${id}`),
    barcode: (gtin: string) => req<ProductDetail>(`/v1/products/barcode/${encodeURIComponent(gtin)}`),
    catalog: () => req<CatalogFacets>('/v1/catalog'),
    profiles: () => req<ProfileInfo[]>('/v1/profiles'),
    tags: () => req<TagsInfo>('/v1/tags'),
    /** Re-check a catalogue product against the user's own profile options. */
    evaluate: (id: number, profiles: (string | { id: string; options: Record<string, boolean> })[]) =>
      req<{ profiles: ProfileResult[] }>(`/v1/products/${id}/evaluate`, {
        method: 'POST',
        body: JSON.stringify({ profiles }),
      }),
  };
}

export type Api = ReturnType<typeof makeApi>;
