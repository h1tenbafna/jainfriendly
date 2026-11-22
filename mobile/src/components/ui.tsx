// Small shared building blocks.
import Ionicons from '@expo/vector-icons/Ionicons';
import { ReactNode } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View, ViewStyle } from 'react-native';

import { colors, radius, space, verdictStyle } from '@/lib/theme';

export function VerdictPill({ verdict, label, large }: { verdict: string; label?: string; large?: boolean }) {
  const v = verdictStyle[verdict] ?? verdictStyle.no_data;
  return (
    <View style={[styles.pill, { backgroundColor: v.bg }, large && styles.pillLarge]}>
      <Ionicons name={v.icon as never} size={large ? 16 : 12} color={v.fg} />
      <Text style={[styles.pillText, { color: v.fg }, large && { fontSize: 14 }]}>{label ?? v.label}</Text>
    </View>
  );
}

export function Chip({
  label,
  active,
  onPress,
  icon,
}: {
  label: string;
  active?: boolean;
  onPress?: () => void;
  icon?: string;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [styles.chip, active && styles.chipActive, pressed && { opacity: 0.7 }]}
      accessibilityRole="button"
      accessibilityState={{ selected: !!active }}
    >
      {icon ? <Ionicons name={icon as never} size={14} color={active ? colors.accentText : colors.textMuted} /> : null}
      <Text style={[styles.chipText, active && styles.chipTextActive]}>{label}</Text>
    </Pressable>
  );
}

const STORE_COLORS: Record<string, string> = {
  blinkit: '#F8CB46',
  zepto: '#7B2FF7',
  instamart: '#FC8019',
  bigbasket: '#84C225',
  amazon: '#FF9900',
  flipkart: '#2874F0',
  jiomart: '#0078AD',
};

export function StoreBadge({ platform, name }: { platform: string; name: string }) {
  const bg = STORE_COLORS[platform] ?? colors.surfaceRaised;
  return (
    <View style={[styles.storeBadge, { backgroundColor: bg }]}>
      <Text style={styles.storeBadgeText}>{name.slice(0, 1)}</Text>
    </View>
  );
}

export function Card({ children, style }: { children: ReactNode; style?: ViewStyle }) {
  return <View style={[styles.card, style]}>{children}</View>;
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return <Text style={styles.sectionTitle}>{children}</Text>;
}

export function Button({
  title,
  onPress,
  kind = 'primary',
  disabled,
}: {
  title: string;
  onPress: () => void;
  kind?: 'primary' | 'secondary';
  disabled?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      style={({ pressed }) => [
        styles.button,
        kind === 'secondary' && styles.buttonSecondary,
        (pressed || disabled) && { opacity: 0.6 },
      ]}
    >
      <Text style={[styles.buttonText, kind === 'secondary' && { color: colors.text }]}>{title}</Text>
    </Pressable>
  );
}

export function Message({
  icon = 'information-circle-outline',
  title,
  body,
  action,
}: {
  icon?: string;
  title: string;
  body?: string;
  action?: ReactNode;
}) {
  return (
    <View style={styles.message}>
      <Ionicons name={icon as never} size={36} color={colors.textFaint} />
      <Text style={styles.messageTitle}>{title}</Text>
      {body ? <Text style={styles.messageBody}>{body}</Text> : null}
      {action}
    </View>
  );
}

export function Loading() {
  return (
    <View style={styles.message}>
      <ActivityIndicator color={colors.accent} />
    </View>
  );
}

export const styles = StyleSheet.create({
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radius.pill,
    alignSelf: 'flex-start',
  },
  pillLarge: { paddingHorizontal: 12, paddingVertical: 6, gap: 6 },
  pillText: { fontSize: 12, fontWeight: '600' },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: radius.pill,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipActive: { backgroundColor: colors.accent, borderColor: colors.accent },
  chipText: { color: colors.textMuted, fontSize: 13, fontWeight: '500' },
  chipTextActive: { color: colors.accentText, fontWeight: '700' },
  storeBadge: { width: 32, height: 32, borderRadius: radius.sm, alignItems: 'center', justifyContent: 'center' },
  storeBadgeText: { color: '#fff', fontWeight: '800', fontSize: 15 },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: space(4),
    borderWidth: 1,
    borderColor: colors.border,
    gap: space(2),
  },
  sectionTitle: {
    color: colors.textMuted,
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 1,
    textTransform: 'uppercase',
    marginTop: space(5),
    marginBottom: space(2),
  },
  button: {
    backgroundColor: colors.accent,
    borderRadius: radius.md,
    paddingVertical: 14,
    alignItems: 'center',
  },
  buttonSecondary: { backgroundColor: colors.surfaceRaised },
  buttonText: { color: colors.accentText, fontWeight: '700', fontSize: 16 },
  message: { alignItems: 'center', justifyContent: 'center', padding: space(8), gap: space(2) },
  messageTitle: { color: colors.text, fontSize: 16, fontWeight: '600', textAlign: 'center' },
  messageBody: { color: colors.textMuted, fontSize: 14, textAlign: 'center', lineHeight: 20 },
});
