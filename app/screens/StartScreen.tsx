import branding from "../../branding.json";
import { Screen } from "../components/Screen";
import { Text } from "../components/Text";
import { t } from "../i18n";

// Placeholder start screen (BUILDPLAN 1.5.8); replaced by pairing and the todo list in later runs.
export function StartScreen() {
  return (
    <Screen>
      <Text variant="title" testID="start-title">
        {t("app.start.welcome", { name: branding.displayName })}
      </Text>
    </Screen>
  );
}
