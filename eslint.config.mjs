import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";

export default defineConfig([
  ...nextVitals,
  globalIgnores([
    ".next/**",
    "out/**",
    "build/**",
    "coverage/**",
    ".pytest_cache/**",
    "backend/.pytest_cache/**",
    "backend/**/__pycache__/**",
    "next-env.d.ts",
  ]),
  {
    rules: {
      // These React Compiler diagnostics are useful during a migration, but
      // this client state architecture intentionally initializes form and
      // async request state in effects. Keep the established lint baseline
      // enforceable without turning those existing patterns into hard errors.
      "react-hooks/set-state-in-effect": "off",
      "react-hooks/purity": "off",
      "react/no-unescaped-entities": "off",
    },
  },
]);
