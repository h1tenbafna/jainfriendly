// One dark theme. Our own palette: deep green-black with a saffron accent.
export const colors = {
  bg: '#0B0F0D',
  surface: '#141A17',
  surfaceRaised: '#1C2420',
  border: '#26302B',
  text: '#ECF2EE',
  textMuted: '#93A39A',
  textFaint: '#5F6E66',
  accent: '#F2A93B', // saffron
  accentText: '#1A1203',
  link: '#7CC4A0',
  danger: '#F06C5B',
};

export const verdictStyle: Record<string, { label: string; short: string; fg: string; bg: string; icon: string }> = {
  friendly: { label: 'Friendly', short: 'OK', fg: '#5FD39A', bg: '#123323', icon: 'checkmark-circle' },
  likely_friendly: { label: 'Likely friendly', short: 'Likely', fg: '#B5D96A', bg: '#26301A', icon: 'checkmark-circle-outline' },
  unclear: { label: 'Unclear', short: 'Unclear', fg: '#F2C14E', bg: '#33290F', icon: 'help-circle' },
  not_friendly: { label: 'Not friendly', short: 'No', fg: '#F06C5B', bg: '#3A1714', icon: 'close-circle' },
  no_data: { label: 'No ingredient list yet', short: 'No data', fg: '#93A39A', bg: '#1C2420', icon: 'document-outline' },
};

export const space = (n: number) => n * 4;
export const radius = { sm: 8, md: 12, lg: 18, pill: 999 };
