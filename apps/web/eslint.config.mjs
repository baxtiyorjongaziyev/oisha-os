import js from "@eslint/js";
import globals from "globals";
import tseslint from "typescript-eslint";
// eslint-config-next 16 nativ flat config eksport qiladi (massiv).
// FlatCompat orqali o'tkazish shart emas va @eslint/eslintrc legacy loader'ida
// "TypeError: Converting circular structure to JSON" crash'iga olib keladi.
import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

const config = [
  {
    ignores: [".next/**", "dist/**", "next-env.d.ts"]
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  ...nextCoreWebVitals,
  ...nextTypescript,
  {
    languageOptions: {
      ecmaVersion: "latest",
      globals: {
        ...globals.browser,
        ...globals.node
      },
      sourceType: "module"
    }
  }
];

export default config;
