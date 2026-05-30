import { useState, useCallback } from 'react';
import {
  FlatList,
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { DealCard } from '../components/DealCard';
import { useListings, useIgnoreListing, useFullPipeline } from '../api/queries';

const RATING_ORDER = ['STEAL', 'GREAT', 'GOOD', 'FAIR', 'PASS'];

export function ListingsScreen() {
  const [refreshing, setRefreshing] = useState(false);
  const { data: listings = [], isLoading, error, refetch } = useListings();
  const ignoreMutation = useIgnoreListing();
  const pipelineMutation = useFullPipeline();

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await refetch();
    setRefreshing(false);
  }, [refetch]);

  function confirmPipeline(id: number) {
    Alert.alert(
      'Full Pipeline ⚡',
      'Move to inventory, auto-price, and list on Facebook Marketplace?',
      [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Go', onPress: () => pipelineMutation.mutate(id) },
      ]
    );
  }

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
        <Text style={styles.errorTitle}>Cannot reach backend</Text>
        <Text style={styles.errorSub}>Check Settings → Backend URL</Text>
      </View>
    );
  }

  const sorted = [...listings].sort((a, b) => {
    const ai = RATING_ORDER.indexOf(a.deal_score?.rating ?? 'PASS');
    const bi = RATING_ORDER.indexOf(b.deal_score?.rating ?? 'PASS');
    return ai - bi;
  });

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <Text style={styles.heading}>Deals</Text>
        <Text style={styles.count}>{sorted.length} live</Text>
      </View>
      <FlatList
        data={sorted}
        keyExtractor={(item) => String(item.id)}
        renderItem={({ item }) => (
          <DealCard
            listing={item}
            onIgnore={(id) => ignoreMutation.mutate(id)}
            onPipeline={confirmPipeline}
          />
        )}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor="#7c3aed"
          />
        }
        contentContainerStyle={styles.list}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text style={styles.emptyTitle}>No deals right now</Text>
            <Text style={styles.emptySub}>Pull to refresh or run scrapers</Text>
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
  errorTitle: { color: '#f87171', fontSize: 17, fontWeight: '600', marginBottom: 6 },
  errorSub: { color: '#6b7280', fontSize: 14 },
  empty: { alignItems: 'center', marginTop: 100 },
  emptyTitle: { color: '#6b7280', fontSize: 18, fontWeight: '600', marginBottom: 8 },
  emptySub: { color: '#374151', fontSize: 14 },
});
