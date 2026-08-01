import { execFileSync } from "node:child_process";

export default function globalTeardown() {
  try {
    execFileSync(
      "docker",
      [
        "compose",
        "--project-name",
        "meridian-e2e",
        "-f",
        "backend/docker-compose.test.yml",
        "down",
        "--volumes",
        "--remove-orphans",
      ],
      { stdio: "inherit" },
    );
  } catch (error) {
    process.stderr.write(`Unable to clean up the E2E Docker stack: ${String(error)}\n`);
  }
}
