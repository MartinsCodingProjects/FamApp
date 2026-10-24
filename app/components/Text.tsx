import type { ReactNode } from "react";
import { Text as RNText } from "react-native";

import { useTheme } from "../theme/ThemeProvider";

type Variant = "body" | "title" | "caption";

export function Text({ children, variant = "body", testID }: { children: ReactNode; variant?: Variant; testID?: string }) {
  const theme = useTheme();
  const size = { body: theme.fontSize.body, title: theme.fontSize.heading, caption: theme.fontSize.caption }[variant];
  const weight = variant === "title" ? theme.fontWeight.title : theme.fontWeight.body;
  const color = variant === "caption" ? theme.colors.text.muted : theme.colors.text.primary;
  return (
    <RNText testID={testID} style={{ color, fontSize: size, fontWeight: weight }}>
      {children}
    </RNText>
  );
}
