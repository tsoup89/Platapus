/**
 * Claude AI service — plant photo analysis, identification, and pest detection.
 *
 * Production: calls Firebase Cloud Functions (API key never in app bundle).
 * Development: set EXPO_PUBLIC_CLAUDE_API_KEY in .env for direct calls.
 */

import * as FileSystem from 'expo-file-system';
import type { AIAnalysisResult, Plant, CareProfile, PlantDifficulty, PestDetectionResult } from '../types';

const FUNCTIONS_BASE_URL = process.env.EXPO_PUBLIC_FUNCTIONS_BASE_URL ?? '';
const DEV_CLAUDE_KEY     = process.env.EXPO_PUBLIC_CLAUDE_API_KEY ?? '';
const MODEL              = 'claude-sonnet-4-6';

export interface PlantIdentificationResult {
  species: string;
  commonName: string;
  confidence: 'high' | 'medium' | 'low';
  description: string;
  toxicToPets: boolean;
  difficulty: PlantDifficulty;
  suggestedCareProfile: Omit<CareProfile,
    'lastWatered' | 'lastFertilized' | 'lastRepotted' | 'lastTrimmed' | 'lastMisted'>;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────────────────────────

async function uriToBase64(uri: string): Promise<string> {
  return FileSystem.readAsStringAsync(uri, { encoding: FileSystem.EncodingType.Base64 });
}

async function callClaude(messages: object[]): Promise<string> {
  const response = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'x-api-key':         DEV_CLAUDE_KEY,
      'anthropic-version': '2023-06-01',
      'content-type':      'application/json',
    },
    body: JSON.stringify({ model: MODEL, max_tokens: 1500, messages }),
  });
  if (!response.ok) throw new Error(`Claude API ${response.status}: ${await response.text()}`);
  const data = await response.json();
  return data.content?.[0]?.text ?? '{}';
}

async function callFunction(endpoint: string, body: object): Promise<object> {
  const url = `${FUNCTIONS_BASE_URL}/${endpoint}`;
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`Function error ${response.status}: ${await response.text()}`);
  return response.json();
}

// ─── Analyze plant health ─────────────────────────────────────────────────────────────────────────────

function buildAnalyzePrompt(plant?: Plant): string {
  const context = plant
    ? `Plant: ${plant.name} (${plant.species}). Watering: every ${plant.careProfile.wateringFrequencyDays} days.`
    : 'No plant context. Identify the species if possible.';
  return `You are an expert botanist. Analyze this houseplant photo.
${context}

Return ONLY this JSON:
{
  "healthStatus": "healthy"|"warning"|"critical",
  "identifiedSpecies": string|null,
  "summary": "2-3 sentences for a beginner",
  "issues": [{"type":string,"severity":"low"|"medium"|"high","description":string}],
  "recommendations": [{"action":string,"priority":"low"|"medium"|"high","reason":string}],
  "scheduleAdjustments": [{"field":"wateringFrequencyDays"|"fertilizingFrequencyDays"|"trimmingFrequencyDays"|"mistingFrequencyDays","label":string,"currentValue":number|null,"recommendedValue":number,"unit":"days","reason":string}]
}`;
}

export async function analyzePlantPhoto(
  imageUri: string,
  plant?: Plant,
): Promise<AIAnalysisResult> {
  const base64 = await uriToBase64(imageUri);
  let result: AIAnalysisResult;

  if (FUNCTIONS_BASE_URL) {
    result = await callFunction('analyzePlant', {
      imageBase64: base64, mimeType: 'image/jpeg',
      plantContext: plant ? { name: plant.name, species: plant.species, careProfile: plant.careProfile } : null,
    }) as AIAnalysisResult;
  } else {
    const text = await callClaude([{
      role: 'user',
      content: [
        { type: 'image', source: { type: 'base64', media_type: 'image/jpeg', data: base64 } },
        { type: 'text', text: buildAnalyzePrompt(plant) },
      ],
    }]);
    result = JSON.parse(text);
  }

  return { ...result, timestamp: new Date().toISOString() };
}

// ─── Pest & Disease Detection ─────────────────────────────────────────────────────────────────────

const PEST_DETECTION_PROMPT = `You are an expert plant pathologist and entomologist specializing in houseplants.
Carefully examine this photo for any signs of pests, disease, or nutrient deficiencies.

Look specifically for:
PESTS: spider mites (fine webbing, stippled/bronzed leaves), aphids (soft clusters on new growth/stem tips), fungus gnats (soil surface, weak seedlings), scale insects (waxy brown/tan bumps on stems), mealybugs (white cottony masses in leaf axils), thrips (silvery streaking, distorted leaves), whiteflies (white cloud when leaf disturbed)
DISEASES: root rot (yellowing + mushy stem base), powdery mildew (white powder on leaf surface), leaf spot (brown/black spots with yellow halo), botrytis/grey mold (fuzzy grey growth on dying tissue), rust (orange/brown pustules on undersides)
DEFICIENCIES: overall yellowing (nitrogen), young leaves yellow/old green (iron), yellowing between veins (magnesium), purple tint on undersides (phosphorus)

If the plant looks completely healthy with no signs of any issue, say so clearly and return an empty issues array.

Return ONLY valid JSON (no markdown, no extra text):
{
  "overallSeverity": "clean"|"warning"|"infestation",
  "summary": "2-3 beginner-friendly sentences describing what you see",
  "quarantineRecommended": boolean,
  "immediateActions": ["concrete step 1", "concrete step 2"],
  "issues": [
    {
      "name": "Spider mites",
      "type": "pest"|"disease"|"deficiency",
      "confidence": "high"|"medium"|"low",
      "severity": "low"|"medium"|"high",
      "symptoms": "what is specifically visible in this photo",
      "treatment": "step-by-step treatment, mention products if helpful (e.g. neem oil, insecticidal soap)",
      "prevention": "how to prevent this from happening again"
    }
  ]
}`;

export async function detectPlantPests(
  imageUri: string,
  plant?: Plant,
): Promise<PestDetectionResult> {
  const base64 = await uriToBase64(imageUri);
  let result: PestDetectionResult;

  if (FUNCTIONS_BASE_URL) {
    result = await callFunction('detectPests', {
      imageBase64:  base64,
      mimeType:     'image/jpeg',
      plantName:    plant?.name,
      plantSpecies: plant?.species,
    }) as PestDetectionResult;
  } else {
    const context = plant
      ? `\n\nPlant context: ${plant.name} (${plant.species}).`
      : '';
    const text = await callClaude([{
      role: 'user',
      content: [
        { type: 'image', source: { type: 'base64', media_type: 'image/jpeg', data: base64 } },
        { type: 'text', text: PEST_DETECTION_PROMPT + context },
      ],
    }]);
    result = JSON.parse(text);
  }

  return { ...result, timestamp: new Date().toISOString() };
}

// ─── Identify unknown plant ─────────────────────────────────────────────────────────────────────────────

const IDENTIFY_PROMPT = `You are an expert botanist. Identify this houseplant.

Return ONLY this JSON (no markdown, no extra text):
{
  "species": "scientific name",
  "commonName": "common English name",
  "confidence": "high"|"medium"|"low",
  "description": "1-2 sentences about this plant",
  "toxicToPets": boolean,
  "difficulty": "easy"|"medium"|"hard",
  "suggestedCareProfile": {
    "wateringFrequencyDays": number,
    "lightRequirement": "low"|"medium"|"high"|"direct",
    "humidityRequirement": "low"|"medium"|"high",
    "fertilizingFrequencyDays": number,
    "repottingFrequencyMonths": number,
    "trimmingFrequencyDays": number or null,
    "mistingFrequencyDays": number or null
  }
}`;

export async function identifyPlantFromPhoto(
  imageUri: string,
): Promise<PlantIdentificationResult> {
  const base64 = await uriToBase64(imageUri);
  let result: PlantIdentificationResult;

  if (FUNCTIONS_BASE_URL) {
    result = await callFunction('identifyPlant', {
      imageBase64: base64,
      mimeType: 'image/jpeg',
    }) as PlantIdentificationResult;
  } else {
    const text = await callClaude([{
      role: 'user',
      content: [
        { type: 'image', source: { type: 'base64', media_type: 'image/jpeg', data: base64 } },
        { type: 'text', text: IDENTIFY_PROMPT },
      ],
    }]);
    result = JSON.parse(text);
  }

  // Ensure null values become undefined
  if (result.suggestedCareProfile) {
    const cp = result.suggestedCareProfile as any;
    if (!cp.trimmingFrequencyDays)  delete cp.trimmingFrequencyDays;
    if (!cp.mistingFrequencyDays)   delete cp.mistingFrequencyDays;
  }

  return result;
}
