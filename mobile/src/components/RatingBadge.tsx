import { View, Text, StyleSheet } from 'react-native';

const PALETTE: Record<string, { bg: string; label: string }> = {
  STEAL: { bg: '#dc2626', label: '#fff' },
  GREAT: { bg: '#16a34a', label: '#fff' },
  GOOD:  { bg: '#2563eb', label: '#fff' },
  FAIR:  { bg: '#d97706', label: '#fff' },
  PASS:  { bg: '#4b5563', label: '#fff' },
};

export function RatingBadge({ rating }: { rating: string }) {
  const c = PALETTE[rating] ?? PALETTE.PASS;
  return (
    <View style={[styles.badge, { backgroundColor: c.bg }]}>
      <Text style={[styles.text, { color: c.label }]}>{rating}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 12,
  },
  text: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
});
