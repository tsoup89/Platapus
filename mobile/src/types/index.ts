// ─── Care profile ──────────────────────────────────────────────────────────────────────────────────────

export type LightRequirement = 'low' | 'medium' | 'high' | 'direct';
export type HumidityRequirement = 'low' | 'medium' | 'high';
export type PlantStatus = 'healthy' | 'needs_attention' | 'sick';
export type CareTaskType = 'water' | 'fertilize' | 'repot' | 'trim' | 'mist' | 'custom';
export type PlantDifficulty = 'easy' | 'medium' | 'hard';

export interface CareProfile {
  wateringFrequencyDays: number;
  lightRequirement: LightRequirement;
  humidityRequirement: HumidityRequirement;
  // Optional recurring care tasks
  fertilizingFrequencyDays?: number;
  repottingFrequencyMonths?: number;
  trimmingFrequencyDays?: number;
  mistingFrequencyDays?: number;
  // Last performed dates (ISO strings)
  lastWatered?: string;
  lastFertilized?: string;
  lastRepotted?: string;
  lastTrimmed?: string;
  lastMisted?: string;
}

// ─── Core models ──────────────────────────────────────────────────────────────────────────────────────

export interface Plant {
  id: string;
  userId: string;
  name: string;          // User's nickname, e.g. "Big leafy boi"
  species: string;       // Common or scientific name
  roomId: string;
  roomName?: string;     // Denormalized for display
  photoUrl?: string;     // Download URL from Firebase Storage
  photoPath?: string;    // Storage path for deletion
  dateAdded: string;     // ISO date
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
  icon: string;          // Emoji icon
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
  dueDate: string;       // ISO date
  completedDate?: string;
  completed: boolean;
  notes?: string;
}

// ─── AI Analysis ──────────────────────────────────────────────────────────────────────────────────────

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

// ─── User / Settings ──────────────────────────────────────────────────────────────────────────────────

export interface NotificationPreferences {
  enabled: boolean;
  dailyReminderHour: number;   // 0–23
  dailyReminderMinute: number;
  advanceNotificationHours: number;
}

export interface UserProfile {
  uid: string;
  email: string;
  displayName?: string;
  notificationPreferences: NotificationPreferences;
  expoPushToken?: string;
}

// ─── Plant templates (database) ──────────────────────────────────────────────────────────────────────

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
