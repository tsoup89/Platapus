/**
 * Claude AI service — plant photo analysis and plant identification.
 *
 * Production: calls Firebase Cloud Functions (API key never in app bundle).
 * Development: set EXPO_PUBLIC_CLAUDE_API_KEY in .env for direct calls.
 */

import * as FileSystem from 'expo-file-system';
import type { AIAnalysisResult, Plant, CareProfile, PlantDifficulty } from '../types';

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
    body: JSON.stringify({ model: MODEL, max_tokens: 1024, messages }),
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
    "trimmingFrequencyDays": number|null,
    "mistingFrequencyDays": number|null
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
