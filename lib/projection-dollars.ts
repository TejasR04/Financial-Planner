export type ProjectionDollarDisplay = "today" | "future";

/** Convert a real-dollar model output solely for presentation. */
export function displayProjectionDollars(
  value: number,
  yearsFromToday: number,
  inflationRate: number,
  display: ProjectionDollarDisplay,
) {
  return display === "future" ? value * (1 + inflationRate) ** Math.max(0, yearsFromToday) : value;
}
