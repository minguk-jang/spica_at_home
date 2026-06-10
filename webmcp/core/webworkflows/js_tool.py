from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from webworkflows.loader import WorkflowSkillLoader
from webworkflows.storage import WorkflowSkillStore, dumps
from webworkflows.update_proposal import workflow_json_from_skill


@dataclass(frozen=True)
class ExportedJsTool:
    tool_dir: Path
    manifest: dict[str, Any]
    workflow_json: dict[str, Any]


class JsToolRuntimeError(RuntimeError):
    pass


class JsToolExporter:
    def __init__(self, store: WorkflowSkillStore):
        self.store = store

    def export(self, *, workflow_name: str, version: int, output_dir: str | Path) -> ExportedJsTool:
        skill = WorkflowSkillLoader(self.store).load_skill_version(workflow_name, version)
        workflow_json = workflow_json_from_skill(self.store, skill)
        manifest = {
            "name": skill.name,
            "version": skill.version,
            "description": skill.description,
            "domain": skill.domain,
            "task_type": skill.task_type,
            "runtime": "webmcp-js-tool-v1",
            "entrypoint": "tool.cjs",
            "input_schema": skill.input_schema,
            "output_schema": skill.output_schema,
        }
        slug = str(workflow_json.get("slug") or skill.name.replace("_", "-"))
        tool_dir = Path(output_dir) / f"{slug}-v{skill.version}"
        tool_dir.mkdir(parents=True, exist_ok=True)
        (tool_dir / "manifest.json").write_text(dumps(manifest), encoding="utf-8")
        (tool_dir / "workflow.json").write_text(dumps(workflow_json), encoding="utf-8")
        (tool_dir / "tool.cjs").write_text(JS_TOOL_RUNTIME, encoding="utf-8")
        return ExportedJsTool(tool_dir=tool_dir, manifest=manifest, workflow_json=workflow_json)


def run_js_tool(tool_dir: str | Path, arguments: dict[str, Any], *, node_binary: str = "node") -> dict[str, Any]:
    tool_path = Path(tool_dir) / "tool.cjs"
    completed = subprocess.run(
        [node_binary, str(tool_path)],
        input=json.dumps(arguments, ensure_ascii=False, sort_keys=True),
        text=True,
        capture_output=True,
    )
    if not completed.stdout.strip():
        raise JsToolRuntimeError(
            f"javascript tool produced no JSON output (exit={completed.returncode}). stderr={completed.stderr}"
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise JsToolRuntimeError(f"javascript tool returned invalid JSON: {completed.stdout}") from exc
    if completed.returncode != 0:
        message = payload.get("message") or payload.get("error") or completed.stderr
        raise JsToolRuntimeError(f"javascript tool failed: {message}")
    return payload


def eval_js_tool(
    tool_dir: str | Path,
    arguments: dict[str, Any],
    *,
    required_output: list[str] | None = None,
    node_binary: str = "node",
) -> dict[str, Any]:
    run_payload = run_js_tool(tool_dir, arguments, node_binary=node_binary)
    output = run_payload.get("output") if isinstance(run_payload.get("output"), dict) else {}
    missing = [
        key
        for key in (required_output or [])
        if output.get(key) in (None, "")
    ]
    return {
        "passed": run_payload.get("status") == "succeeded" and not missing,
        "missing_output": missing,
        "run": run_payload,
    }


JS_TOOL_RUNTIME = r'''#!/usr/bin/env node
"use strict";

const manifest = require("./manifest.json");
const workflow = require("./workflow.json");

async function run(args = {}) {
  const resolvedArgs = resolveArguments(workflow, args);
  const context = {
    arguments: resolvedArgs,
    url: null,
    pageText: String(resolvedArgs.page_text || ""),
    output: {},
    reportText: ""
  };
  const stepResults = [];

  for (const step of workflow.steps || []) {
    const result = executeStep(step, context);
    Object.assign(context.output, result.output || {});
    stepResults.push({
      name: step.name,
      step_type: step.step_type,
      status: "succeeded",
      evidence: result.evidence || {}
    });
  }

  return {
    status: "succeeded",
    workflow: manifest.name,
    workflow_version: manifest.version,
    output: context.output,
    steps: stepResults
  };
}

function executeStep(step, context) {
  if (step.step_type === "goto") {
    const url = renderTemplate(String((step.action || {}).url_template || ""), context.arguments);
    context.url = url;
    return { output: { url, final_url: url }, evidence: { url } };
  }

  if (step.step_type === "llm_browser_action") {
    throw new Error("llm_browser_action requires the browser evaluation runtime; run this workflow through Python run-version --eval-and-evolve");
  }

  if (["click", "click_text", "fill", "press", "select_suggestion"].includes(step.step_type)) {
    return { output: {}, evidence: { browser_action: step.step_type, action: renderValue(step.action || {}, context) } };
  }

  if (step.step_type === "wait_for_text") {
    const expected = ((step.assertions || {}).contains_any || []).map((item) => renderTemplate(String(item), context.arguments));
    const matched = expected.filter((item) => item && context.pageText.includes(item));
    if (expected.length > 0 && matched.length === 0) {
      throw new Error(`none of the expected text markers were found: ${JSON.stringify(expected)}`);
    }
    return { output: {}, evidence: { matched_any: matched } };
  }

  if (step.step_type === "run_handler") {
    const handlerRef = step.handler_ref;
    const handler = builtInHandlers[handlerRef];
    if (!handler) {
      throw new Error(`handler not available in javascript tool: ${handlerRef}`);
    }
    const handlerOutput = handler(handlerInput(step, context));
    for (const key of ((step.assertions || {}).required_output || [])) {
      if (handlerOutput[key] === undefined || handlerOutput[key] === null || handlerOutput[key] === "") {
        throw new Error(`handler output missing required key: ${key}`);
      }
    }
    return { output: handlerOutput, evidence: { handler_ref: handlerRef } };
  }

  if (step.step_type === "assert_output") {
    const output = context.output;
    const equals = (step.assertions || {}).equals || {};
    const optionalEquals = (step.assertions || {}).optional_equals || {};
    for (const [key, template] of Object.entries(equals)) {
      if (template === null || template === undefined) continue;
      const expected = renderTemplate(String(template), context.arguments);
      if (String(output[key]) !== expected) {
        throw new Error(`output[${JSON.stringify(key)}] expected ${JSON.stringify(expected)}, got ${JSON.stringify(output[key])}`);
      }
    }
    for (const [key, template] of Object.entries(optionalEquals)) {
      if (template === null || template === undefined) continue;
      const expected = renderTemplate(String(template), context.arguments);
      if (expected && output[key] && String(output[key]) !== expected) {
        throw new Error(`output[${JSON.stringify(key)}] expected ${JSON.stringify(expected)}, got ${JSON.stringify(output[key])}`);
      }
    }
    for (const key of ((step.assertions || {}).required_output || [])) {
      if (output[key] === undefined || output[key] === null || output[key] === "") {
        throw new Error(`output missing required key: ${key}`);
      }
    }
    return { output: {}, evidence: { validated: true } };
  }

  if (step.step_type === "render_report") {
    const resourceName = (step.action || {}).template_resource;
    const resource = (workflow.resources || []).find((item) => item.name === resourceName);
    if (!resource) {
      throw new Error(`report template resource not found: ${resourceName}`);
    }
    const renderContext = templateValues(context);
    const currentPrice = Number(context.output.current_price || 0);
    renderContext.current_price_formatted = Number.isFinite(currentPrice) ? currentPrice.toLocaleString("en-US") : "";
    const reportText = renderTemplate(String(resource.content_text || ""), renderContext);
    context.reportText = reportText;
    return {
      output: {
        final_url: context.url || "",
        page_text: context.pageText || "",
        report_text: reportText,
        report_markdown: reportText,
        markdown_report: reportText,
        status: "passed"
      },
      evidence: { template_resource: resourceName }
    };
  }

  throw new Error(`unsupported workflow step type: ${step.step_type}`);
}

function resolveArguments(workflowDef, args) {
  const resolved = { ...args };
  const missing = [];
  for (const argument of workflowDef.arguments || []) {
    if (resolved[argument.name] === undefined && argument.default_value !== null && argument.default_value !== undefined) {
      resolved[argument.name] = argument.default_value;
    }
    if (argument.required && !resolved[argument.name]) {
      missing.push(argument.name);
    }
  }
  if (missing.length) {
    throw new Error(`missing required workflow arguments: ${missing.join(", ")}`);
  }
  return resolved;
}

function handlerInput(step, context) {
  const inputs = (step.action || {}).inputs;
  if (inputs && typeof inputs === "object" && !Array.isArray(inputs) && Object.keys(inputs).length > 0) {
    return renderValue(inputs, context);
  }
  return {
    ...templateValues(context),
    page_text: context.pageText,
    news_limit: context.arguments.news_limit || 3
  };
}

const builtInHandlers = {
  "naver_stock.extract_stock_card": extractStockCard,
  "naver_map.extract_subway_duration": extractSubwayDuration
};

function extractStockCard(input) {
  const pageText = String(input.page_text || "");
  const companyName = String(input.company_name || "");
  const ticker = String(input.ticker || firstMatch(pageText, /\b[0-9]{6}\b/) || "");
  const priceText = firstMatch(pageText, /[0-9]{1,3}(?:,[0-9]{3})+/);
  const currentPrice = priceText ? Number(priceText.replace(/,/g, "")) : 0;
  const changeText = firstLineMatching(pageText, /전일대비|[▲▼+-]?\s?[0-9,]+\s?\([+-]?[0-9.]+%\)/) || "review needed";
  const marketStatus = firstLineMatching(pageText, /KRX/) || "review needed";
  return {
    company_name: pageText.includes(companyName) ? companyName : firstNonEmptyLine(pageText),
    ticker,
    current_price: currentPrice,
    change_text: changeText,
    market_status: marketStatus,
    news_context: newsContext(pageText, Number(input.news_limit || 3))
  };
}

function extractSubwayDuration(input) {
  const pageText = normalizeSpace(String(input.page_text || ""));
  const startStation = String(input.start_station || "");
  const endStation = String(input.end_station || "");
  if (!pageText) throw new Error("page_text is required");
  if (!pageText.includes(startStation) || !pageText.includes(endStation)) {
    throw new Error(`route text does not include requested stations: ${startStation}, ${endStation}`);
  }
  const segment = bestRouteSegment(pageText, startStation, endStation);
  const durationMatch = segment.match(/(?<!\d)(\d{1,3})분/);
  if (!durationMatch) throw new Error("subway route duration was not found");
  const durationMinutes = Number(durationMatch[1]);
  const durationText = `${durationMinutes}분`;
  return {
    start_station: startStation,
    end_station: endStation,
    duration_text: durationText,
    duration_minutes: durationMinutes,
    route_summary: `${startStation} to ${endStation} takes about ${durationText}. ${segment.slice(0, 500).trim()}`
  };
}

function bestRouteSegment(text, startStation, endStation) {
  const candidates = text
    .split(/\s*상세보기\s*/)
    .map((segment) => segment.trim())
    .filter((segment) => segment.includes(startStation) && segment.includes(endStation));
  if (!candidates.length) throw new Error("no route segment found");
  return candidates.sort((left, right) => durationNumber(left) - durationNumber(right))[0];
}

function durationNumber(segment) {
  const match = segment.match(/(?<!\d)(\d{1,3})분/);
  return match ? Number(match[1]) : 9999;
}

function renderValue(value, context) {
  if (typeof value === "string") return renderTemplate(value, templateValues(context));
  if (Array.isArray(value)) return value.map((item) => renderValue(item, context));
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, renderValue(item, context)]));
  }
  return value;
}

function templateValues(context) {
  return {
    ...(context.arguments || {}),
    ...(context.output || {}),
    page_text: context.pageText || "",
    final_url: context.url || "",
    url: context.url || ""
  };
}

function renderTemplate(template, values) {
  let rendered = String(template);
  for (const [key, rawValue] of Object.entries(values || {})) {
    const value = rawValue === null || rawValue === undefined ? "" : String(rawValue);
    rendered = rendered.split(`{{${key}}}`).join(value);
    rendered = rendered.split("${" + key + "}").join(value);
    rendered = rendered.split(`{${key}}`).join(value);
  }
  return rendered;
}

function firstMatch(text, pattern) {
  const match = String(text || "").match(pattern);
  return match ? match[0].trim() : "";
}

function firstLineMatching(text, pattern) {
  for (const line of String(text || "").split(/\r?\n/)) {
    if (pattern.test(line)) return line.trim();
  }
  return "";
}

function firstNonEmptyLine(text) {
  return (String(text || "").split(/\r?\n/).map((line) => line.trim()).find(Boolean)) || "";
}

function newsContext(text, limit) {
  const lines = String(text || "").split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  const newsIndex = lines.findIndex((line) => line.includes("뉴스"));
  const start = newsIndex >= 0 ? newsIndex + 1 : 0;
  const selected = lines.slice(start, start + Math.max(limit, 0));
  return selected.length ? selected.map((line) => `- ${line}`).join("\n") : "- no related news";
}

function normalizeSpace(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

async function readStdinJson() {
  const raw = await new Promise((resolve, reject) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => { data += chunk; });
    process.stdin.on("end", () => resolve(data));
    process.stdin.on("error", reject);
  });
  return raw.trim() ? JSON.parse(raw) : {};
}

if (require.main === module) {
  readStdinJson()
    .then((input) => run(input))
    .then((result) => {
      process.stdout.write(`${JSON.stringify(result)}\n`);
    })
    .catch((error) => {
      process.stdout.write(`${JSON.stringify({
        status: "failed",
        error_type: error && error.name ? error.name : "Error",
        message: error && error.message ? error.message : String(error)
      })}\n`);
      process.exitCode = 1;
    });
}

module.exports = { manifest, workflow, run };
'''
