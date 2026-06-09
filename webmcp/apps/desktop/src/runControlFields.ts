import type { WorkflowArgument } from "./vite-env";

export type RunControlInputType = "text" | "number" | "checkbox";
export type RunControlRole = "request" | "companyName" | "ticker" | "newsLimit" | "extraArgument";

export type VisibleRunControlField = {
  key: string;
  role: RunControlRole;
  label: string;
  inputType: RunControlInputType;
  argumentName?: string;
  description?: string;
  required?: boolean;
  valueType?: string;
};

const requestField: VisibleRunControlField = {
  key: "request",
  role: "request",
  label: "Request",
  inputType: "text"
};

const hiddenArgumentNames = new Set(["page_text"]);

const canonicalArguments: Record<string, Omit<VisibleRunControlField, "argumentName" | "description" | "required" | "valueType">> = {
  company_name: { key: "companyName", role: "companyName", label: "Company", inputType: "text" },
  companyName: { key: "companyName", role: "companyName", label: "Company", inputType: "text" },
  ticker: { key: "ticker", role: "ticker", label: "Ticker", inputType: "text" },
  news_limit: { key: "newsLimit", role: "newsLimit", label: "News", inputType: "number" },
  newsLimit: { key: "newsLimit", role: "newsLimit", label: "News", inputType: "number" }
};

export function buildVisibleRunControlFields(workflowArguments: WorkflowArgument[]): VisibleRunControlField[] {
  const fields: VisibleRunControlField[] = [requestField];
  const seenKeys = new Set(fields.map((field) => field.key));

  for (const argument of [...workflowArguments].sort((left, right) => left.orderIndex - right.orderIndex)) {
    if (hiddenArgumentNames.has(argument.name)) {
      continue;
    }
    const canonical = canonicalArguments[argument.name];
    const field: VisibleRunControlField = canonical
      ? {
          ...canonical,
          argumentName: argument.name,
          description: argument.description,
          required: argument.required,
          valueType: argument.valueType
        }
      : {
          key: `argument:${argument.name}`,
          role: "extraArgument",
          label: labelForArgument(argument.name),
          inputType: inputTypeForArgument(argument.valueType),
          argumentName: argument.name,
          description: argument.description,
          required: argument.required,
          valueType: argument.valueType
        };
    if (seenKeys.has(field.key)) {
      continue;
    }
    seenKeys.add(field.key);
    fields.push(field);
  }

  return fields;
}

function inputTypeForArgument(valueType: string): RunControlInputType {
  const normalized = valueType.trim().toLowerCase();
  if (["integer", "number", "float"].includes(normalized)) {
    return "number";
  }
  if (["boolean", "bool"].includes(normalized)) {
    return "checkbox";
  }
  return "text";
}

function labelForArgument(name: string): string {
  return name
    .replace(/[_-]+/g, " ")
    .split(" ")
    .filter(Boolean)
    .map((part) => (part.toLowerCase() === "url" ? "URL" : part.charAt(0).toUpperCase() + part.slice(1)))
    .join(" ");
}
