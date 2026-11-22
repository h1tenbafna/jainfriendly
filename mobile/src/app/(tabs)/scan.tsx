import { BarcodeScanningResult, CameraView, useCameraPermissions } from 'expo-camera';
import { router, useFocusEffect } from 'expo-router';
import { useCallback, useRef, useState } from 'react';
import { Platform, StyleSheet, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button, Message } from '@/components/ui';
import { ApiError } from '@/lib/api';
import { usePrefs } from '@/lib/prefs';
import { colors, radius, space } from '@/lib/theme';

type Status = { kind: 'idle' } | { kind: 'looking'; code: string } | { kind: 'missing'; code: string } | { kind: 'error'; message: string };

export default function Scan() {
  const { api } = usePrefs();
  const [permission, requestPermission] = useCameraPermissions();
  const [focused, setFocused] = useState(false);
  const [status, setStatus] = useState<Status>({ kind: 'idle' });
  const [manual, setManual] = useState('');
  const busy = useRef(false);

  // Only one camera preview may be active at a time: mount it only while this tab is focused.
  useFocusEffect(
    useCallback(() => {
      setFocused(true);
      busy.current = false;
      setStatus({ kind: 'idle' });
      return () => setFocused(false);
    }, []),
  );

  const lookup = useCallback(
    async (code: string) => {
      const clean = code.replace(/\D/g, '');
      if (busy.current || clean.length < 8) return;
      busy.current = true;
      setStatus({ kind: 'looking', code: clean });
      try {
        const product = await api.barcode(clean);
        router.push(`/product/${product.id}`);
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) setStatus({ kind: 'missing', code: clean });
        else setStatus({ kind: 'error', message: (e as Error).message });
        busy.current = false;
      }
    },
    [api],
  );

  const onScanned = (r: BarcodeScanningResult) => lookup(r.data);
  const cameraAvailable = Platform.OS !== 'web';

  return (
    <SafeAreaView edges={['top']} style={s.root}>
      <Text style={s.title}>Scan a barcode</Text>
      <Text style={s.lead}>Point the camera at the barcode on the back of the pack.</Text>

      <View style={s.viewfinder}>
        {!cameraAvailable ? (
          <Message icon="camera-outline" title="Camera scanning works in the phone app" body="Type the barcode below instead." />
        ) : !permission ? null : !permission.granted ? (
          <Message
            icon="camera-outline"
            title="Camera access needed"
            body="We only use the camera to read barcodes. Nothing is recorded or uploaded."
            action={<Button title="Allow camera" onPress={requestPermission} />}
          />
        ) : focused ? (
          <CameraView
            style={StyleSheet.absoluteFill}
            facing="back"
            barcodeScannerSettings={{ barcodeTypes: ['ean13', 'ean8', 'upc_a', 'upc_e'] }}
            onBarcodeScanned={status.kind === 'idle' ? onScanned : undefined}
          />
        ) : null}
        {cameraAvailable && permission?.granted ? <View pointerEvents="none" style={s.frame} /> : null}
      </View>

      <View style={s.status}>
        {status.kind === 'looking' ? <Text style={s.statusText}>Looking up {status.code}…</Text> : null}
        {status.kind === 'missing' ? (
          <>
            <Text style={s.statusText}>{status.code} isn’t in our catalogue yet.</Text>
            <Text style={s.statusSub}>We’re still adding products. Try searching by name instead.</Text>
            <Button title="Scan again" kind="secondary" onPress={() => setStatus({ kind: 'idle' })} />
          </>
        ) : null}
        {status.kind === 'error' ? (
          <>
            <Text style={[s.statusText, { color: colors.danger }]}>{status.message}</Text>
            <Button title="Try again" kind="secondary" onPress={() => setStatus({ kind: 'idle' })} />
          </>
        ) : null}
      </View>

      <View style={s.manual}>
        <TextInput
          value={manual}
          onChangeText={setManual}
          placeholder="Or type the barcode number"
          placeholderTextColor={colors.textFaint}
          keyboardType="number-pad"
          style={s.input}
          onSubmitEditing={() => lookup(manual)}
          returnKeyType="search"
        />
        <Button title="Look up" kind="secondary" onPress={() => lookup(manual)} disabled={manual.replace(/\D/g, '').length < 8} />
      </View>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg, padding: space(4), gap: space(3) },
  title: { color: colors.text, fontSize: 22, fontWeight: '800' },
  lead: { color: colors.textMuted, fontSize: 14 },
  viewfinder: {
    height: 300,
    borderRadius: radius.lg,
    overflow: 'hidden',
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    justifyContent: 'center',
  },
  frame: {
    position: 'absolute',
    left: '12%',
    right: '12%',
    top: '30%',
    bottom: '30%',
    borderWidth: 2,
    borderColor: colors.accent,
    borderRadius: radius.md,
  },
  status: { gap: space(2), minHeight: 40 },
  statusText: { color: colors.text, fontSize: 15, fontWeight: '600' },
  statusSub: { color: colors.textMuted, fontSize: 13 },
  manual: { gap: space(2) },
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
});
