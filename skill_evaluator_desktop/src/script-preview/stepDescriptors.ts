import type { WorkflowHandler, WorkflowStep } from "../vite-env";
import type { StepScriptDescriptor } from "./types";

export function getStepScriptDescriptor(
  step: WorkflowStep,
  handlers: WorkflowHandler[]
): StepScriptDescriptor {
  if (step.stepType === "run_handler") {
    const handler = handlers.find((candidate) => candidate.name === step.handlerRef);
    return {
      kind: "Python handler",
      language: "Python",
      implementation: handler ? `${handler.module}.${handler.function}` : step.handlerRef ?? "Unregistered handler",
      storedAs: handler
        ? "handler_registry.module + handler_registry.function"
        : "workflow_skill_steps.handler_ref"
    };
  }

  if (step.stepType === "render_report") {
    return {
      kind: "Template renderer",
      language: "Python executor + Markdown template",
      implementation: "WorkflowExecutor._execute_step(render_report)",
      storedAs: "workflow_skill_resources.content_text",
      resourceName: resourceNameFromAction(step.action)
    };
  }

  return {
    kind: "Built-in executor action",
    language: "Python executor + JSON action",
    implementation: `WorkflowExecutor._execute_step(${step.stepType})`,
    storedAs: "workflow_skill_steps.action_json"
  };
}

function resourceNameFromAction(action: unknown): string | undefined {
  if (!action || typeof action !== "object" || !("template_resource" in action)) {
    return undefined;
  }
  const value = (action as { template_resource?: unknown }).template_resource;
  return typeof value === "string" ? value : undefined;
}
