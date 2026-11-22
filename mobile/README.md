# JainFriendly mobile app

Expo (SDK 58, React Native, Expo Router) client for the JainFriendly API.

## Run it

```bash
# 1. API, reachable from your phone on the same Wi-Fi
scripts/run.sh --host 0.0.0.0          # from the repo root

# 2. App
cd mobile
npm install
npx expo start                         # scan the QR code with Expo Go (Android) or the Camera app (iOS)
npx expo start --web                   # quick preview in a browser (no camera scanning)
```

The app looks for the API on the same machine that serves the JS bundle, at port 8000. You can
change this in the **You** tab or with `EXPO_PUBLIC_API_URL=http://192.168.1.5:8000 npx expo start`.

Checks: `npx tsc --noEmit` and `npx expo lint`.

## Screens

| Route | What |
|---|---|
| `src/app/onboarding.tsx` | First run: diet (Jain / vegetarian / vegan), personal Jain options (sonth, yeast, brinjal…), allergies |
| `src/app/(tabs)/index.tsx` | Browse: search, "friendly only" / "verified only" / "made in India", category chips, infinite list |
| `src/app/(tabs)/scan.tsx` | Barcode scanner (`expo-camera`) → `/v1/products/barcode/{gtin}`, plus manual entry |
| `src/app/(tabs)/you.tsx` | Edit preferences, server address |
| `src/app/product/[id].tsx` | Personal verdict with evidence, allergy checks, other diets, contains / might contain / traces, ingredients + source, where to buy |

## How personal options reach the server

The catalogue stores verdicts computed with each profile's **default** options. The app handles
personal options as follows:

- **In lists**, the app turns each extra restriction the user switches on (e.g. avoid sonth) into
  `avoid=<tag>` filters. It expands `group:` targets using `/v1/tags`.
- **On the product screen**, if any option differs from the default, the app calls
  `POST /v1/products/{id}/evaluate`. The server re-checks the stored ingredients and veg mark with the
  user's exact options. Otherwise it uses the stored per-profile results.

Products without an ingredient list always show "No ingredient list yet", never a verdict.

## Storage

Preferences live in `expo-sqlite/kv-store` on device (`src/lib/storage.ts`). The web preview uses
`localStorage` (`storage.web.ts`) because expo-sqlite on web needs WASM and cross-origin isolation.
