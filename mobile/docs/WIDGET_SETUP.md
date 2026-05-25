# Gamgee iOS Home Screen Widget — Setup Guide

The widget uses a **WidgetKit extension** + a shared **App Group** so the
main app can push data to the widget without launching.

---

## How it works

```
Main app (React Native)
  │
  │  NativeModules.WidgetBridge.updateWidgetData(json)
  ▼
UserDefaults (group.com.gamgee.app)
  │
  │  WidgetCenter.shared.reloadAllTimelines()
  ▼
GamgeeWidget extension reads UserDefaults → renders small/medium widget
```

---

## Development build (EAS Build required)

Widgets cannot run in Expo Go — you need a development build:

```bash
cd mobile
npx eas build --platform ios --profile development
```

Or run on a simulator (EAS Build supports that via `ios.simulator: true`).

---

## One-time Xcode setup

After EAS generates the Xcode project (`npx expo prebuild`) you need to:

1. Open `ios/Gamgee.xcworkspace` in Xcode.
2. Select the **Gamgee** target → Signing & Capabilities.
3. Add **App Groups** capability → `group.com.gamgee.app`.
4. Select the **gamgee-widget** target → Signing & Capabilities.
5. Add **App Groups** capability → `group.com.gamgee.app`.

EAS Build handles this automatically if you set the correct provisioning
profiles in `eas.json` and your Apple Developer account.

---

## Widget sizes

| Size   | Shows |
|--------|-------|
| Small  | Task count + overdue count |
| Medium | Task count + up to 3 plant names with care-type emoji |

---

## Data sync

`widgetService.syncWidgetData()` is called from the home screen whenever
`plants` or `tasks` arrays change. It's a no-op on Android and Expo Go.

The widget also polls every 30 minutes as a fallback via its WidgetKit
timeline, so even if the app is never opened the widget won't go stale
for more than half an hour.

---

## Firebase Cloud Function note

The new `detectPests` Cloud Function endpoint must be deployed:

```bash
cd mobile/functions
npx firebase deploy --only functions
```

Make sure `ANTHROPIC_API_KEY` is set as a Firebase secret:

```bash
npx firebase functions:secrets:set ANTHROPIC_API_KEY
```
