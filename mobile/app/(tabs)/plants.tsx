import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  TextInput,
  RefreshControl,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '@/hooks/useAuth';
import { usePlants } from '@/hooks/usePlants';
import { useCareTasks } from '@/hooks/useCareTasks';
import { PlantCard } from '@/components/PlantCard';
import { Colors } from '@/constants/Colors';
import type { CareTask } from '@/types';

export default function PlantsScreen() {
  const router = useRouter();
  const { user } = useAuth();
  const { plants, loading, refresh } = usePlants(user?.uid);
  const { tasks, refresh: refreshTasks } = useCareTasks(user?.uid);
  const [search, setSearch] = useState('');

  useEffect(() => { refresh(); refreshTasks(); }, []);

  const filtered = search.trim()
    ? plants.filter(
        (p) =>
          p.name.toLowerCase().includes(search.toLowerCase()) ||
          p.species.toLowerCase().includes(search.toLowerCase()),
      )
    : plants;

  // Map plantId -> next task
  const nextTaskMap = tasks.reduce<Record<string, CareTask>>((acc, task) => {
    if (!acc[task.plantId] || task.dueDate < acc[task.plantId].dueDate) {
      acc[task.plantId] = task;
    }
    return acc;
  }, {});

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl refreshing={loading} onRefresh={() => { refresh(); refreshTasks(); }} />
        }
      >
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.title}>My Plants 🌱</Text>
          <TouchableOpacity
            style={styles.addBtn}
            onPress={() => router.push('/plant/add')}
          >
            <Text style={styles.addBtnText}>+ Add</Text>
          </TouchableOpacity>
        </View>

        {/* Search */}
        <TextInput
          style={styles.searchInput}
          value={search}
          onChangeText={setSearch}
          placeholder="Search plants..."
          placeholderTextColor={Colors.textMuted}
          clearButtonMode="while-editing"
        />

        {/* Plant grid */}
        {filtered.length === 0 && !loading ? (
          <View style={styles.emptyState}>
            {plants.length === 0 ? (
              <>
                <Text style={styles.emptyEmoji}>🌱</Text>
                <Text style={styles.emptyTitle}>No plants yet</Text>
                <Text style={styles.emptyText}>Add your first plant to get started.</Text>
                <TouchableOpacity
                  style={styles.addFirstBtn}
                  onPress={() => router.push('/plant/add')}
                >
                  <Text style={styles.addFirstBtnText}>Add a Plant</Text>
                </TouchableOpacity>
              </>
            ) : (
              <>
                <Text style={styles.emptyEmoji}>🔍</Text>
                <Text style={styles.emptyTitle}>No matches</Text>
              </>
            )}
          </View>
        ) : (
          filtered.map((plant) => (
            <PlantCard
              key={plant.id}
              plant={plant}
              nextTask={nextTaskMap[plant.id]}
              onPress={() => router.push(`/plant/${plant.id}`)}
            />
          ))
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe:    { flex: 1, backgroundColor: Colors.background },
  scroll:  { flex: 1 },
  content: { padding: 20, paddingBottom: 40 },
  header:  { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  title:   { fontSize: 24, fontWeight: '800', color: Colors.text },
  addBtn:  { backgroundColor: Colors.primary, borderRadius: 20, paddingHorizontal: 16, paddingVertical: 8 },
  addBtnText: { color: '#fff', fontWeight: '700', fontSize: 14 },
  searchInput: {
    backgroundColor: Colors.surface,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 10,
    fontSize: 15,
    color: Colors.text,
    borderWidth: 1,
    borderColor: Colors.border,
    marginBottom: 16,
  },
  emptyState: { alignItems: 'center', paddingTop: 60 },
  emptyEmoji: { fontSize: 48 },
  emptyTitle: { fontSize: 18, fontWeight: '700', color: Colors.text, marginTop: 12 },
  emptyText:  { fontSize: 14, color: Colors.textSecondary, marginTop: 4, textAlign: 'center' },
  addFirstBtn: {
    marginTop: 20,
    backgroundColor: Colors.primary,
    borderRadius: 20,
    paddingHorizontal: 24,
    paddingVertical: 12,
  },
  addFirstBtnText: { color: '#fff', fontWeight: '700', fontSize: 15 },
});
