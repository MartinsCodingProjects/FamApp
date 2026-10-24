import { render, screen } from "@testing-library/react-native";

import { StartScreen } from "../StartScreen";
import { ThemeProvider } from "../../theme/ThemeProvider";

test("start screen shows the welcome string from de.json", async () => {
  await render(
    <ThemeProvider scheme="dark">
      <StartScreen />
    </ThemeProvider>,
  );
  expect(screen.getByTestId("start-title")).toHaveTextContent("Willkommen bei FamApp");
});
