# WebMCP VLM Evaluation

WebMCP의 Eval & Evolve는 Playwright로 workflow step을 실제 브라우저에서 실행하고,
각 step의 screenshot, page text, URL, title, handler output, assertion을
Codex VLM evaluator에 보냅니다. 평가 결과는 고정 JSON schema로 받아
`workflow_runs`, `step_runs`, `evolution_attempts`, Desktop UI에 기록합니다.

## Current Default

기본 CLI 옵션은 다음과 같습니다.

```bash
python3 -m webworkflows.cli run-version \
  --eval-and-evolve \
  --vlm-evaluator codex \
  --vlm-model gpt-5.5
```

`--vlm-evaluator codex`는 `webworkflows.vlm_codex.CodexAppServerVisionLanguageEvaluator`
를 사용합니다. 이 evaluator는 `codex app-server --stdio`를 장기 실행 JSON-RPC
프로세스로 띄우고, 로컬 Codex OAuth 로그인(`~/.codex/auth.json` 또는 OS credential
store)을 재사용합니다.

중요한 점:

- API key가 필요하지 않습니다.
- 매 step마다 `codex exec` subprocess를 새로 띄우지 않습니다.
- 기본 모델은 `gpt-5.5`입니다.
- screenshot은 `localImage` 입력으로 전달됩니다.
- final answer는 `outputSchema`로 고정된 JSON만 허용합니다.
- 평가용 thread는 `read-only`, `approvalPolicy=never`, `ephemeral=true`로 시작합니다.

## Evaluator Options

현재 CLI 선택지는 두 가지입니다.

```text
--vlm-evaluator codex            # default: Codex app-server + Codex OAuth
--vlm-evaluator openai-responses # optional: Platform API key + /v1/responses
```

Desktop은 evaluator 선택을 UI에 노출하지 않고 항상 `--vlm-evaluator codex`를
붙입니다. 이 동작은 `apps/desktop/electron/update-command.cjs`의
`appendEvalAndEvolveArgs()`에서 관리합니다.

## Code Map

VLM 경로를 바꿀 때 확인할 파일은 다음입니다.

- `core/webworkflows/vlm_codex.py`: evaluator 구현.
- `core/webworkflows/cli.py`: `--vlm-evaluator` 선택지와 기본 evaluator 생성.
- `core/webworkflows/eval_loop.py`: Playwright evidence 수집과 evaluator lifecycle.
- `core/tests/test_eval_and_evolve_loop.py`: evaluator contract 테스트.
- `apps/desktop/electron/update-command.cjs`: Desktop이 Core CLI에 전달하는 evaluator 옵션.
- `apps/desktop/tests/updateCommand.test.cjs`, `apps/desktop/tests/coreClient.test.cjs`: Desktop CLI argument contract.

## Switching To Another VLM Path

새 VLM 경로를 사용할 수 있게 되면 다음 순서로 바꿉니다.

1. `core/webworkflows/vlm_codex.py`에 새 evaluator class를 추가합니다.
2. 새 evaluator가 `EvaluationSnapshot`과 `criteria`를 받아 `StepEvaluation`을
   반환하게 합니다.
3. screenshot path는 반드시 absolute path로 전달합니다. 상대 경로는 Core cwd 기준
   resolve해야 합니다.
4. 모델 응답은 `CODEX_VLM_RESPONSE_SCHEMA`와 동일한 JSON이어야 합니다.
5. `core/webworkflows/cli.py`의 `add_eval_loop_args()`에 evaluator 이름을 추가합니다.
6. `build_evaluation_loop()`에서 새 evaluator를 생성합니다.
7. Desktop 기본값까지 바꿀 경우 `apps/desktop/electron/update-command.cjs`의
   `appendEvalAndEvolveArgs()`를 수정합니다.
8. Core test와 Desktop argument test를 먼저 RED/GREEN으로 갱신합니다.
9. Naver Maps smoke를 실제로 실행해 browser evidence, VLM JSON, final output을 확인합니다.

## Expected JSON

모든 evaluator는 아래 shape를 반환해야 합니다.

```json
{
  "status": "passed",
  "summary": "현재 화면에 요청한 결과가 보입니다.",
  "problems": [],
  "suggested_update": "",
  "failure_kind": "",
  "expected_state": "기대 상태",
  "observed_state": "관찰 상태",
  "repair_focus": "",
  "evidence_artifacts": ["outputs/.../step_05_result.png"]
}
```

`status`는 `passed` 또는 `failed`만 허용합니다. `assertion_error`가 있으면 모델이
`passed`를 반환해도 Core가 실패로 덮어씁니다.

## Smoke Test

Codex OAuth app-server 경로가 동작하는지 빠르게 보려면 Core root에서 실행합니다.

```bash
python3 - <<'PY'
from pathlib import Path
import base64
import tempfile

from webworkflows.eval_loop import EvaluationSnapshot
from webworkflows.vlm_codex import CodexAppServerVisionLanguageEvaluator

png = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)

with tempfile.TemporaryDirectory() as tmp:
    shot = Path(tmp) / "step.png"
    shot.write_bytes(png)
    evaluator = CodexAppServerVisionLanguageEvaluator(model="gpt-5.5", cwd=tmp)
    try:
        result = evaluator.evaluate(
            EvaluationSnapshot(
                step_name="oauth_smoke",
                step_type="wait_for_text",
                phase="intermediate",
                user_request="VLM OAuth smoke test",
                url="https://example.test",
                title="Smoke",
                page_text="The page contains the marker oauth app-server ok.",
                screenshot_path=str(shot),
                output={},
            ),
            {"assertions": {"contains_any": ["oauth app-server ok"]}},
        )
        print(result.status, result.evidence["vlm_evaluator"], result.evidence["codex_model"])
    finally:
        evaluator.close()
PY
```

성공하면 `passed codex_app_server gpt-5.5` 형태로 출력됩니다.

## Naver Maps QA

대표 QA는 다음 명령입니다.

```bash
cd webmcp/core
python3 -m webworkflows.cli create-workflow \
  --db outputs/qa_naver_map/workflows.sqlite \
  --output-dir outputs/qa_naver_map/runs \
  --start-url "https://www.naver.com" \
  --task "네이버 홈에서 네이버 지도로 이동한 뒤, 지하철 대중교통 경로로 양재역에서 사당역까지 몇 분 걸리는지 검색한다." \
  --final-state "네이버 지도 대중교통 길찾기 결과에 양재역에서 사당역까지 지하철 소요 시간이 표시되어야 한다." \
  --argument start_station=양재역 \
  --argument end_station=사당역 \
  --synthesizer codex \
  --synthesizer-model gpt-5.5 \
  --max-attempts 1 \
  --eval-and-evolve \
  --vlm-evaluator codex \
  --eval-browser chromium
```

성공 기준은 `status=succeeded`, `workflow=naver_map_transit_route`, output에
`duration_text`, `duration_minutes`, `report_text`가 포함되는 것입니다.
