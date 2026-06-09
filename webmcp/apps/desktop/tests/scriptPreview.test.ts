import assert from "node:assert/strict";
import test from "node:test";

import { generatePlaywrightScriptPreview } from "../src/script-preview/playwrightPreview.ts";
import { getStepScriptDescriptor } from "../src/script-preview/stepDescriptors.ts";
import type { WorkflowHandler, WorkflowResource, WorkflowStep } from "../src/vite-env";

const baseStep: WorkflowStep = {
  id: 1,
  versionId: 2,
  orderIndex: 0,
  name: "open_search",
  description: "Open search page",
  stepType: "goto",
  handlerRef: null,
  action: { url_template: "https://search.naver.com/search.naver?query={{company_name}} 주가" },
  argumentBindings: {},
  assertions: {},
  fallbackPolicy: {},
  updatePolicy: {}
};

const naverHandler: WorkflowHandler = {
  id: 10,
  name: "naver_stock.extract_stock_card",
  description: "Extract stock quote fields from Naver stock search text.",
  module: "webworkflows.handlers.naver_stock",
  function: "extract_stock_card",
  inputSchema: {},
  outputSchema: {},
  allowedDomains: ["naver.com"],
  sourcePath: "/repo/webworkflows/handlers/naver_stock.py",
  sourceText: [
    "def extract_stock_card(*, page_text, company_name, ticker=None, news_limit=3):",
    "    return {'company_name': company_name}",
    "",
    "def _helper():",
    "    return 'helper'"
  ].join("\n")
};

const reportTemplate: WorkflowResource = {
  id: 20,
  versionId: 2,
  resourceType: "report_template",
  name: "stock_report_markdown",
  description: "Report template",
  contentJson: null,
  contentText: "# {{company_name}} 주가 리포트\n현재가: {{current_price}}",
  loadWhen: {}
};

test("describes built-in executor steps as JSON actions, not JavaScript", () => {
  const descriptor = getStepScriptDescriptor(baseStep, []);

  assert.equal(descriptor.kind, "Built-in executor action");
  assert.equal(descriptor.language, "Python executor + JSON action");
  assert.equal(descriptor.implementation, "WorkflowExecutor._execute_step(goto)");
  assert.equal(descriptor.storedAs, "workflow_skill_steps.action_json");
});

test("describes run_handler steps as Python handlers from the registry", () => {
  const descriptor = getStepScriptDescriptor(
    {
      ...baseStep,
      name: "extract_stock_card",
      stepType: "run_handler",
      handlerRef: "naver_stock.extract_stock_card"
    },
    [naverHandler]
  );

  assert.equal(descriptor.kind, "Python handler");
  assert.equal(descriptor.language, "Python");
  assert.equal(descriptor.implementation, "webworkflows.handlers.naver_stock.extract_stock_card");
  assert.equal(descriptor.storedAs, "handler_registry.module + handler_registry.function");
});

test("describes report rendering as a template-backed executor step", () => {
  const descriptor = getStepScriptDescriptor(
    {
      ...baseStep,
      name: "render_stock_report",
      stepType: "render_report",
      action: { template_resource: "stock_report_markdown" }
    },
    []
  );

  assert.equal(descriptor.kind, "Template renderer");
  assert.equal(descriptor.language, "Python executor + Markdown template");
  assert.equal(descriptor.implementation, "WorkflowExecutor._execute_step(render_report)");
  assert.equal(descriptor.resourceName, "stock_report_markdown");
});

test("generates an inspectable Python Playwright preview from workflow steps", () => {
  const script = generatePlaywrightScriptPreview(
    [
      baseStep,
      {
        ...baseStep,
        id: 2,
        orderIndex: 1,
        name: "extract_stock_card",
        stepType: "run_handler",
        handlerRef: "naver_stock.extract_stock_card",
        action: { input_key: "page_text" },
        assertions: { required_output: ["company_name", "current_price"] }
      },
      {
        ...baseStep,
        id: 3,
        orderIndex: 2,
        name: "render_stock_report",
        stepType: "render_report",
        action: { template_resource: "stock_report_markdown" }
      }
    ],
    [naverHandler],
    [reportTemplate]
  );

  assert.match(script, /from playwright\.async_api import async_playwright/);
  assert.match(script, /await page\.goto/);
  assert.doesNotMatch(script, /from webworkflows\.handlers\.naver_stock import extract_stock_card/);
  assert.match(script, /BEGIN inlined handler module: webworkflows\.handlers\.naver_stock/);
  assert.match(script, /\ndef extract_stock_card\(\*, page_text, company_name, ticker=None, news_limit=3\):/);
  assert.doesNotMatch(script, /# def extract_stock_card/);
  assert.match(script, /\ndef _helper\(\):/);
  assert.doesNotMatch(script, /# def _helper/);
  assert.match(script, /handler_result = extract_stock_card/);
  assert.match(script, /stock_report_markdown/);
  assert.match(script, /asyncio\.run\(main\(\)\)/);
});

test("does not silently omit missing handler source in previews", () => {
  const script = generatePlaywrightScriptPreview(
    [
      {
        ...baseStep,
        id: 4,
        name: "extract_stock_card",
        stepType: "run_handler",
        handlerRef: "naver_stock.extract_stock_card"
      }
    ],
    [
      {
        ...naverHandler,
        sourceText: ""
      }
    ],
    []
  );

  assert.doesNotMatch(script, /MISSING handler source/);
  assert.match(script, /BEGIN missing handler stub: webworkflows\.handlers\.naver_stock\.extract_stock_card/);
  assert.match(script, /\ndef extract_stock_card\(\*args, \*\*kwargs\):/);
  assert.match(script, /raise RuntimeError\("Missing handler source: webworkflows\.handlers\.naver_stock\.extract_stock_card"\)/);
});
