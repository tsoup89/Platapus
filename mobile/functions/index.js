/**
 * Gamgee Firebase Cloud Functions
 *
 * Two endpoints:
 *  POST /analyzePlant   — diagnose plant health from photo
 *  POST /identifyPlant  — identify unknown plant + suggest care profile
 *
 * Store API key:
 *   firebase functions:secrets:set ANTHROPIC_API_KEY
 * Deploy:
 *   cd functions && firebase deploy --only functions
 */

const { onRequest } = require('firebase-functions/v2/https');
const { defineSecret } = require('firebase-functions/params');
const Anthropic = require('@anthropic-ai/sdk');

const ANTHROPIC_API_KEY = defineSecret('ANTHROPIC_API_KEY');
const MODEL = 'claude-sonnet-4-6';

const FUNCTION_OPTS = {
  secrets:        [ANTHROPIC_API_KEY],
  cors:           true,
  timeoutSeconds: 60,
  memory:         '256MiB',
};

async function callClaude(apiKey, messages) {
  const client = new Anthropic({ apiKey });
  const msg = await client.messages.create({
    model:      MODEL,
    max_tokens: 1024,
    messages,
  });
  return msg.content?.[0]?.text ?? '{}';
}

function safeJson(text) {
  try { return JSON.parse(text); }
  catch { return { error: 'Failed to parse AI response', raw: text.slice(0, 200) }; }
}

// ─── POST /analyzePlant ────────────────────────────────────────────────────────────────────────────

exports.analyzePlant = onRequest(FUNCTION_OPTS, async (req, res) => {
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST only' });

  const { imageBase64, mimeType = 'image/jpeg', plantContext } = req.body;
  if (!imageBase64) return res.status(400).json({ error: 'imageBase64 required' });

  const context = plantContext
    ? `Plant: ${plantContext.name} (${plantContext.species}). Watering: every ${plantContext.careProfile?.wateringFrequencyDays ?? '?'} days.`
    : 'No plant context. Identify the species if possible.';

  const prompt = `You are an expert botanist. Analyze this houseplant photo.
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

  try {
    const text   = await callClaude(ANTHROPIC_API_KEY.value(), [{
      role: 'user',
      content: [
        { type: 'image', source: { type: 'base64', media_type: mimeType, data: imageBase64 } },
        { type: 'text', text: prompt },
      ],
    }]);
    const result = safeJson(text);
    result.timestamp = new Date().toISOString();
    res.status(200).json(result);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});

// ─── POST /identifyPlant ────────────────────────────────────────────────────────────────────────────

exports.identifyPlant = onRequest(FUNCTION_OPTS, async (req, res) => {
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST only' });

  const { imageBase64, mimeType = 'image/jpeg' } = req.body;
  if (!imageBase64) return res.status(400).json({ error: 'imageBase64 required' });

  const prompt = `You are an expert botanist. Identify this houseplant.

Return ONLY this JSON:
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

  try {
    const text   = await callClaude(ANTHROPIC_API_KEY.value(), [{
      role: 'user',
      content: [
        { type: 'image', source: { type: 'base64', media_type: mimeType, data: imageBase64 } },
        { type: 'text', text: prompt },
      ],
    }]);
    const result = safeJson(text);
    // Clean up null optional fields
    if (result.suggestedCareProfile) {
      const cp = result.suggestedCareProfile;
      if (!cp.trimmingFrequencyDays)  delete cp.trimmingFrequencyDays;
      if (!cp.mistingFrequencyDays)   delete cp.mistingFrequencyDays;
    }
    res.status(200).json(result);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});
