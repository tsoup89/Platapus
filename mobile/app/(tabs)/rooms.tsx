import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  TextInput,
  Alert,
  Modal,
  FlatList,
  RefreshControl,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '@/hooks/useAuth';
import { useRooms } from '@/hooks/useRooms';
import { RoomCard } from '@/components/RoomCard';
import { Colors } from '@/constants/Colors';
import { DEFAULT_ROOMS } from '@/services/roomService';

const ROOM_ICONS = [
  '🛋️','🛌','🍳','🛀','💼','🌟','🌿','🌺','📚','🏡','🌈',
  '🛕','🚪','🤝','🍎','🥣','🍄','💧','☀️','🍄',
];

export default function RoomsScreen() {
  const router = useRouter();
  const { user } = useAuth();
  const { rooms, loading, refresh, add, edit, remove } = useRooms(user?.uid);

  const [modalVisible, setModalVisible] = useState(false);
  const [roomName,     setRoomName]     = useState('');
  const [roomIcon,     setRoomIcon]     = useState('🏠');
  const [saving,       setSaving]       = useState(false);

  useEffect(() => { refresh(); }, []);

  async function handleAdd() {
    if (!roomName.trim()) { Alert.alert('Name required', 'Please give the room a name.'); return; }
    setSaving(true);
    try {
      await add(roomName.trim(), roomIcon);
      setRoomName('');
      setRoomIcon('🏠');
      setModalVisible(false);
    } finally {
      setSaving(false);
    }
  }

  function handleLongPress(room: { id: string; name: string }) {
    Alert.alert(
      room.name,
      'What would you like to do?',
      [
        { text: 'Delete Room', style: 'destructive', onPress: () => remove(room.id) },
        { text: 'Cancel', style: 'cancel' },
      ],
    );
  }

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={refresh} />}
      >
        <View style={styles.header}>
          <Text style={styles.title}>Rooms 🏠</Text>
          <TouchableOpacity style={styles.addBtn} onPress={() => setModalVisible(true)}>
            <Text style={styles.addBtnText}>+ Room</Text>
          </TouchableOpacity>
        </View>

        {rooms.length === 0 && !loading ? (
          <View style={styles.emptyState}>
            <Text style={styles.emptyEmoji}>🏠</Text>
            <Text style={styles.emptyTitle}>No rooms yet</Text>
            <Text style={styles.emptyText}>Create rooms to organize your plants by location.</Text>
            {/* Seed defaults */}
            <TouchableOpacity
              style={styles.seedBtn}
              onPress={async () => {
                for (const r of DEFAULT_ROOMS) await add(r.name, r.icon);
              }}
            >
              <Text style={styles.seedBtnText}>Add Default Rooms</Text>
            </TouchableOpacity>
          </View>
        ) : (
          rooms.map((room) => (
            <RoomCard
              key={room.id}
              room={room}
              onPress={() => router.push({ pathname: '/(tabs)/plants', params: { roomId: room.id } })}
              onLongPress={() => handleLongPress(room)}
            />
          ))
        )}
      </ScrollView>

      {/* Add Room Modal */}
      <Modal
        visible={modalVisible}
        transparent
        animationType="slide"
        onRequestClose={() => setModalVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalSheet}>
            <Text style={styles.modalTitle}>New Room</Text>

            <Text style={styles.modalLabel}>Room name</Text>
            <TextInput
              style={styles.modalInput}
              value={roomName}
              onChangeText={setRoomName}
              placeholder="e.g. Living Room"
              placeholderTextColor={Colors.textMuted}
              autoFocus
            />

            <Text style={styles.modalLabel}>Icon</Text>
            <FlatList
              data={ROOM_ICONS}
              horizontal
              keyExtractor={(item) => item}
              showsHorizontalScrollIndicator={false}
              style={{ marginBottom: 20 }}
              renderItem={({ item }) => (
                <TouchableOpacity
                  style={[
                    styles.iconOption,
                    item === roomIcon && styles.iconOptionSelected,
                  ]}
                  onPress={() => setRoomIcon(item)}
                >
                  <Text style={{ fontSize: 24 }}>{item}</Text>
                </TouchableOpacity>
              )}
            />

            <View style={styles.modalActions}>
              <TouchableOpacity
                style={styles.cancelBtn}
                onPress={() => setModalVisible(false)}
              >
                <Text style={styles.cancelBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.confirmBtn, saving && { opacity: 0.6 }]}
                onPress={handleAdd}
                disabled={saving}
              >
                <Text style={styles.confirmBtnText}>Create</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
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
  emptyState: { alignItems: 'center', paddingTop: 60 },
  emptyEmoji: { fontSize: 48 },
  emptyTitle: { fontSize: 18, fontWeight: '700', color: Colors.text, marginTop: 12 },
  emptyText:  { fontSize: 14, color: Colors.textSecondary, marginTop: 4, textAlign: 'center' },
  seedBtn:    { marginTop: 20, backgroundColor: Colors.primaryPastel, borderRadius: 20, paddingHorizontal: 20, paddingVertical: 10 },
  seedBtnText:{ color: Colors.primary, fontWeight: '700' },
  // Modal
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'flex-end' },
  modalSheet:   { backgroundColor: Colors.surface, borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 24, paddingBottom: 40 },
  modalTitle:   { fontSize: 20, fontWeight: '800', color: Colors.text, marginBottom: 16 },
  modalLabel:   { fontSize: 13, fontWeight: '600', color: Colors.textSecondary, marginBottom: 6 },
  modalInput:   { borderWidth: 1, borderColor: Colors.border, borderRadius: 12, paddingHorizontal: 14, paddingVertical: 12, fontSize: 15, color: Colors.text, marginBottom: 16 },
  iconOption:         { padding: 8, borderRadius: 12, marginRight: 8, borderWidth: 2, borderColor: 'transparent' },
  iconOptionSelected: { borderColor: Colors.primary, backgroundColor: Colors.primaryPastel },
  modalActions: { flexDirection: 'row', gap: 12, marginTop: 8 },
  cancelBtn:   { flex: 1, padding: 14, borderRadius: 12, borderWidth: 1, borderColor: Colors.border, alignItems: 'center' },
  cancelBtnText:{ color: Colors.textSecondary, fontWeight: '600' },
  confirmBtn:  { flex: 1, padding: 14, borderRadius: 12, backgroundColor: Colors.primary, alignItems: 'center' },
  confirmBtnText:{ color: '#fff', fontWeight: '700' },
});
