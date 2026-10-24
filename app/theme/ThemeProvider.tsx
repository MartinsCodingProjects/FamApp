// ThemeProvider (README 8.2): semantic tokens from tokens.generated.ts, light/dark following
// the system. Only base components in components/ read the theme.
import { createContext, useContext, type ReactNode } from "react";
import { useColorScheme } from "react-native";

import { darkColors, duration, fontSize, fontWeight, lightColors, radius, space, type ColorTokens } from "./tokens.generated";

export type Theme = {
  scheme: "light" | "dark";
  colors: ColorTokens;
  space: typeof space;
  radius: typeof radius;
  fontSize: typeof fontSize;
  fontWeight: typeof fontWeight;
  duration: typeof duration;
};

export function makeTheme(scheme: "light" | "dark"): Theme {
  return {
    scheme,
    colors: scheme === "dark" ? darkColors : lightColors,
    space,
    radius,
    fontSize,
    fontWeight,
    duration,
  };
}

const ThemeContext = createContext<Theme>(makeTheme("light"));

export function ThemeProvider({ children, scheme }: { children: ReactNode; scheme?: "light" | "dark" }) {
  const system = useColorScheme();
  const theme = makeTheme(scheme ?? (system === "dark" ? "dark" : "light"));
  return <ThemeContext.Provider value={theme}>{children}</ThemeContext.Provider>;
}

export function useTheme(): Theme {
  return useContext(ThemeContext);
}
