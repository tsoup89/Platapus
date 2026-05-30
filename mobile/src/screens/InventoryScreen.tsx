import {
  FlatList,
  View,
  Text,
  Image,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useListings } from '../api/queries';
import { RatingBadge } from '../components/RatingBadge';

export function InventoryScreen() {
  const { data: listings = [], isLoading, error } = useListings();

  // Proxy: alerted deals are items that cleared the quality bar
  const inventory = listings.filter((l) => l.alert_sent && !l.ignored);

  if (isLoading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#7c3aed" />
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>Cannot reach backend</Text>
      </View>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <Text style={styles.heading}>Inventory</Text>
        <Text style={styles.count}>{inventory.length} items</Text>
      </View>
      <FlatList
        data={inventory}
        keyExtractor={(item) => String(item.id)}
        renderItem={({ item }) => (
          <View style={styles.card}>
            {item.image_url ? (
              <Image source={{ uri: item.image_url }} style={styles.thumb} />
            ) : (
              <View style={[styles.thumb, styles.thumbEmpty]} />
            )}
            <View style={styles.info}>
              <Text style={styles.title} numberOfLines={2}>
                {item.title}
              </Text>
              <View style={styles.row}>
                {item.price != null && (
                  <Text style={styles.price}>${item.price.toFixed(0)}</Text>
                )}
                {item.deal_score?.estimated_profit != null && (
                  <Text style={styles.profit}>
                    +${item.deal_score.estimated_profit.toFixed(0)} est.
                  </Text>
                )}
              </View>
              <View style={styles.row}>
                <RatingBadge rating={item.deal_score?.rating ?? 'PASS'} />
                {item.location ? (
                  <Text style={styles.location}>{item.location}</Text>
                ) : null}
              </View>
            </View>
          </View>
        )}
        contentContainerStyle={styles.list}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text style={styles.emptyTitle}>No inventory yet</Text>
            <Text style={styles.emptySub}>
              Deals you get alerted on will appear here
            </Text>
          </View>
        }
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0d0d1a' },
  center: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#0d0d1a',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 14,
  },
  heading: { fontSize: 30, fontWeight: '800', color: '#fff' },
  count: { fontSize: 14, color: '#4b5563' },
  list: { paddingBottom: 24 },
  card: {
    backgroundColor: '#1e1e2e',
    borderRadius: 14,
    marginHorizontal: 16,
    marginVertical: 6,
    padding: 14,
    flexDirection: 'row',
    gap: 12,
  },
  thumb: { width: 80, height: 80, borderRadius: 10 },
  thumbEmpty: { backgroundColor: '#2d2d42' },
  info: { flex: 1, gap: 6 },
  title: { fontSize: 14, fontWeight: '600', color: '#f0f0f0', lineHeight: 20 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  price: { fontSize: 18, fontWeight: '800', color: '#fff' },
  profit: { fontSize: 13, color: '#22c55e', fontWeight: '600' },
  location: { fontSize: 12, color: '#6b7280' },
  errorText: { color: '#6b7280', fontSize: 16 },
  empty: { alignItems: 'center', marginTop: 100 },
  emptyTitle: { color: '#6b7280', fontSize: 18, fontWeight: '600', marginBottom: 8 },
  emptySub: { color: '#374151', fontSize: 14, textAlign: 'center' },
});
