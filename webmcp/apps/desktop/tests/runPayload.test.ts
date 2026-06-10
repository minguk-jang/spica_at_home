import assert from "node:assert/strict";
import test from "node:test";

import { buildRunArgumentPayload } from "../src/features/run-workflow/model/runPayload.ts";
import type { WorkflowArgument } from "../src/vite-env";

test("includes visible generic workflow arguments in run payload", () => {
  const payload = buildRunArgumentPayload(
    [
      argument({ name: "start_url", orderIndex: 0 }),
      argument({ name: "username", orderIndex: 1 }),
      argument({ name: "password", orderIndex: 2 }),
      argument({ name: "page_text", orderIndex: 3 })
    ],
    {
      companyName: "",
      ticker: "",
      newsLimit: 3,
      extraArguments: {
        start_url: "https://the-internet.herokuapp.com/login",
        username: "tomsmith",
        password: "SuperSecretPassword!",
        page_text: "runtime-only evidence",
        empty: ""
      }
    }
  );

  assert.deepEqual(payload, {
    extraArguments: {
      start_url: "https://the-internet.herokuapp.com/login",
      username: "tomsmith",
      password: "SuperSecretPassword!"
    }
  });
});

test("keeps canonical stock arguments out of generic extra arguments", () => {
  const payload = buildRunArgumentPayload(
    [
      argument({ name: "company_name", orderIndex: 0 }),
      argument({ name: "ticker", orderIndex: 1 }),
      argument({ name: "news_limit", orderIndex: 2 })
    ],
    {
      companyName: "삼성전자",
      ticker: "005930",
      newsLimit: 3,
      extraArguments: {
        company_name: "ignored",
        ticker: "ignored",
        news_limit: 99
      }
    }
  );

  assert.deepEqual(payload, {
    companyName: "삼성전자",
    ticker: "005930",
    newsLimit: 3
  });
});

function argument(overrides: Partial<WorkflowArgument>): WorkflowArgument {
  return {
    id: overrides.id ?? overrides.orderIndex ?? 0,
    versionId: 1,
    name: overrides.name ?? "argument",
    description: overrides.description ?? "",
    valueType: overrides.valueType ?? "string",
    required: overrides.required ?? true,
    defaultValue: overrides.defaultValue ?? null,
    validation: {},
    examples: [],
    isDynamic: false,
    orderIndex: overrides.orderIndex ?? 0
  };
}
