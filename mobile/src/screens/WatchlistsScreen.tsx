import {
  FlatList,
  View,
  Text,
  Switch,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useWatchlists, useToggleWatchlist } from '../api/queries';

export function WatchlistsScreen() {
  const { data: watchlists = [], isLoading, error } = useWatchlists();
  const toggleMutation = useToggleWatchlist();

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
        <Text style={styles.heading}>Watchlists</Text>
      </View>
      <FlatList
        data={watchlists}
        keyExtractor={(item) => String(item.id)}
        renderItem={({ item }) => (
          <View style={styles.card}>
            <View style={styles.cardBody}>
              <Text style={styles.name}>{item.name}</Text>
              {item.keywords.length > 0 && (
                <Text style={styles.keywords} numberOfLines={1}>
                  {item.keywords.slice(0, 4).join(', ')}
                  {item.keywords.length > 4 ? ` +${item.keywords.length - 4}` : ''}
                </Text>
              )}
              <View style={styles.badges}>
                {item.category ? (
                  <View style={styles.badge}>
                    <Text style={styles.badgeText}>{item.category}</Text>
                  </View>
                ) : null}
                <View style={styles.badge}>
                  <Text style={styles.badgeText}>Every {item.run_frequency_minutes}m</Text>
                </View>
                <View style={styles.badge}>
                  <Text style={styles.badgeText}>{item.min_rating_to_alert}+</Text>
                </View>
              </View>
            </View>
            <Switch
              value={item.enabled}
              onValueChange={() => toggleMutation.mutate(item.id)}
              trackColor={{ false: '#2d2d42', true: '#5b21b6' }}
              thumbColor="#fff"
            />
          </View>
        )}
        contentContainerStyle={styles.list}
        ListEmptyComponent={
          <View style={styles.center}>
            <Text style={styles.errorText}>No watchlists configured</Text>
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
    minHeight: 200,
  },
  header: { paddingHorizontal: 16, paddingVertical: 14 },
  heading: { fontSize: 30, fontWeight: '800', color: '#fff' },
  list: { paddingBottom: 24 },
  card: {
    backgroundColor: '#1e1e2e',
    borderRadius: 14,
    marginHorizontal: 16,
    marginVertical: 6,
    padding: 16,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  cardBody: { flex: 1, marginRight: 14 },
  name: { fontSize: 16, fontWeight: '700', color: '#fff', marginBottom: 4 },
  keywords: { fontSize: 13, color: '#6b7280', marginBottom: 8 },
  badges: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  badge: {
    backgroundColor: '#2d2d42',
    borderRadius: 8,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  badgeText: { color: '#9ca3af', fontSize: 11 },
  errorText: { color: '#6b7280', fontSize: 16 },
});
