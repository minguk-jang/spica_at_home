import type { WorkflowArgument, WorkflowDetail, WorkflowStep } from "../../../vite-env";

export function defaultJsToolArgumentsJson(detail: WorkflowDetail): string {
  const values: Record<string, unknown> = {};
  const pageTextSeed = pageTextSeedFromSteps(detail.steps);
  for (const argument of [...detail.arguments].sort((left, right) => left.orderIndex - right.orderIndex)) {
    const value = defaultRunValue(argument);
    if (value !== undefined) {
      values[argument.name] = value;
      continue;
    }
    if (argument.name === "page_text" && pageTextSeed) {
      values[argument.name] = pageTextSeed;
      continue;
    }
    if (argument.required) {
      values[argument.name] = sampleValueForArgument(argument);
    }
  }
  if (values.page_text === undefined && pageTextSeed) {
    values.page_text = pageTextSeed;
  }
  return JSON.stringify(values, null, 2);
}

export function defaultRequiredOutputKeys(detail: WorkflowDetail, selectedVersion: number | null): string[] {
  const version = detail.versions.find((candidate) => candidate.version === selectedVersion) ?? detail.versions[0] ?? null;
  return version ? schemaKeys(version.outputSchema) : [];
}

function pageTextSeedFromSteps(steps: WorkflowStep[]): string {
  const markers = uniqueStrings(
    steps
      .filter((step) => step.stepType === "wait_for_text")
      .flatMap((step) => {
        const assertions = asRecord(step.assertions);
        return [
          ...toStringList(assertions.contains_any),
          ...toStringList(assertions.contains_all),
          ...toStringList(assertions.required_text),
          ...toStringList(assertions.text)
        ];
      })
  );
  return markers.join("\n");
}

function defaultRunValue(argument: WorkflowArgument): unknown {
  if (argument.defaultValue !== undefined && argument.defaultValue !== null) {
    return argument.defaultValue;
  }
  if (Array.isArray(argument.examples) && argument.examples.length > 0) {
    return argument.examples[0];
  }
  return undefined;
}

function sampleValueForArgument(argument: WorkflowArgument): unknown {
  const valueType = argument.valueType.toLowerCase();
  if (valueType.includes("number") || valueType.includes("integer")) {
    return 0;
  }
  if (valueType.includes("boolean")) {
    return false;
  }
  return "";
}

function schemaKeys(schema: unknown): string[] {
  const record = asRecord(schema);
  const properties = asRecord(record.properties);
  const directKeys = Object.keys(record).filter((key) => !["type", "properties", "required"].includes(key));
  return uniqueStrings([
    ...toStringList(record.required),
    ...Object.keys(properties),
    ...directKeys
  ]);
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

function toStringList(value: unknown): string[] {
  if (value === null || value === undefined) {
    return [];
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed ? [trimmed] : [];
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return [String(value)];
  }
  if (Array.isArray(value)) {
    return value.flatMap((item) => toStringList(item));
  }
  if (typeof value === "object") {
    return Object.values(value as Record<string, unknown>).flatMap((item) => toStringList(item));
  }
  return [];
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
