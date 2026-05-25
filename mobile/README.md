# 🌿 Platapus Mobile — Plant Care App

A smart iPhone app to keep your houseplants alive and thriving. Powered by Claude AI for photo-based plant health analysis.

## Features

- 📱 **My Plants** — Track all your houseplants with photos, names, and care profiles
- 🏠 **Rooms** — Organize plants by room (Living Room, Bedroom, Kitchen, etc.)
- ⏰ **Smart Reminders** — Push notifications for watering, fertilizing, repotting, and trimming
- 🤖 **AI Analysis** — Snap a photo and Claude AI tells you what's wrong and how to fix it
- 🌱 **Plant Database** — Quick-start care profiles for 50+ common houseplants

## Tech Stack

| Layer | Technology |
|-------|------------|
| Framework | React Native (Expo SDK 52) |
| Navigation | Expo Router (file-based) |
| Auth + DB | Firebase (Firestore, Auth) |
| Storage | Firebase Storage |
| Push Notifications | Expo Notifications + FCM |
| AI | Claude claude-sonnet-4-6 via Cloud Functions |
| Language | TypeScript |

## Getting Started

### 1. Install dependencies

```bash
cd mobile
npm install
```

### 2. Configure Firebase

1. Create a project at [console.firebase.google.com](https://console.firebase.google.com)
2. Enable: Authentication (Email/Password), Firestore, Storage, Cloud Functions
3. Copy your config to `.env`:

```bash
cp .env.example .env
# Fill in all values from your Firebase console
```

### 3. Deploy Cloud Functions (handles Claude API calls securely)

```bash
cd functions
npm install
firebase functions:secrets:set ANTHROPIC_API_KEY
firebase deploy --only functions
```

### 4. Run the app

```bash
npm start
# Scan QR code with Expo Go on your iPhone
```

## Project Structure

```
mobile/
├── app/                    # Expo Router screens
│   ├── _layout.tsx         # Root layout (auth gate)
│   ├── (auth)/             # Login / Register
│   ├── (tabs)/             # Bottom tab screens
│   │   ├── index.tsx       # Home — Today's tasks
│   │   ├── plants.tsx      # My Plants
│   │   ├── rooms.tsx       # Rooms
│   │   └── settings.tsx    # Settings
│   ├── plant/
│   │   ├── [id].tsx        # Plant detail
│   │   └── add.tsx         # Add / edit plant
│   └── analyze.tsx         # AI photo analysis
├── src/
│   ├── types/              # TypeScript types
│   ├── constants/          # Colors, plant database
│   ├── services/           # Firebase + Claude API
│   ├── hooks/              # React hooks
│   └── components/         # Shared UI components
└── functions/              # Firebase Cloud Functions
```

## Building for iPhone (TestFlight)

```bash
npm install -g eas-cli
eas build:configure
eas build --platform ios
eas submit --platform ios
```

> ⚠️ **Never commit your `.env` file.** The Claude API key lives only as a Firebase Functions secret.

## Roadmap

- [x] Plant CRUD with photos
- [x] Rooms / collections
- [x] Care task scheduling + push notifications
- [x] Claude AI photo analysis
- [ ] Plant identification from photo
- [ ] Weather-based watering adjustments
- [ ] Pest / disease detection mode
- [ ] Care history charts
- [ ] Family sharing
