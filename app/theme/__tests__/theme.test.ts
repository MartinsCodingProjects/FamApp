import { makeTheme } from "../ThemeProvider";

test("light and dark use the generated semantic tokens", () => {
  const light = makeTheme("light");
  const dark = makeTheme("dark");
  expect(light.colors.state.urgent).toMatch(/^#[0-9a-f]{6}$/);
  expect(dark.colors.bg.app).not.toBe(light.colors.bg.app);
  expect(Object.keys(dark.colors)).toEqual(Object.keys(light.colors));
  expect(light.space.screen.padding).toBeGreaterThan(0);
});
