// t(key, params) over shared/strings/de.json (README 8.4). Behavior is fixed by
// shared/test-vectors/strings/: unknown key → the key; missing param → `{name}` stays;
// plural form "one" only for integer count === 1, otherwise "other".

export type Strings = Record<string, string | Record<string, string>>;
export type Params = Record<string, string | number>;

const PLACEHOLDER = /\{([a-z][a-zA-Z0-9]*)\}/g;

export function pluralForm(count: unknown): "one" | "other" {
  return typeof count === "number" && Number.isInteger(count) && count === 1 ? "one" : "other";
}

export function render(strings: Strings, key: string, params: Params = {}): string {
  const value = strings[key];
  if (value === undefined) {
    return key;
  }
  const text = typeof value === "string" ? value : (value[pluralForm(params.count)] ?? value.other);
  return text.replace(PLACEHOLDER, (match, name: string) =>
    Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : match,
  );
}
