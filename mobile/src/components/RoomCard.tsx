import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Colors } from '../constants/Colors';
import type { Room } from '../types';

interface Props {
  room: Room;
  onPress: () => void;
  onLongPress?: () => void;
}

export function RoomCard({ room, onPress, onLongPress }: Props) {
  return (
    <TouchableOpacity
      style={styles.card}
      onPress={onPress}
      onLongPress={onLongPress}
      activeOpacity={0.85}
    >
      <Text style={styles.icon}>{room.icon}</Text>
      <View style={styles.info}>
        <Text style={styles.name}>{room.name}</Text>
        <Text style={styles.count}>
          {room.plantCount} {room.plantCount === 1 ? 'plant' : 'plants'}
        </Text>
      </View>
      <Text style={styles.arrow}>›</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: Colors.surface,
    borderRadius: 14,
    padding: 16,
    marginBottom: 10,
    flexDirection: 'row',
    alignItems: 'center',
    shadowColor: Colors.shadow,
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06,
    shadowRadius: 6,
    elevation: 2,
  },
  icon:  { fontSize: 32, marginRight: 14 },
  info:  { flex: 1 },
  name:  { fontSize: 16, fontWeight: '700', color: Colors.text },
  count: { fontSize: 13, color: Colors.textSecondary, marginTop: 2 },
  arrow: { fontSize: 22, color: Colors.textMuted },
});
