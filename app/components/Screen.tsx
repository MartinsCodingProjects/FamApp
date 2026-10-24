import type { ReactNode } from "react";
import { StyleSheet, View } from "react-native";

import { useTheme } from "../theme/ThemeProvider";

export function Screen({ children }: { children: ReactNode }) {
  const theme = useTheme();
  return (
    <View style={[styles.base, { backgroundColor: theme.colors.bg.app, padding: theme.space.screen.padding }]}>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  base: { flex: 1, alignItems: "center", justifyContent: "center" },
});
