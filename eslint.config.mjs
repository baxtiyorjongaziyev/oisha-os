import js from "@eslint/js";
import globals from "globals";
import tseslint from "typescript-eslint";

export default [
  {
    ignores: [
      ".next/**",
      ".turbo/**",
      ".venv/**",
      "dist/**",
      "**/.next/**",
      "**/.turbo/**",
      "**/dist/**",
      "**/next-env.d.ts",
      "node_modules/**",
      "**/node_modules/**",
      "tmp/**",
      "logs/**",
      "data/**"
    ]
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    languageOptions: {
      ecmaVersion: "latest",
      globals: {
        ...globals.browser,
        ...globals.node
      },
      sourceType: "module"
    },
    rules: {
      "@typescript-eslint/no-explicit-any": "off"
    }
  }
];
