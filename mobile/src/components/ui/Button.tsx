import React from 'react';
import {
  TouchableOpacity,
  Text,
  ActivityIndicator,
  StyleSheet,
  type ViewStyle,
  type TextStyle,
} from 'react-native';
import { Colors } from '../../constants/Colors';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
type Size    = 'sm' | 'md' | 'lg';

interface Props {
  label: string;
  onPress: () => void;
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  disabled?: boolean;
  icon?: string;   // Emoji prefix
  style?: ViewStyle;
}

export function Button({
  label,
  onPress,
  variant = 'primary',
  size    = 'md',
  loading = false,
  disabled = false,
  icon,
  style,
}: Props) {
  const containerStyle = [
    styles.base,
    styles[`variant_${variant}`],
    styles[`size_${size}`],
    (disabled || loading) && styles.disabled,
    style,
  ];

  const textStyle: TextStyle[] = [
    styles.label,
    styles[`label_${variant}`],
    styles[`labelSize_${size}`],
  ];

  return (
    <TouchableOpacity
      style={containerStyle}
      onPress={onPress}
      disabled={disabled || loading}
      activeOpacity={0.8}
    >
      {loading ? (
        <ActivityIndicator color={variant === 'primary' ? '#fff' : Colors.primary} />
      ) : (
        <Text style={textStyle}>
          {icon ? `${icon}  ` : ''}{label}
        </Text>
      )}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  base: {
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
  },
  disabled: { opacity: 0.5 },

  variant_primary:   { backgroundColor: Colors.primary },
  variant_secondary: { backgroundColor: Colors.primaryPastel, borderWidth: 1, borderColor: Colors.border },
  variant_ghost:     { backgroundColor: 'transparent' },
  variant_danger:    { backgroundColor: Colors.error },

  size_sm: { paddingHorizontal: 12, paddingVertical: 8,  minWidth: 80  },
  size_md: { paddingHorizontal: 20, paddingVertical: 12, minWidth: 120 },
  size_lg: { paddingHorizontal: 24, paddingVertical: 16, minWidth: 160 },

  label:           { fontWeight: '600' },
  label_primary:   { color: Colors.textOnPrimary },
  label_secondary: { color: Colors.primary },
  label_ghost:     { color: Colors.primary },
  label_danger:    { color: '#fff' },

  labelSize_sm: { fontSize: 13 },
  labelSize_md: { fontSize: 15 },
  labelSize_lg: { fontSize: 17 },
});
