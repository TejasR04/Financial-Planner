import { fileURLToPath } from "node:url";
import { configDefaults, defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      "@": fileURLToPath(new URL(".", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
    exclude: [...configDefaults.exclude, "e2e/**"],
    setupFiles: ["./vitest.setup.ts"],
    coverage: {
      provider: "v8",
      include: ["lib/**/*.{ts,tsx}", "components/**/*.{ts,tsx}"],
      exclude: ["**/*.test.{ts,tsx}"],
      reporter: ["text", "json-summary"],
      thresholds: {
        // This is an honest whole-frontend baseline. Raise these staged
        // thresholds as page orchestration and mutation flows gain tests.
        branches: 25,
        functions: 25,
        lines: 20,
        statements: 20,
      },
    },
  },
});
