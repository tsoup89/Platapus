export const Colors = {
  // Brand greens
  primary:         '#2d7a47',
  primaryLight:    '#4a9e65',
  primaryDark:     '#1a5e3a',
  primaryPastel:   '#e8f5ee',

  // Accent (warm terracotta for pots!)
  accent:          '#e07a5f',
  accentLight:     '#f4b8a8',

  // Surfaces
  background:      '#f7faf8',
  surface:         '#ffffff',
  surfaceSecondary:'#f0f7f3',

  // Text
  text:            '#1a2e25',
  textSecondary:   '#4e6e5d',
  textMuted:       '#8fa898',
  textOnPrimary:   '#ffffff',

  // Borders
  border:          '#d4e6da',
  borderLight:     '#eaf3ec',

  // Semantic
  error:           '#c0392b',
  errorLight:      '#fde8e6',
  warning:         '#e8930a',
  warningLight:    '#fef6e4',
  success:         '#27ae60',
  successLight:    '#e8f8ef',

  // Care task type colors
  water:           '#3d9dd9',
  waterLight:      '#e3f4fc',
  fertilize:       '#7cb83e',
  fertilizeLight:  '#f0f8e6',
  repot:           '#a0785a',
  repotLight:      '#f5ede8',
  trim:            '#5aad6f',
  trimLight:       '#e8f6eb',
  mist:            '#5bc8d4',
  mistLight:       '#e2f8fa',
  custom:          '#9b59b6',
  customLight:     '#f4edf9',

  // Plant status
  healthy:         '#27ae60',
  needsAttention:  '#e8930a',
  sick:            '#c0392b',

  // Tab bar
  tabBar:          '#ffffff',
  tabBarIcon:      '#8fa898',
  tabBarIconActive:'#2d7a47',

  // Shadow
  shadow:          '#000000',
} as const;

export type ColorKey = keyof typeof Colors;

// Gradient pairs [start, end]
export const Gradients = {
  primary:  ['#2d7a47', '#1a5e3a'] as [string, string],
  sunrise:  ['#e07a5f', '#c0392b'] as [string, string],
  sky:      ['#3d9dd9', '#2980b9'] as [string, string],
  earth:    ['#a0785a', '#7a5840'] as [string, string],
} as const;
