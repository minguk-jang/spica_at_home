# `/webwright:craft`

요청받은 웹 작업을 재사용 가능한 CLI tool로 만듭니다. literal 값만 처리하는
one-shot script가 아니라, 나중에 다른 argument로 다시 실행할 수 있는
`final_script.py`를 작성해야 합니다.

## 절차

1. workspace를 만들고 `plan.md`를 작성합니다.
2. 사용자가 바꿀 수 있는 값을 parameter로 식별합니다.
3. DOM/text/ARIA/URL/response evidence를 우선해 Playwright로 탐색합니다.
4. screenshot은 감사용으로 저장하고, 구조화 evidence가 부족할 때만 vision
   fallback으로 사용합니다.
5. `final_script.py`는 typed function argument와 `argparse --flag`를 모두 가져야
   합니다.
6. argument 없이 실행했을 때 원래 사용자 요청을 그대로 재현해야 합니다.
7. action log의 첫 줄에 resolved parameter를 기록합니다.

## WebMCP workflow 동시 생성

이 결과를 현재 repo의 workflow cache로 관리하려면 workspace에 `workflow.json`도
작성합니다. active Codex 모델이 JSON을 직접 만들고 local CLI가 DB에 반영합니다.

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

Core가 synthesis를 맡아야 하면 `--synthesizer codex`를 사용할 수 있습니다. 이
경로는 Codex app-server JSON-RPC를 사용해야 하며 nested `codex exec`를 시작하면
안 됩니다.

Task:

```text
$ARGUMENTS
```
