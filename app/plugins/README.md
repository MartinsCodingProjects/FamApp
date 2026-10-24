# Config plugins

All native Android configuration goes through Expo config plugins in this folder (README 8.1, AGENTS.md section 5): manifest entries, receivers, permissions, the FCM service. The generated `android/` folder is git-ignored, produced only by `npx expo prebuild`, and never edited by hand.

Add a plugin as `plugins/with<Name>.js` and list it in `app.config.js` → `expo.plugins`.
