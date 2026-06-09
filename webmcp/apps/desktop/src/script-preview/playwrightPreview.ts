import type { WorkflowHandler, WorkflowResource, WorkflowStep } from "../vite-env";

export function generatePlaywrightScriptPreview(
  steps: WorkflowStep[],
  handlers: WorkflowHandler[],
  resources: WorkflowResource[]
): string {
  const sortedSteps = [...steps].sort((left, right) => left.orderIndex - right.orderIndex);
  const handlerSections = buildInlinedHandlerSections(sortedSteps, handlers);
  const reportTemplates = Object.fromEntries(
    resources.map((resource) => [
      resource.name,
      resource.contentText || JSON.stringify(resource.contentJson, null, 2)
    ])
  );
  const lines = [
    ...handlerSections.futureImports,
    "# Generated inspection preview for this WebMCP workflow.",
    "# This is Python + Playwright, not JavaScript.",
    "# Handler implementations are inlined below as real Python code.",
    "import asyncio",
    "import json",
    "import os",
    "from pathlib import Path",
    "from playwright.async_api import async_playwright",
    "",
    ...handlerSections.body,
    `REPORT_TEMPLATES = ${pythonJson(reportTemplates)}`,
    "",
    "",
    "def render_template(template, values):",
    "    rendered = template",
    "    for key, value in values.items():",
    "        rendered = rendered.replace('{{' + key + '}}', str(value))",
    "    return rendered",
    "",
    "",
    "async def main(company_name=None, ticker=None, news_limit=None):",
    "    company_name = company_name or os.environ.get('WEBMCP_COMPANY_NAME', '삼성전자')",
    "    ticker = ticker if ticker is not None else os.environ.get('WEBMCP_TICKER', '')",
    "    news_limit = int(news_limit or os.environ.get('WEBMCP_NEWS_LIMIT', '3'))",
    "    values = {'company_name': company_name, 'ticker': ticker, 'news_limit': news_limit}",
    "    output = {}",
    "    page_text = ''",
    "    headless = os.environ.get('WEBWRIGHT_HEADLESS', '1') not in {'0', 'false', 'False'}",
    "    async with async_playwright() as playwright:",
    "        browser = await playwright.chromium.launch(headless=headless)",
    "        page = await browser.new_page(viewport={'width': 1280, 'height': 1800})",
    "        try:",
    ...sortedSteps.flatMap((step) => renderStepPreview(step, handlers)),
    "        finally:",
    "            await browser.close()",
    "    print(json.dumps(output, ensure_ascii=False, indent=2))",
    "    return output",
    "",
    "",
    "if __name__ == '__main__':",
    "    asyncio.run(main())",
    ""
  ];
  return lines.join("\n");
}

interface InlinedHandlerSections {
  futureImports: string[];
  body: string[];
}

function buildInlinedHandlerSections(
  steps: WorkflowStep[],
  handlers: WorkflowHandler[]
): InlinedHandlerSections {
  const futureImports = new Set<string>();
  const body: string[] = [];
  const seen = new Set<string>();

  for (const step of steps) {
    if (step.stepType !== "run_handler") {
      continue;
    }
    const handler = handlers.find((candidate) => candidate.name === step.handlerRef);
    const handlerName = handler?.name ?? step.handlerRef ?? "unregistered";
    const dedupeKey = handler?.sourceText ? `module:${handler.module}` : `handler:${handlerName}`;
    if (seen.has(dedupeKey)) {
      continue;
    }
    seen.add(dedupeKey);

    const block = inlinedHandlerBlock(handlerName, handler);
    for (const futureImport of block.futureImports) {
      futureImports.add(futureImport);
    }
    body.push(...block.body);
  }

  return {
    futureImports: [...futureImports].sort(),
    body
  };
}

function inlinedHandlerBlock(
  handlerName: string,
  handler: WorkflowHandler | undefined
): InlinedHandlerSections {
  if (!handler) {
    return missingHandlerStub(handlerName, handlerName);
  }
  if (!handler.sourceText) {
    return missingHandlerStub(`${handler.module}.${handler.function}`, handler.function, handler.sourcePath);
  }
  const source = splitHandlerSource(handler.sourceText);
  return {
    futureImports: source.futureImports,
    body: [
      "",
      `# BEGIN inlined handler module: ${handler.module}`,
      `# source_path: ${handler.sourcePath || ""}`,
      ...source.body,
      `# END inlined handler module: ${handler.module}`,
      ""
    ]
  };
}

function missingHandlerStub(
  handlerId: string,
  functionName: string,
  sourcePath = ""
): InlinedHandlerSections {
  const safeFunctionName = safePythonFunctionName(functionName);
  return {
    futureImports: [],
    body: [
      "",
      `# BEGIN missing handler stub: ${handlerId}`,
      `# source_path: ${sourcePath}`,
      `def ${safeFunctionName}(*args, **kwargs):`,
      `    raise RuntimeError(${pythonString(`Missing handler source: ${handlerId}`)})`,
      `# END missing handler stub: ${handlerId}`,
      ""
    ]
  };
}

function splitHandlerSource(sourceText: string): InlinedHandlerSections {
  const futureImports: string[] = [];
  const body: string[] = [];
  for (const line of sourceText.replace(/\r\n/g, "\n").replace(/\r/g, "\n").split("\n")) {
    if (/^from __future__ import /.test(line)) {
      futureImports.push(line);
      continue;
    }
    body.push(line);
  }
  return { futureImports, body: trimTrailingBlankLines(body) };
}

function trimTrailingBlankLines(lines: string[]): string[] {
  const trimmed = [...lines];
  while (trimmed.length > 0 && trimmed[trimmed.length - 1] === "") {
    trimmed.pop();
  }
  return trimmed;
}

function safePythonFunctionName(value: string): string {
  const candidate = value.split(".").pop() || "missing_handler";
  return /^[A-Za-z_][A-Za-z0-9_]*$/.test(candidate) ? candidate : "missing_handler";
}

function renderStepPreview(step: WorkflowStep, handlers: WorkflowHandler[]): string[] {
  const number = step.orderIndex + 1;
  const prefix = "            ";
  const action = isRecord(step.action) ? step.action : {};
  const assertions = isRecord(step.assertions) ? step.assertions : {};
  const lines = [
    `${prefix}# step ${number}: ${step.name} (${step.stepType})`,
    `${prefix}# ${step.description}`
  ];

  if (step.stepType === "goto") {
    const urlTemplate = stringField(action, "url_template");
    if (!urlTemplate) {
      return [...lines, `${prefix}# Missing action.url_template; cannot generate page.goto.`];
    }
    return [
      ...lines,
      `${prefix}url = render_template(${pythonString(urlTemplate)}, values)`,
      `${prefix}await page.goto(url, wait_until='domcontentloaded')`,
      `${prefix}page_text = await page.locator('body').inner_text()`
    ];
  }

  if (step.stepType === "wait_for_text") {
    const markers = stringArrayField(assertions, "contains_any");
    return [
      ...lines,
      `${prefix}page_text = await page.locator('body').inner_text()`,
      `${prefix}markers = ${pythonJson(markers)}`,
      `${prefix}if markers and not any(marker in page_text for marker in markers):`,
      `${prefix}    raise AssertionError(f'none of the expected text markers were found: {markers}')`
    ];
  }

  if (step.stepType === "run_handler") {
    const handler = handlers.find((candidate) => candidate.name === step.handlerRef);
    if (!handler) {
      return [...lines, `${prefix}# Unregistered handler_ref: ${step.handlerRef ?? ""}`];
    }
    const requiredOutput = stringArrayField(assertions, "required_output");
    return [
      ...lines,
      `${prefix}handler_result = ${handler.function}(`,
      `${prefix}    page_text=page_text,`,
      `${prefix}    company_name=company_name,`,
      `${prefix}    ticker=ticker,`,
      `${prefix}    news_limit=news_limit,`,
      `${prefix})`,
      `${prefix}output.update(handler_result)`,
      `${prefix}for required_key in ${pythonJson(requiredOutput)}:`,
      `${prefix}    if output.get(required_key) in (None, ''):`,
      `${prefix}        raise AssertionError(f'handler output missing required key: {required_key}')`
    ];
  }

  if (step.stepType === "assert_output") {
    return [
      ...lines,
      `${prefix}# Output assertions from workflow_tool_steps.assertions_json:`,
      `${prefix}# ${oneLineJson(step.assertions)}`
    ];
  }

  if (step.stepType === "render_report") {
    const resourceName = stringField(action, "template_resource") || "";
    return [
      ...lines,
      `${prefix}template = REPORT_TEMPLATES.get(${pythonString(resourceName)}, '')`,
      `${prefix}report_values = dict(values)`,
      `${prefix}report_values.update(output)`,
      `${prefix}report_text = render_template(template, report_values)`,
      `${prefix}output['report_text'] = report_text`,
      `${prefix}Path('report_preview.md').write_text(report_text, encoding='utf-8')`
    ];
  }

  return [
    ...lines,
    `${prefix}# Unsupported preview step_type; raw action follows:`,
    `${prefix}# ${oneLineJson(step.action)}`
  ];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function stringField(record: Record<string, unknown>, key: string): string | undefined {
  const value = record[key];
  return typeof value === "string" ? value : undefined;
}

function stringArrayField(record: Record<string, unknown>, key: string): string[] {
  const value = record[key];
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function pythonString(value: string): string {
  return JSON.stringify(value);
}

function pythonJson(value: unknown): string {
  return pythonLiteral(value, 0);
}

function pythonLiteral(value: unknown, indent: number): string {
  if (value === null || value === undefined) {
    return "None";
  }
  if (typeof value === "string") {
    return pythonString(value);
  }
  if (typeof value === "number" || typeof value === "bigint") {
    return String(value);
  }
  if (typeof value === "boolean") {
    return value ? "True" : "False";
  }
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return "[]";
    }
    const pad = " ".repeat(indent);
    const childPad = " ".repeat(indent + 2);
    return `[\n${value
      .map((item) => `${childPad}${pythonLiteral(item, indent + 2)}`)
      .join(",\n")}\n${pad}]`;
  }
  if (isRecord(value)) {
    const entries = Object.entries(value);
    if (entries.length === 0) {
      return "{}";
    }
    const pad = " ".repeat(indent);
    const childPad = " ".repeat(indent + 2);
    return `{\n${entries
      .map(([key, item]) => `${childPad}${pythonString(key)}: ${pythonLiteral(item, indent + 2)}`)
      .join(",\n")}\n${pad}}`;
  }
  return pythonString(String(value));
}

function oneLineJson(value: unknown): string {
  return JSON.stringify(value);
}
