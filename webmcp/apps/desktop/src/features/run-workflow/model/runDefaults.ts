import type { WorkflowArgument } from "../../../vite-env";

export function defaultRunValue(argument: WorkflowArgument): unknown {
  if (argument.defaultValue !== undefined && argument.defaultValue !== null) {
    return argument.defaultValue;
  }
  if (Array.isArray(argument.examples) && argument.examples.length > 0) {
    return argument.examples[0];
  }
  return undefined;
}
