// ESLint flat config for all JS/TS in the repo. The Expo app (1.5) extends it with React rules.
import js from "@eslint/js";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    ignores: [
      "**/node_modules/**",
      "**/dist/**",
      "**/build/**",
      "**/.expo/**",
      "app/android/**",
      "**/.venv/**",
      ".tools/**",
      "**/*.min.js",
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      globals: { ...globals.node },
    },
  },
  {
    // Expo/Metro config files are CommonJS (app/package.json has no "type": "module").
    files: ["app/*.config.js"],
    languageOptions: { sourceType: "commonjs" },
    rules: { "@typescript-eslint/no-require-imports": "off" },
  },
  {
    files: ["**/__tests__/**", "**/*.test.{ts,tsx}"],
    languageOptions: { globals: { ...globals.jest } },
  },
);
