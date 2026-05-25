import React, { useEffect, useState } from 'react';
import {
  View, Text, ScrollView, TextInput, StyleSheet,
  TouchableOpacity, Image, Alert, Switch,
} from 'react-native';
import { useRouter } from 'expo-router';
import * as ImagePicker from 'expo-image-picker';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '@/hooks/useAuth';
import { usePlants } from '@/hooks/usePlants';
import { useRooms } from '@/hooks/useRooms';
import { Colors } from '@/constants/Colors';
import { Button } from '@/components/ui/Button';
import { PLANT_DATABASE, searchPlantDatabase } from '@/constants/PlantDatabase';
import type { CareProfile, PlantTemplate } from '@/types';

export default function AddPlantScreen() {
  const router = useRouter();
  const { user } = useAuth();
  const { add }  = usePlants(user?.uid);
  const { rooms, refresh: refreshRooms } = useRooms(user?.uid);

  const [photoUri, setPhotoUri] = useState<string | null>(null);
  const [name,     setName]     = useState('');
  const [species,  setSpecies]  = useState('');
  const [roomId,   setRoomId]   = useState('');
  const [notes,    setNotes]    = useState('');
  const [saving,   setSaving]   = useState(false);

  // Care profile state
  const [waterDays,    setWaterDays]    = useState('7');
  const [fertilizeDays,setFertilizeDays]= useState('30');
  const [repotMonths,  setRepotMonths]  = useState('18');
  const [trimDays,     setTrimDays]     = useState('');
  const [light,        setLight]        = useState<CareProfile['lightRequirement']>('medium');
  const [humidity,     setHumidity]     = useState<CareProfile['humidityRequirement']>('medium');

  const [templateSearch, setTemplateSearch] = useState('');
  const [showTemplates,  setShowTemplates]  = useState(false);

  useEffect(() => { refreshRooms(); }, []);

  function applyTemplate(t: PlantTemplate) {
    setSpecies(t.species);
    if (!name) setName(t.commonName);
    setWaterDays(String(t.defaultCareProfile.wateringFrequencyDays));
    setLight(t.defaultCareProfile.lightRequirement);
    setHumidity(t.defaultCareProfile.humidityRequirement);
    if (t.defaultCareProfile.fertilizingFrequencyDays)
      setFertilizeDays(String(t.defaultCareProfile.fertilizingFrequencyDays));
    if (t.defaultCareProfile.repottingFrequencyMonths)
      setRepotMonths(String(t.defaultCareProfile.repottingFrequencyMonths));
    if (t.defaultCareProfile.trimmingFrequencyDays)
      setTrimDays(String(t.defaultCareProfile.trimmingFrequencyDays));
    setShowTemplates(false);
    setTemplateSearch('');
  }

  async function pickPhoto() {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.7,
      allowsEditing: true,
      aspect: [4, 3],
    });
    if (!result.canceled) setPhotoUri(result.assets[0].uri);
  }

  async function takePhoto() {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== 'granted') { Alert.alert('Camera permission required'); return; }
    const result = await ImagePicker.launchCameraAsync({
      quality: 0.7,
      allowsEditing: true,
      aspect: [4, 3],
    });
    if (!result.canceled) setPhotoUri(result.assets[0].uri);
  }

  async function handleSave() {
    if (!name.trim())    { Alert.alert('Name required', 'Give your plant a name.'); return; }
    if (!species.trim()) { Alert.alert('Species required', 'Enter the plant species.'); return; }
    if (!roomId)         { Alert.alert('Room required', 'Choose a room for this plant.'); return; }
    if (!waterDays || Number(waterDays) < 1) { Alert.alert('Invalid watering', 'Enter a valid watering frequency.'); return; }

    setSaving(true);
    try {
      const roomName = rooms.find((r) => r.id === roomId)?.name;
      const careProfile: CareProfile = {
        wateringFrequencyDays: Number(waterDays),
        lightRequirement:      light,
        humidityRequirement:   humidity,
        fertilizingFrequencyDays: fertilizeDays ? Number(fertilizeDays) : undefined,
        repottingFrequencyMonths: repotMonths   ? Number(repotMonths)   : undefined,
        trimmingFrequencyDays:    trimDays      ? Number(trimDays)      : undefined,
      };
      await add(
        { name: name.trim(), species: species.trim(), roomId, roomName, notes: notes.trim(), careProfile },
        photoUri ?? undefined,
      );
      router.back();
    } catch (e: any) {
      Alert.alert('Error', e.message);
    } finally {
      setSaving(false);
    }
  }

  const matchedTemplates = templateSearch.trim()
    ? searchPlantDatabase(templateSearch)
    : PLANT_DATABASE.slice(0, 6);

  const LIGHT_OPTIONS: CareProfile['lightRequirement'][] = ['low', 'medium', 'high', 'direct'];
  const LIGHT_LABELS: Record<string, string> = { low: 'Low', medium: 'Indirect', high: 'Bright', direct: 'Direct sun' };

  return (
    <SafeAreaView style={styles.safe} edges={['bottom']}>
      <ScrollView style={styles.scroll} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">

        {/* Photo picker */}
        <View style={styles.photoRow}>
          {photoUri ? (
            <Image source={{ uri: photoUri }} style={styles.photoPreview} />
          ) : (
            <View style={styles.photoPlaceholder}>
              <Text style={{ fontSize: 40 }}>📷</Text>
            </View>
          )}
          <View style={styles.photoButtons}>
            <TouchableOpacity style={styles.photoBtn} onPress={takePhoto}>
              <Text style={styles.photoBtnText}>📸 Take Photo</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.photoBtn} onPress={pickPhoto}>
              <Text style={styles.photoBtnText}>🖼️ Choose from Library</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Quick-fill from plant database */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Quick-fill from plant database</Text>
          <TextInput
            style={styles.input}
            value={templateSearch}
            onChangeText={(t) => { setTemplateSearch(t); setShowTemplates(true); }}
            onFocus={() => setShowTemplates(true)}
            placeholder="Search common plants..."
            placeholderTextColor={Colors.textMuted}
          />
          {showTemplates && (
            <View style={styles.templateList}>
              {matchedTemplates.map((t) => (
                <TouchableOpacity
                  key={t.species}
                  style={styles.templateRow}
                  onPress={() => applyTemplate(t)}
                >
                  <Text style={styles.templateEmoji}>{t.emoji}</Text>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.templateName}>{t.commonName}</Text>
                    <Text style={styles.templateSpecies}>{t.species}</Text>
                  </View>
                  <View style={styles.difficultyBadge}>
                    <Text style={styles.difficultyText}>{t.difficulty}</Text>
                  </View>
                </TouchableOpacity>
              ))}
            </View>
          )}
        </View>

        {/* Basic info */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Plant Info</Text>
          <Field label="Nickname *">
            <TextInput style={styles.input} value={name} onChangeText={setName} placeholder="e.g. Big leafy boi" placeholderTextColor={Colors.textMuted} />
          </Field>
          <Field label="Species *">
            <TextInput style={styles.input} value={species} onChangeText={setSpecies} placeholder="e.g. Monstera deliciosa" placeholderTextColor={Colors.textMuted} />
          </Field>
          <Field label="Room *">
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: 4 }}>
              {rooms.map((r) => (
                <TouchableOpacity
                  key={r.id}
                  style={[styles.chip, roomId === r.id && styles.chipSelected]}
                  onPress={() => setRoomId(r.id)}
                >
                  <Text style={[styles.chipText, roomId === r.id && styles.chipTextSelected]}>
                    {r.icon} {r.name}
                  </Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
          </Field>
          <Field label="Notes">
            <TextInput
              style={[styles.input, { height: 72, textAlignVertical: 'top' }]}
              value={notes}
              onChangeText={setNotes}
              placeholder="Any notes about this plant..."
              placeholderTextColor={Colors.textMuted}
              multiline
            />
          </Field>
        </View>

        {/* Care schedule */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Care Schedule</Text>
          <Field label="Water every (days) *">
            <TextInput style={styles.input} value={waterDays} onChangeText={setWaterDays} keyboardType="number-pad" placeholder="7" placeholderTextColor={Colors.textMuted} />
          </Field>
          <Field label="Light requirement">
            <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
              {LIGHT_OPTIONS.map((opt) => (
                <TouchableOpacity
                  key={opt}
                  style={[styles.chip, light === opt && styles.chipSelected]}
                  onPress={() => setLight(opt)}
                >
                  <Text style={[styles.chipText, light === opt && styles.chipTextSelected]}>{LIGHT_LABELS[opt]}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </Field>
          <Field label="Fertilize every (days)">
            <TextInput style={styles.input} value={fertilizeDays} onChangeText={setFertilizeDays} keyboardType="number-pad" placeholder="30" placeholderTextColor={Colors.textMuted} />
          </Field>
          <Field label="Repot every (months)">
            <TextInput style={styles.input} value={repotMonths} onChangeText={setRepotMonths} keyboardType="number-pad" placeholder="18" placeholderTextColor={Colors.textMuted} />
          </Field>
          <Field label="Trim every (days, optional)">
            <TextInput style={styles.input} value={trimDays} onChangeText={setTrimDays} keyboardType="number-pad" placeholder="Leave blank if not needed" placeholderTextColor={Colors.textMuted} />
          </Field>
        </View>

        <Button label="Save Plant" icon="🌱" onPress={handleSave} loading={saving} size="lg" />
        <View style={{ height: 20 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <View style={{ marginBottom: 14 }}>
      <Text style={styles.fieldLabel}>{label}</Text>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  safe:   { flex: 1, backgroundColor: Colors.background },
  scroll: { flex: 1 },
  content:{ padding: 16, paddingBottom: 40 },
  photoRow: { flexDirection: 'row', gap: 12, marginBottom: 16, alignItems: 'center' },
  photoPreview:    { width: 100, height: 100, borderRadius: 16 },
  photoPlaceholder:{ width: 100, height: 100, borderRadius: 16, backgroundColor: Colors.primaryPastel, alignItems: 'center', justifyContent: 'center' },
  photoButtons:    { flex: 1, gap: 8 },
  photoBtn:        { backgroundColor: Colors.surfaceSecondary, borderRadius: 10, padding: 10, borderWidth: 1, borderColor: Colors.border },
  photoBtnText:    { fontSize: 13, color: Colors.primary, fontWeight: '600' },
  section: { backgroundColor: Colors.surface, borderRadius: 16, padding: 16, marginBottom: 16, shadowColor: Colors.shadow, shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.06, shadowRadius: 6, elevation: 2 },
  sectionTitle:    { fontSize: 14, fontWeight: '700', color: Colors.textSecondary, marginBottom: 14, textTransform: 'uppercase', letterSpacing: 0.6 },
  fieldLabel:      { fontSize: 13, fontWeight: '600', color: Colors.textSecondary, marginBottom: 6 },
  input:           { borderWidth: 1, borderColor: Colors.border, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontSize: 14, color: Colors.text, backgroundColor: Colors.background },
  chip:            { borderWidth: 1, borderColor: Colors.border, borderRadius: 20, paddingHorizontal: 12, paddingVertical: 6, marginRight: 6 },
  chipSelected:    { backgroundColor: Colors.primary, borderColor: Colors.primary },
  chipText:        { fontSize: 13, color: Colors.textSecondary },
  chipTextSelected:{ color: '#fff', fontWeight: '700' },
  templateList:    { marginTop: 4, borderWidth: 1, borderColor: Colors.border, borderRadius: 12, overflow: 'hidden' },
  templateRow:     { flexDirection: 'row', alignItems: 'center', padding: 12, gap: 10, borderBottomWidth: 1, borderBottomColor: Colors.borderLight },
  templateEmoji:   { fontSize: 24 },
  templateName:    { fontSize: 14, fontWeight: '700', color: Colors.text },
  templateSpecies: { fontSize: 11, color: Colors.textMuted, fontStyle: 'italic' },
  difficultyBadge: { backgroundColor: Colors.surfaceSecondary, borderRadius: 8, paddingHorizontal: 8, paddingVertical: 3 },
  difficultyText:  { fontSize: 11, color: Colors.textSecondary, fontWeight: '600' },
});
