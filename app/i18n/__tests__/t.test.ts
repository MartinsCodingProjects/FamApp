import vectors from "../../../shared/test-vectors/strings/t.json";
import { t } from "..";
import { render, type Params, type Strings } from "../t";

describe("string vectors", () => {
  it.each(vectors.cases.map((c) => [c.name, c] as const))("%s", (_name, c) => {
    expect(render(vectors.strings as Strings, c.key, c.params as Params)).toBe(c.expected);
  });
});

test("t() reads de.json", () => {
  expect(t("todo.action.claim")).toBe("Mach ich");
  expect(t("sync.banner.pending", { count: 1 })).toBe("1 Änderung noch nicht synchronisiert");
  expect(t("does.not.exist")).toBe("does.not.exist");
});
