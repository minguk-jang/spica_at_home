---
name: webwright
description: 사용자가 웹 작업 자동화, 브라우저 조작, 검색, 필터링, 폼 입력, 데이터 추출, Playwright 스크립트 재사용, text-first evidence, vision fallback, headed 실행을 요청할 때 사용한다.
allowed-tools: Bash, Read, Write, Edit, bash, read_file, write_file
---

# Webwright Text-Default + Vision-Fallback

이 skill은 Codex 안에서 직접 Playwright를 실행해 웹 작업을 해결합니다. 기본
경로로 standalone Python harness를 실행하지 않습니다. 특히 Codex 세션 안에서
`codex exec`를 model backend처럼 다시 호출하면 시작이 느려지고 timeout 위험이
커지므로 금지합니다. Core LLM 호출이 필요하면 Codex app-server 경로를 사용합니다.

정책 sentinel:

- Text-default mode
- Vision fallback
- Do not send screenshots to the default text model
- No nested Codex
- Do not launch the standalone Python harness as the default path
- WebMCP Workflow Optimization
- Use Codex app-server for Core-managed Codex synthesis

## 원칙

```mermaid
flowchart LR
  Task["사용자 웹 작업"]
  DOM["DOM/text/ARIA evidence"]
  Script["Playwright final_script.py"]
  Shot["screenshot artifacts"]
  Vision["vision fallback"]
  Report["최종 보고"]

  Task --> DOM
  DOM --> Script
  Script --> Shot
  DOM --> Report
  Shot -->|구조화 증거로 부족할 때만| Vision
  Vision --> Report
```

- 기본 모드는 text-only라고 가정합니다. `gpt-5.5`는 DOM, locator,
  URL, response, ARIA snapshot, action log를 우선 사용합니다.
- screenshot은 감사용 artifact로 저장합니다. 기본 text model 입력으로 보내지
  않습니다.
- 시각 상태가 DOM/ARIA/log로 증명되지 않을 때만 vision-capable model이나 host
  시각 도구를 fallback으로 사용합니다.
- `python -m webwright.run.cli`와 `model_codex_oauth_text_vision.yaml` 조합은
  명시적인 harness 테스트 요청이 있을 때만 사용합니다.

## 필수 작업 흐름

1. 현재 디렉터리 아래 task-specific workspace를 만듭니다.
2. `plan.md`에 task, start URL, 제약, 성공 기준, critical point를 적습니다.
3. Playwright script로 DOM/text/ARIA/URL/attribute/count를 먼저 탐색합니다.
4. screenshot은 저장하되, 구조화 evidence가 부족한 critical point에만 vision
   fallback을 기록합니다.
5. clean browser context에서 다시 실행 가능한 `final_script.py`를 작성합니다.
6. `final_runs/run_<id>/` 아래 action log와 screenshot을 저장합니다.
7. 최종 응답에서 script path, action log, screenshot folder, text evidence와
   vision fallback 사용 여부를 구분해 보고합니다.

## WebMCP workflow 최적화

재사용 가능한 결과는 Codex agent skill이 아니라 **WebMCP workflow**라고 부릅니다.
WebMCP workflow는 SQLite에 저장되는 arguments, steps, resources, handlers, run
history, update events입니다.

Codex 안에서 cold init을 만들 때는 active Codex 모델이 `workflow.json`을 직접
작성하고, local CLI가 이를 materialize합니다.

```bash
python3 -m webworkflows.cli intelligent-cold-init \
  --db outputs/webmcp_workflows/workflows.sqlite \
  --output-dir outputs/webmcp_workflows/runs \
  --request "<user request>" \
  --company-name "<company>" \
  --ticker "<ticker>" \
  --page-text-file "<discovered text file>" \
  --synthesizer agent-json \
  --workflow-json-file "<workspace>/workflow.json"
```

Codex 세션 안에서 Core가 직접 synthesis를 맡아야 하면 `--synthesizer codex`를
사용합니다. 이 경로는 Codex app-server JSON-RPC를 사용해야 하며 nested
`codex exec`를 시작하면 안 됩니다.

## Headed mode

사용자가 브라우저가 보이길 원하면 shell 환경에 `WEBWRIGHT_HEADLESS=0`을 설정하고
generated script는 환경변수에서 headless 여부를 읽습니다.

```python
headless = os.environ.get("WEBWRIGHT_HEADLESS", "1") not in {"0", "false", "False"}
browser = await playwright.chromium.launch(headless=headless)
```

## 증거 정책

- `inner_text`, `text_content`, `get_attribute`, `is_checked`, `is_visible`,
  `count`, URL assertion, response payload, `aria_snapshot`을 우선합니다.
- visual success를 screenshot path만으로 주장하지 않습니다.
- canvas/image-only 상태는 vision fallback을 사용하고, 어떤 screenshot에서 어떤
  visual claim을 확인했는지 기록합니다.

## 모드

- `/webwright:run <task>`: literal 값으로 one-shot script를 작성합니다.
- `/webwright:craft <task>`: 재사용 가능한 CLI tool을 작성합니다. 변동 가능한 값은
  function argument와 `argparse` flag로 노출해야 합니다.
