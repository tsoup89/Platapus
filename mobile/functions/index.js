/**
 * Platapus Firebase Cloud Functions
 *
 * Securely proxies Claude AI requests from the mobile app.
 * The ANTHROPIC_API_KEY is stored as a Firebase secret:
 *   firebase functions:secrets:set ANTHROPIC_API_KEY
 *
 * Deploy with:
 *   cd functions && firebase deploy --only functions
 */

const { onRequest } = require('firebase-functions/v2/https');
const { defineSecret } = require('firebase-functions/params');
const Anthropic = require('@anthropic-ai/sdk');

const ANTHROPIC_API_KEY = defineSecret('ANTHROPIC_API_KEY');

/**
 * POST /analyzePlant
 * Body: { imageBase64: string, mimeType: string, plantContext?: object }
 * Returns: AIAnalysisResult JSON
 */
exports.analyzePlant = onRequest(
  {
    secrets: [ANTHROPIC_API_KEY],
    cors: true,                  // Allow mobile app origins
    timeoutSeconds: 60,
    memory: '256MiB',
  },
  async (req, res) => {
    if (req.method !== 'POST') {
      res.status(405).json({ error: 'Method not allowed' });
      return;
    }

    const { imageBase64, mimeType = 'image/jpeg', plantContext } = req.body;

    if (!imageBase64) {
      res.status(400).json({ error: 'imageBase64 is required' });
      return;
    }

    // Build prompt
    const context = plantContext
      ? `Plant name: ${plantContext.name}\nSpecies: ${plantContext.species}\nCurrent watering schedule: every ${plantContext.careProfile?.wateringFrequencyDays ?? '?'} days.`
      : 'No plant context provided. Please identify the plant species if possible.';

    const prompt = `You are an expert botanist and houseplant care advisor. Analyze this photo of a houseplant.

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

Only include issues you can actually see in the photo. Respond ONLY with the JSON object.`;

    try {
      const client = new Anthropic({ apiKey: ANTHROPIC_API_KEY.value() });

      const message = await client.messages.create({
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
                  media_type: mimeType,
                  data:       imageBase64,
                },
              },
              { type: 'text', text: prompt },
            ],
          },
        ],
      });

      const text = message.content?.[0]?.text ?? '{}';

      // Parse and validate JSON
      let analysis;
      try {
        analysis = JSON.parse(text);
      } catch {
        // Claude returned invalid JSON — wrap it
        analysis = {
          healthStatus: 'warning',
          summary: text.slice(0, 300),
          issues: [],
          recommendations: [],
          scheduleAdjustments: [],
        };
      }

      analysis.timestamp = new Date().toISOString();
      res.status(200).json(analysis);

    } catch (err) {
      console.error('Claude API error:', err);
      res.status(500).json({ error: err.message ?? 'AI analysis failed' });
    }
  },
);
