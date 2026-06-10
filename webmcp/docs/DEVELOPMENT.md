# WebMCP 개발 가이드

이 문서는 새 구조에서 어디서 어떤 명령을 실행해야 하는지 정리합니다. Python
명령은 `webmcp/core`에서, Desktop 명령은 `webmcp/apps/desktop`에서 실행합니다.
처음 환경을 띄우거나 장애 대응까지 한 번에 보려면 [RUNBOOK.md](RUNBOOK.md)를
먼저 따라갑니다. 이 문서는 검증 명령을 빠르게 찾는 reference입니다.

## 개발 루프

```mermaid
flowchart LR
  Change["코드/문서 수정"]
  CoreTest["Core unittest"]
  NodeTest["Desktop unit test"]
  Typecheck["TypeScript typecheck"]
  Build["Vite build"]
  Sidecar["Rust sidecar test/build"]
  Smoke["npm run dev smoke"]

  Change --> CoreTest
  Change --> NodeTest
  NodeTest --> Typecheck
  Typecheck --> Build
  Build --> Sidecar
  Sidecar --> Smoke
```

## Core 검증

```bash
cd webmcp/core
python3 -m unittest tests/test_repo_structure.py tests/test_workflow_runtime_service.py tests/test_workflow_update_runtime_service.py tests/test_synthesis_provider_port.py tests/test_workflow_tools.py tests/test_text_default_vision_fallback.py
```

`tests/test_repo_structure.py`는 feature slice 구조, 문서 entry point, 한글
문서화, Mermaid 다이어그램 개수를 함께 확인합니다. 구조를 바꾸면 이 테스트를
먼저 갱신해야 합니다.

`tests/test_workflow_runtime_service.py`와
`tests/test_workflow_update_runtime_service.py`는 CLI와 다른 app adapter가 공유할
Core service payload를 고정합니다. `tests/test_synthesis_provider_port.py`는 모델
provider 이름이 흔들리지 않도록 확인합니다.

## Desktop 검증

```bash
cd webmcp/apps/desktop
npm run test:unit
npm run typecheck
npm run build
npm run sidecar:test
npm run sidecar:build
WEBMCP_DEV_SMOKE=1 npm run dev
```

```mermaid
flowchart TB
  Unit["npm run test:unit<br/>renderer/electron helper"]
  TS["npm run typecheck<br/>타입 안정성"]
  Vite["npm run build<br/>renderer bundle"]
  CargoTest["npm run sidecar:test<br/>SQLite sidecar"]
  CargoBuild["npm run sidecar:build<br/>실행 바이너리"]
  Dev["WEBMCP_DEV_SMOKE=1 npm run dev<br/>dev entrypoint"]

  Unit --> TS
  TS --> Vite
  Unit --> CargoTest
  CargoTest --> CargoBuild
  CargoBuild --> Dev
```

## Live workflow smoke

Naver 주가 workflow를 Desktop과 같은 방식으로 live page text를 수집해
실행하려면 다음 명령을 사용합니다.

```bash
cd webmcp/core
reference/webwright/.venv/bin/python -m webworkflows.cli run-version \
  --db outputs/webmcp_plugin_cold_iter_check/workflows.sqlite \
  --output-dir outputs/desktop_runs \
  --workflow-name naver_stock_report \
  --version 7 \
  --request "네이버에서 삼성전자 주가 리포트" \
  --company-name 삼성전자 \
  --ticker 005930 \
  --news-limit 1 \
  --live-page-text
```

## Ablation benchmark

Core behavior를 비교할 때는 고정된 ablation runner를 사용합니다.

```bash
cd webmcp
python3 core/scripts/run_ablation_studies.py --suite all
```

개발 중 빠르게 확인하려면 다음만 돌립니다.

```bash
python3 core/scripts/run_ablation_studies.py --suite fast --quick
```

각 suite의 역할은 다음과 같습니다.

- `baseline`: 저장 DB workflow 재사용, JS tool export, 기본 dynamic action 비교.
- `harder`: multi-variant browser task에서 static selector와 runtime dynamic action 비교.
- `memory`: page analysis와 script-generation knowledge 유무에 따른 synthesis/실행 성공률 비교.

결과는 `core/outputs/ablation_latest/consolidated_summary.md`에 모입니다. 이 경로는
ignored output이므로 benchmark 증거를 공유해야 할 때만 docs 보고서로 승격합니다.

## Ignore 기준

```mermaid
flowchart TD
  Generated["생성물"]
  Outputs["core/outputs"]
  Reference["core/reference/webwright"]
  Node["apps/desktop/node_modules"]
  Dist["apps/desktop/dist"]
  Target["apps/desktop/rust/**/target"]

  Generated --> Outputs
  Generated --> Reference
  Generated --> Node
  Generated --> Dist
  Generated --> Target
```

생성물은 fixture나 문서 증거로 승격할 때만 Git에 포함합니다. 일반 실행 산출물과
build output은 작업 디렉터리에 남기되 commit 대상에서 제외합니다.
