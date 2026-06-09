# `/webwright:run`

요청받은 웹 작업을 one-shot Playwright script로 해결합니다. 이 명령은 현재 Codex
세션 안에서 직접 실행되어야 하며, 사용자가 명시적으로 harness 테스트를 요청하지
않는 한 standalone `python -m webwright.run.cli`를 시작하지 않습니다.

## 절차

1. 이번 실행을 위한 workspace를 만듭니다.
2. `plan.md`에 critical point를 적고, DOM/text/ARIA/log evidence로 검증할 수 있는
   항목을 우선합니다.
3. 짧은 Playwright 탐색 script로 locator, visible text, URL, attribute,
   `aria_snapshot`을 출력합니다.
4. screenshot은 artifact로 저장하지만 기본 text model 입력으로 사용하지 않습니다.
5. 구조화 evidence로 증명할 수 없는 UI 상태에만 vision fallback을 사용합니다.
6. `final_runs/run_<id>/` 안에서 `final_script.py`를 작성하고 실행합니다.
7. 최종 보고에서 text evidence와 vision fallback 판단을 분리해 설명합니다.

## WebMCP workflow로 승격

사용자가 재사용이나 최적화를 원하면 또 다른 Codex skill을 만들지 말고 WebMCP
workflow를 만듭니다. workspace에 `workflow.json`을 작성한 뒤 nested Codex 없이
materialize합니다.

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

Codex 세션 안에서 `--synthesizer codex`를 사용하지 않습니다.
Do not use `--synthesizer codex` from inside Codex.

Task:

```text
$ARGUMENTS
```
