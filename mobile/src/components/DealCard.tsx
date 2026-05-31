import { View, Text, Image, TouchableOpacity, StyleSheet, Linking } from 'react-native';
import { RatingBadge } from './RatingBadge';
import type { Listing } from '../types';

interface Props {
  listing: Listing;
  onIgnore: (id: number) => void;
  onPipeline: (id: number) => void;
}

export function DealCard({ listing, onIgnore, onPipeline }: Props) {
  const score = listing.deal_score;
  const rating = score?.rating ?? 'PASS';

  return (
    <View style={styles.card}>
      <View style={styles.top}>
        {listing.image_url ? (
          <Image source={{ uri: listing.image_url }} style={styles.thumb} />
        ) : (
          <View style={[styles.thumb, styles.thumbEmpty]} />
        )}
        <View style={styles.info}>
          <View style={styles.tagRow}>
            <RatingBadge rating={rating} />
            <Text style={styles.source}>{listing.source}</Text>
          </View>
          <Text style={styles.title} numberOfLines={2}>
            {listing.title}
          </Text>
          <View style={styles.priceRow}>
            {listing.price != null && (
              <Text style={styles.price}>${listing.price.toFixed(0)}</Text>
            )}
            {score?.estimated_profit != null && (
              <Text style={styles.profit}>
                Est. profit ${score.estimated_profit.toFixed(0)}
              </Text>
            )}
          </View>
          {listing.location ? (
            <Text style={styles.location}>{listing.location}</Text>
          ) : null}
        </View>
      </View>

      <View style={styles.actions}>
        <TouchableOpacity
          style={styles.btnSecondary}
          onPress={() => onIgnore(listing.id)}
        >
          <Text style={styles.btnSecondaryText}>Ignore</Text>
        </TouchableOpacity>

        {listing.url ? (
          <TouchableOpacity
            style={styles.btnSecondary}
            onPress={() => Linking.openURL(listing.url!)}
          >
            <Text style={styles.btnSecondaryText}>View</Text>
          </TouchableOpacity>
        ) : null}

        <TouchableOpacity
          style={styles.btnPrimary}
          onPress={() => onPipeline(listing.id)}
        >
          <Text style={styles.btnPrimaryText}>⚡ Pipeline</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#1e1e2e',
    borderRadius: 14,
    marginHorizontal: 16,
    marginVertical: 6,
    padding: 14,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.4,
    shadowRadius: 6,
    elevation: 4,
  },
  top: { flexDirection: 'row', gap: 12 },
  thumb: { width: 80, height: 80, borderRadius: 10 },
  thumbEmpty: { backgroundColor: '#2d2d42' },
  info: { flex: 1, gap: 5 },
  tagRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  source: { fontSize: 11, color: '#666', textTransform: 'capitalize' },
  title: { fontSize: 14, fontWeight: '600', color: '#f0f0f0', lineHeight: 20 },
  priceRow: { flexDirection: 'row', alignItems: 'baseline', gap: 10 },
  price: { fontSize: 20, fontWeight: '800', color: '#fff' },
  profit: { fontSize: 13, color: '#22c55e', fontWeight: '600' },
  location: { fontSize: 12, color: '#666' },
  actions: { flexDirection: 'row', marginTop: 12, gap: 8 },
  btnSecondary: {
    flex: 1,
    paddingVertical: 8,
    borderRadius: 8,
    backgroundColor: '#2d2d42',
    alignItems: 'center',
  },
  btnSecondaryText: { color: '#999', fontSize: 13, fontWeight: '600' },
  btnPrimary: {
    flex: 1,
    paddingVertical: 8,
    borderRadius: 8,
    backgroundColor: '#5b21b6',
    alignItems: 'center',
  },
  btnPrimaryText: { color: '#fff', fontSize: 13, fontWeight: '700' },
});
