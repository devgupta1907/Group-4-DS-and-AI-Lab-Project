/** Small display helpers shared across features. No app knowledge. */

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${Math.round(kb)} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}

/** Joins the parts of a date range, tolerating either end being absent. */
export function formatRange(start?: string | null, end?: string | null): string | null {
  const from = start?.trim();
  const to = end?.trim();
  if (from && to) return `${from} — ${to}`;
  return from ?? to ?? null;
}

/** Joins present values with a separator, dropping blanks. */
export function joinPresent(
  values: readonly (string | null | undefined)[],
  separator = ' · ',
): string | null {
  const present = values.map((v) => v?.trim()).filter((v): v is string => Boolean(v));
  return present.length > 0 ? present.join(separator) : null;
}
