/** A metric absent from an older results file is written as null (see
 * aggregate_generation.py); this renders "n/a" instead of "null"/NaN. */
export function fmt(value: unknown, digits = 3): string {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value.toFixed(digits);
  }
  return "n/a";
}

export function pct(value: unknown, digits = 1): string {
  if (typeof value === "number" && Number.isFinite(value)) {
    return `${(value * 100).toFixed(digits)}%`;
  }
  return "n/a";
}
