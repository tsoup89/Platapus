// ─── Care profile types ──────────────────────────────────────────────────────────────────────────────────────

export type LightRequirement    = 'low' | 'medium' | 'high' | 'direct';
export type HumidityRequirement = 'low' | 'medium' | 'high';
export type PlantStatus         = 'healthy' | 'needs_attention' | 'sick';
export type CareTaskType        = 'water' | 'fertilize' | 'repot' | 'trim' | 'mist' | 'custom';
export type PlantDifficulty     = 'easy' | 'medium' | 'hard';
export type Hemisphere          = 'north' | 'south';

export interface CareProfile {
  wateringFrequencyDays: number;
  lightRequirement:      LightRequirement;
  humidityRequirement:   HumidityRequirement;
  fertilizingFrequencyDays?: number;
  repottingFrequencyMonths?: number;
  trimmingFrequencyDays?:    number;
  mistingFrequencyDays?:     number;
  lastWatered?:    string;
  lastFertilized?: string;
  lastRepotted?:   string;
  lastTrimmed?:    string;
  lastMisted?:     string;
}

// ─── Core models ──────────────────────────────────────────────────────────────────────────────────────

export interface Plant {
  id: string;
  userId: string;
  name: string;
  species: string;
  roomId: string;
  roomName?: string;
  photoUrl?: string;
  photoPath?: string;
  dateAdded: string;
  notes?: string;
  careProfile: CareProfile;
  status: PlantStatus;
  lastAnalyzed?: string;
  lastAnalysisNotes?: string;
}

export interface Room {
  id: string;
  userId: string;
  name: string;
  icon: string;
  plantCount: number;
  createdAt: string;
}

export interface CareTask {
  id: string;
  plantId: string;
  plantName: string;
  plantPhotoUrl?: string;
  userId: string;
  type: CareTaskType;
  dueDate: string;
  completedDate?: string;
  completed: boolean;
  notes?: string;
}

// ─── AI Health Analysis ─────────────────────────────────────────────────────────────────────────────────────

export interface AIIssue {
  type: string;
  severity: 'low' | 'medium' | 'high';
  description: string;
}

export interface AIRecommendation {
  action: string;
  priority: 'low' | 'medium' | 'high';
  reason: string;
}

export interface ScheduleAdjustment {
  field: keyof Pick<CareProfile,
    'wateringFrequencyDays' | 'fertilizingFrequencyDays' |
    'trimmingFrequencyDays' | 'mistingFrequencyDays'>;
  label: string;
  currentValue?: number;
  recommendedValue: number;
  unit: string;
  reason: string;
}

export interface AIAnalysisResult {
  timestamp: string;
  healthStatus: 'healthy' | 'warning' | 'critical';
  identifiedSpecies?: string;
  issues: AIIssue[];
  recommendations: AIRecommendation[];
  scheduleAdjustments: ScheduleAdjustment[];
  summary: string;
}

// ─── Pest & Disease Detection ────────────────────────────────────────────────

export type PestIssueType = 'pest' | 'disease' | 'deficiency';

export interface PestOrDiseaseIssue {
  /** e.g. "Spider mites", "Powdery mildew", "Nitrogen deficiency" */
  name: string;
  type: PestIssueType;
  confidence: 'high' | 'medium' | 'low';
  severity: 'low' | 'medium' | 'high';
  /** What is visible in the photo */
  symptoms: string;
  /** Step-by-step treatment */
  treatment: string;
  /** How to prevent recurrence */
  prevention: string;
}

export interface PestDetectionResult {
  timestamp: string;
  /** clean = no issues found; warning = early signs; infestation = active problem */
  overallSeverity: 'clean' | 'warning' | 'infestation';
  summary: string;
  quarantineRecommended: boolean;
  immediateActions: string[];
  issues: PestOrDiseaseIssue[];
}

// ─── User / Settings ──────────────────────────────────────────────────────────────────────────────────

export interface NotificationPreferences {
  enabled: boolean;
  dailyReminderHour:   number;
  dailyReminderMinute: number;
  advanceNotificationHours: number;
}

export interface UserProfile {
  uid: string;
  email: string;
  displayName?: string;
  hemisphere: Hemisphere;          // 'north' | 'south' — for seasonal care
  notificationPreferences: NotificationPreferences;
  expoPushToken?: string;
}

// ─── Plant templates ──────────────────────────────────────────────────────────────────────────────────

export interface PlantTemplate {
  species: string;
  commonName: string;
  emoji: string;
  defaultCareProfile: Omit<CareProfile,
    'lastWatered' | 'lastFertilized' | 'lastRepotted' | 'lastTrimmed' | 'lastMisted'>;
  description: string;
  difficulty: PlantDifficulty;
  toxicToPets: boolean;
  tags: string[];
}
