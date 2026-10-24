// Expo app config (BUILDPLAN 1.5.2). Display name and colors only from branding.json,
// version only from app/version.json. Native settings only via config plugins in plugins/.
const branding = require("../branding.json");
const version = require("./version.json");

module.exports = {
  expo: {
    name: branding.displayName,
    slug: "famapp",
    scheme: "famapp",
    version: version.versionName,
    orientation: "portrait",
    icon: "./assets/icon.png",
    userInterfaceStyle: "automatic",
    android: {
      package: "com.cowflex.famapp",
      versionCode: version.versionCode,
      adaptiveIcon: {
        backgroundColor: branding.iconColor,
        foregroundImage: "./assets/android-icon-foreground.png",
        backgroundImage: "./assets/android-icon-background.png",
        monochromeImage: "./assets/android-icon-monochrome.png",
      },
      predictiveBackGestureEnabled: false,
    },
    web: {
      favicon: "./assets/favicon.png",
      name: branding.displayName,
      shortName: branding.shortName,
      themeColor: branding.iconColor,
    },
    plugins: [],
  },
};
