export function parseJsonObject(
  source: string
): { ok: true; value: Record<string, unknown> } | { ok: false; error: string } {
  try {
    const parsed = JSON.parse(source);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return { ok: false, error: "Arguments JSON must be an object." };
    }
    return { ok: true, value: parsed as Record<string, unknown> };
  } catch (error: unknown) {
    return { ok: false, error: `Invalid arguments JSON: ${errorMessage(error)}` };
  }
}

export function parseRequiredOutputKeys(source: string): string[] {
  return uniqueStrings(
    source
      .split(/[\n,]/)
      .map((item) => item.trim())
      .filter(Boolean)
  );
}

function uniqueStrings(values: string[]): string[] {
  const seen = new Set<string>();
  const unique: string[] = [];
  values.forEach((value) => {
    const normalized = value.trim();
    if (!normalized || seen.has(normalized)) {
      return;
    }
    seen.add(normalized);
    unique.push(normalized);
  });
  return unique;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
