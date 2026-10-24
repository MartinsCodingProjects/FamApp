# UI strings

`de.json` is the single source of every user-facing text (README 8.4). Code uses keys only, via `t(key, params)`.

## Keys

- Flat JSON object, keys sorted alphabetically, dotted by area: `<area>.<group>.<name>`, e.g. `todo.action.claim`, `sync.banner.offline`.
- Segments are lowerCamelCase (`[a-z][a-zA-Z0-9]*`), at least two segments.
- Areas so far: `app`, `mode`, `notification`, `settings`, `sync`, `todo`, `admin`, `web`. Add new ones as needed.
- New usage → add the key in the same PR. Removed usage → remove the key.

## Values

- A plain string, or a plural object.
- Placeholders: `{name}` with a lowerCamelCase name. Anything else in braces is literal text. Missing parameters stay as `{name}` in the output.
- Plurals: an object with CLDR forms; German uses `one` (count = 1) and `other` (everything else). `other` is required. The form is chosen from the `count` parameter (an integer; anything else selects `other`), which every call must pass. The `other` form must contain `{count}`; other forms may leave it out ("Ein Todo"), but all forms use the same remaining placeholders. Never build counts by string concatenation.
- An unknown key renders as the key itself (visible, no crash).

Behavior of the `t()` helpers (TypeScript, Kotlin, Python) is fixed by `shared/test-vectors/strings/`.

## Checks (`make lint`, `tools/strings_check.py`)

- `de.json` is valid: sorted keys, key format, value shape, `other` present and using `{count}`, same placeholders in all plural forms.
- Every key used in code (`t("…")`) exists; a used key with a literal parameter object passes exactly the text's placeholders.
- Unused keys are reported as warnings. A key counts as used when it appears as a string literal anywhere in the code (so keys sent by the server as data count too).
- No German string literals in code (umlauts, ß or common German words). Escape hatch for a single line: a comment containing `i18n-ignore`.
