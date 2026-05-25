/**
 * Claude AI service for plant photo analysis.
 *
 * Architecture:
 *  - In PRODUCTION: calls a Firebase Cloud Function which holds the API key securely.
 *  - In DEVELOPMENT: can call Claude directly if EXPO_PUBLIC_CLAUDE_API_KEY is set
 *    (never ship this to production — the key would be visible in the app bundle).
 *
 * The Cloud Function is at functions/index.js in this repo.
 */

import * as FileSystem from 'expo-file-system';
import type { AIAnalysisResult, Plant } from '../types';

const FUNCTIONS_BASE_URL = process.env.EXPO_PUBLIC_FUNCTIONS_BASE_URL ?? '';
const DEV_CLAUDE_KEY     = process.env.EXPO_PUBLIC_CLAUDE_API_KEY ?? '';

// ─── Prompt builder ────────────────────────────────────────────────────────────────────────────────────

function buildPrompt(plant?: Plant): string {
  const context = plant
    ? `Plant name: ${plant.name}\nSpecies: ${plant.species}\nCurrent watering schedule: every ${plant.careProfile.wateringFrequencyDays} days.`
    : 'No plant context provided. Please identify the plant species if possible.';

  return `You are an expert botanist and houseplant care advisor. Analyze this photo of a houseplant.

${context}

Provide your analysis as a JSON object with this exact structure:
{
  "healthStatus": "healthy" | "warning" | "critical",
  "identifiedSpecies": "string or null if already known",
  "summary": "2-3 sentence plain-English summary for a beginner plant owner",
  "issues": [
    {
      "type": "string (e.g. overwatering, root rot, spider mites, sunburn, nutrient deficiency)",
      "severity": "low" | "medium" | "high",
      "description": "what you see and why it's a problem"
    }
  ],
  "recommendations": [
    {
      "action": "concrete action to take",
      "priority": "low" | "medium" | "high",
      "reason": "why this helps"
    }
  ],
  "scheduleAdjustments": [
    {
      "field": "wateringFrequencyDays" | "fertilizingFrequencyDays" | "trimmingFrequencyDays" | "mistingFrequencyDays",
      "label": "human-readable field name",
      "currentValue": number or null,
      "recommendedValue": number,
      "unit": "days",
      "reason": "why this change helps"
    }
  ]
}

Only include issues you can actually see in the photo. If the plant looks healthy, say so and provide an empty issues array.
Respond ONLY with the JSON object, no markdown or extra text.`;
}

// ─── Image helper ────────────────────────────────────────────────────────────────────────────────────

async function uriToBase64(uri: string): Promise<string> {
  const base64 = await FileSystem.readAsStringAsync(uri, {
    encoding: FileSystem.EncodingType.Base64,
  });
  return base64;
}

// ─── Production path (Cloud Function) ───────────────────────────────────────────────────────────────────────

async function analyzeViaCloudFunction(
  base64Image: string,
  plant?: Plant,
): Promise<AIAnalysisResult> {
  const url = `${FUNCTIONS_BASE_URL}/analyzePlant`;
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      imageBase64: base64Image,
      mimeType: 'image/jpeg',
      plantContext: plant
        ? {
            name:   plant.name,
            species:plant.species,
            careProfile: plant.careProfile,
          }
        : null,
    }),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Cloud function error ${response.status}: ${text}`);
  }

  return response.json() as Promise<AIAnalysisResult>;
}

// ─── Dev-only direct path ───────────────────────────────────────────────────────────────────────────────

async function analyzeDirectly(
  base64Image: string,
  plant?: Plant,
): Promise<AIAnalysisResult> {
  const response = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'x-api-key':         DEV_CLAUDE_KEY,
      'anthropic-version': '2023-06-01',
      'content-type':      'application/json',
    },
    body: JSON.stringify({
      model: 'claude-sonnet-4-6',
      max_tokens: 1024,
      messages: [
        {
          role: 'user',
          content: [
            {
              type: 'image',
              source: {
                type:       'base64',
                media_type: 'image/jpeg',
                data:        base64Image,
              },
            },
            { type: 'text', text: buildPrompt(plant) },
          ],
        },
      ],
    }),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Claude API error ${response.status}: ${text}`);
  }

  const data = await response.json();
  const text = data.content?.[0]?.text ?? '{}';
  return JSON.parse(text) as AIAnalysisResult;
}

// ─── Public API ──────────────────────────────────────────────────────────────────────────────────────

export async function analyzePlantPhoto(
  imageUri: string,
  plant?: Plant,
): Promise<AIAnalysisResult> {
  const base64 = await uriToBase64(imageUri);

  const result = FUNCTIONS_BASE_URL
    ? await analyzeViaCloudFunction(base64, plant)
    : await analyzeDirectly(base64, plant);

  return {
    ...result,
    timestamp: new Date().toISOString(),
  };
}
