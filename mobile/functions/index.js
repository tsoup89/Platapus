/**
 * Gamgee Firebase Cloud Functions
 *
 * Three endpoints:
 *  POST /analyzePlant   — diagnose plant health from photo
 *  POST /identifyPlant  — identify unknown plant + suggest care profile
 *  POST /detectPests    — specialist pest & disease scan
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

async function callClaude(apiKey, messages, maxTokens = 1500) {
  const client = new Anthropic({ apiKey });
  const msg = await client.messages.create({
    model:      MODEL,
    max_tokens: maxTokens,
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

// ─── POST /detectPests ─────────────────────────────────────────────────────────────────────────────

exports.detectPests = onRequest(FUNCTION_OPTS, async (req, res) => {
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST only' });

  const { imageBase64, mimeType = 'image/jpeg', plantName, plantSpecies } = req.body;
  if (!imageBase64) return res.status(400).json({ error: 'imageBase64 required' });

  const context = (plantName || plantSpecies)
    ? `\n\nPlant context: ${plantName ?? 'Unknown'} (${plantSpecies ?? 'Unknown species'}).`
    : '';

  const prompt = `You are an expert plant pathologist and entomologist specializing in houseplants.
Carefully examine this photo for any signs of pests, disease, or nutrient deficiencies.

Look specifically for:
PESTS: spider mites (fine webbing, stippled/bronzed leaves), aphids (soft clusters on new growth/stem tips), fungus gnats (soil surface, weak seedlings), scale insects (waxy brown/tan bumps on stems), mealybugs (white cottony masses in leaf axils), thrips (silvery streaking, distorted leaves), whiteflies (white cloud when leaf disturbed)
DISEASES: root rot (yellowing + mushy stem base), powdery mildew (white powder on leaf surface), leaf spot (brown/black spots with yellow halo), botrytis/grey mold (fuzzy grey growth on dying tissue), rust (orange/brown pustules on undersides)
DEFICIENCIES: overall yellowing (nitrogen), young leaves yellow/old green (iron), yellowing between veins (magnesium), purple tint on undersides (phosphorus)

If the plant looks completely healthy with no signs of any issue, say so clearly and return an empty issues array.
${context}

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

  try {
    const text   = await callClaude(ANTHROPIC_API_KEY.value(), [{
      role: 'user',
      content: [
        { type: 'image', source: { type: 'base64', media_type: mimeType, data: imageBase64 } },
        { type: 'text', text: prompt },
      ],
    }], 1500);
    const result = safeJson(text);
    result.timestamp = new Date().toISOString();
    res.status(200).json(result);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});
