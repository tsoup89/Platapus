import React, { useEffect, useState } from 'react';
import {
  View, Text, ScrollView, Image, TouchableOpacity,
  StyleSheet, Alert, ActivityIndicator,
} from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import * as ImagePicker from 'expo-image-picker';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '@/hooks/useAuth';
import { usePlants } from '@/hooks/usePlants';
import { Colors } from '@/constants/Colors';
import { AIAnalysisResult } from '@/components/AIAnalysisResult';
import { PestDetectionResultView } from '@/components/PestDetectionResult';
import { analyzePlantPhoto, detectPlantPests } from '@/services/claudeService';
import { updatePlant } from '@/services/plantService';
import type { AIAnalysisResult as AIResult, PestDetectionResult, ScheduleAdjustment } from '@/types';

type AnalysisMode = 'health' | 'pest';

const MODE_CONFIG = {
  health: { label: '🌿 Health Check', analyzeLabel: '🤖 Analyze Health', analyzingLabel: 'Analyzing health...' },
  pest:   { label: '🐛 Pest Scan',    analyzeLabel: '🔬 Scan for Pests', analyzingLabel: 'Scanning for pests...' },
};

export default function AnalyzeScreen() {
  const { plantId } = useLocalSearchParams<{ plantId?: string }>();
  const { user } = useAuth();
  const { plants, refresh } = usePlants(user?.uid);

  const plant = plants.find((p) => p.id === plantId);

  const [mode,       setMode]       = useState<AnalysisMode>('health');
  const [imageUri,   setImageUri]   = useState<string | null>(null);
  const [analyzing,  setAnalyzing]  = useState(false);
  const [result,     setResult]     = useState<AIResult | null>(null);
  const [pestResult, setPestResult] = useState<PestDetectionResult | null>(null);

  useEffect(() => { refresh(); }, []);

  // Switching modes clears previous results so the screen stays coherent
  function switchMode(m: AnalysisMode) {
    if (m === mode) return;
    setMode(m);
    setResult(null);
    setPestResult(null);
  }

  async function pickFromLibrary() {
    const res = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.8,
    });
    if (!res.canceled) {
      setImageUri(res.assets[0].uri);
      setResult(null);
      setPestResult(null);
    }
  }

  async function takePhoto() {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== 'granted') { Alert.alert('Camera permission required'); return; }
    const res = await ImagePicker.launchCameraAsync({ quality: 0.8 });
    if (!res.canceled) {
      setImageUri(res.assets[0].uri);
      setResult(null);
      setPestResult(null);
    }
  }

  async function handleAnalyze() {
    if (!imageUri) { Alert.alert('No photo', 'Please take or choose a photo first.'); return; }
    setAnalyzing(true);
    try {
      if (mode === 'pest') {
        const pestAnalysis = await detectPlantPests(imageUri, plant);
        setPestResult(pestAnalysis);
      } else {
        const analysis = await analyzePlantPhoto(imageUri, plant);
        setResult(analysis);

        // Persist summary to plant record
        if (plant) {
          await updatePlant(plant.id, {
            lastAnalyzed: analysis.timestamp,
            lastAnalysisNotes: analysis.summary,
            status: analysis.healthStatus === 'healthy' ? 'healthy' :
                    analysis.healthStatus === 'warning'  ? 'needs_attention' : 'sick',
          });
          await refresh();
        }
      }
    } catch (e: any) {
      Alert.alert('Analysis failed', e.message ?? 'Something went wrong. Check your API configuration.');
    } finally {
      setAnalyzing(false);
    }
  }

  async function applyScheduleAdjustments(adjustments: ScheduleAdjustment[]) {
    if (!plant) return;
    const updates: Partial<typeof plant.careProfile> = {};
    for (const adj of adjustments) {
      (updates as any)[adj.field] = adj.recommendedValue;
    }
    await updatePlant(plant.id, { careProfile: { ...plant.careProfile, ...updates } });
    await refresh();
    Alert.alert('Done! ✅', 'Care schedule updated based on AI recommendations.');
  }

  const modeConf = MODE_CONFIG[mode];

  return (
    <SafeAreaView style={styles.safe} edges={['bottom']}>
      <ScrollView style={styles.scroll} contentContainerStyle={styles.content}>

        {/* Context: which plant */}
        {plant ? (
          <View style={styles.plantContext}>
            <Text style={styles.contextEmoji}>🌱</Text>
            <View>
              <Text style={styles.contextTitle}>Analyzing: {plant.name}</Text>
              <Text style={styles.contextSpecies}>{plant.species}</Text>
            </View>
          </View>
        ) : (
          <Text style={styles.noPlantNote}>
            💡 No plant selected. Analyze any plant photo and Claude will identify it and give care advice.
          </Text>
        )}

        {/* ── Mode toggle ── */}
        <View style={styles.modeToggle}>
          {(['health', 'pest'] as AnalysisMode[]).map((m) => (
            <TouchableOpacity
              key={m}
              style={[styles.modeTab, mode === m && styles.modeTabActive]}
              onPress={() => switchMode(m)}
              activeOpacity={0.75}
            >
              <Text style={[styles.modeTabText, mode === m && styles.modeTabTextActive]}>
                {MODE_CONFIG[m].label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Mode description */}
        {mode === 'pest' && (
          <Text style={styles.modeHint}>
            🔬 Pest Scan uses a specialist AI prompt tuned for spider mites, aphids, scale, mealybugs, fungus gnats, powdery mildew, root rot, leaf spot and nutrient deficiencies.
          </Text>
        )}

        {/* Photo area */}
        {imageUri ? (
          <Image source={{ uri: imageUri }} style={styles.previewImage} />
        ) : (
          <View style={styles.photoPlaceholder}>
            <Text style={styles.placeholderEmoji}>{mode === 'pest' ? '🔬' : '📸'}</Text>
            <Text style={styles.placeholderText}>
              {mode === 'pest'
                ? 'Take a close-up photo of the affected area'
                : 'Take or choose a photo of your plant'}
            </Text>
          </View>
        )}

        {/* Photo buttons */}
        <View style={styles.photoButtons}>
          <TouchableOpacity style={styles.photoBtn} onPress={takePhoto}>
            <Text style={styles.photoBtnText}>📸 Camera</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.photoBtn} onPress={pickFromLibrary}>
            <Text style={styles.photoBtnText}>🖼️ Library</Text>
          </TouchableOpacity>
        </View>

        {/* Analyze button */}
        <TouchableOpacity
          style={[styles.analyzeBtn, mode === 'pest' && styles.analyzeBtnPest, (!imageUri || analyzing) && styles.analyzeBtnDisabled]}
          onPress={handleAnalyze}
          disabled={!imageUri || analyzing}
        >
          {analyzing ? (
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
              <ActivityIndicator color="#fff" />
              <Text style={styles.analyzeBtnText}>{modeConf.analyzingLabel}</Text>
            </View>
          ) : (
            <Text style={styles.analyzeBtnText}>{modeConf.analyzeLabel}</Text>
          )}
        </TouchableOpacity>

        {/* Health results */}
        {result && mode === 'health' && (
          <View style={styles.resultContainer}>
            <Text style={styles.resultTitle}>Health Analysis</Text>
            <AIAnalysisResult
              result={result}
              onApplyAdjustments={plant ? applyScheduleAdjustments : undefined}
            />
          </View>
        )}

        {/* Pest results */}
        {pestResult && mode === 'pest' && (
          <View style={styles.resultContainer}>
            <Text style={styles.resultTitle}>Pest & Disease Scan</Text>
            <PestDetectionResultView result={pestResult} />
          </View>
        )}

      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe:    { flex: 1, backgroundColor: Colors.background },
  scroll:  { flex: 1 },
  content: { padding: 20, paddingBottom: 40 },

  plantContext:   { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: Colors.primaryPastel, borderRadius: 14, padding: 14, marginBottom: 16 },
  contextEmoji:   { fontSize: 32 },
  contextTitle:   { fontSize: 15, fontWeight: '700', color: Colors.primaryDark },
  contextSpecies: { fontSize: 12, color: Colors.primary, fontStyle: 'italic' },
  noPlantNote:    { backgroundColor: Colors.warningLight, borderRadius: 12, padding: 14, fontSize: 13, color: Colors.warning, marginBottom: 16, lineHeight: 20 },

  // Mode toggle
  modeToggle:        { flexDirection: 'row', backgroundColor: Colors.surfaceSecondary, borderRadius: 14, padding: 4, marginBottom: 12, gap: 4 },
  modeTab:           { flex: 1, paddingVertical: 10, borderRadius: 11, alignItems: 'center' },
  modeTabActive:     { backgroundColor: Colors.surface, shadowColor: '#000', shadowOpacity: 0.08, shadowRadius: 4, shadowOffset: { width: 0, height: 2 }, elevation: 2 },
  modeTabText:       { fontSize: 13, fontWeight: '600', color: Colors.textMuted },
  modeTabTextActive: { color: Colors.text },
  modeHint:          { fontSize: 12, color: Colors.textMuted, backgroundColor: Colors.surfaceSecondary, borderRadius: 10, padding: 12, marginBottom: 12, lineHeight: 18 },

  previewImage:     { width: '100%', height: 260, borderRadius: 16, marginBottom: 16 },
  photoPlaceholder: { height: 200, borderRadius: 16, backgroundColor: Colors.surfaceSecondary, alignItems: 'center', justifyContent: 'center', marginBottom: 16, borderWidth: 2, borderColor: Colors.border, borderStyle: 'dashed' },
  placeholderEmoji: { fontSize: 48 },
  placeholderText:  { fontSize: 14, color: Colors.textMuted, marginTop: 10, textAlign: 'center', paddingHorizontal: 20 },

  photoButtons: { flexDirection: 'row', gap: 10, marginBottom: 16 },
  photoBtn:     { flex: 1, backgroundColor: Colors.surface, borderRadius: 12, padding: 14, alignItems: 'center', borderWidth: 1, borderColor: Colors.border },
  photoBtnText: { fontSize: 14, fontWeight: '600', color: Colors.primary },

  analyzeBtn:         { backgroundColor: Colors.primary, borderRadius: 16, padding: 16, alignItems: 'center', marginBottom: 24 },
  analyzeBtnPest:     { backgroundColor: '#6a1b9a' },  // purple tint for pest mode
  analyzeBtnDisabled: { opacity: 0.5 },
  analyzeBtnText:     { color: '#fff', fontSize: 16, fontWeight: '800' },

  resultContainer: { marginTop: 8 },
  resultTitle:     { fontSize: 18, fontWeight: '800', color: Colors.text, marginBottom: 16 },
});
