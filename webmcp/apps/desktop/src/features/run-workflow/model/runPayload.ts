import type { RunPayload, WorkflowArgument } from "../../../vite-env";
import {
  buildVisibleRunControlFields,
  type VisibleRunControlField
} from "./runControlFields.ts";

export type RunArgumentValues = {
  companyName: string;
  ticker: string;
  newsLimit: number;
  extraArguments: Record<string, unknown>;
};

export function buildRunArgumentPayload(
  workflowArguments: WorkflowArgument[],
  values: RunArgumentValues
): Pick<RunPayload, "companyName" | "ticker" | "newsLimit" | "extraArguments"> {
  const fields = buildVisibleRunControlFields(workflowArguments);
  const payload: Pick<RunPayload, "companyName" | "ticker" | "newsLimit" | "extraArguments"> = {};
  const hasRole = (role: VisibleRunControlField["role"]) => fields.some((field) => field.role === role);

  if (hasRole("companyName") && values.companyName.trim()) {
    payload.companyName = values.companyName.trim();
  }
  if (hasRole("ticker") && values.ticker.trim()) {
    payload.ticker = values.ticker.trim();
  }
  if (hasRole("newsLimit")) {
    payload.newsLimit = values.newsLimit;
  }

  const allowedExtraArguments = new Set(
    fields
      .filter((field) => field.role === "extraArgument" && field.argumentName)
      .map((field) => field.argumentName as string)
  );
  const nextExtraArguments = Object.fromEntries(
    Object.entries(values.extraArguments).filter(([key, value]) =>
      allowedExtraArguments.has(key) && value !== undefined && value !== null && value !== ""
    )
  );
  if (Object.keys(nextExtraArguments).length > 0) {
    payload.extraArguments = nextExtraArguments;
  }

  return payload;
}
