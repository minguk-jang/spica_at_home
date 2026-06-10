# WebMCP Core Ablation Study - 2026-06-10

## 요약

WebMCP core는 `cli.py` 진입점에서 `services/*`, `storage.py`, `loader.py`, `executor.py`, `synthesis.py`, `eval_loop.py`, `page_memory.py`로 나뉜다. 이번 조사는 저장 workflow 재사용, cold/create 경로, JS tool export, page/knowledge memory, runtime dynamic action을 대상으로 했다.

실험은 격리 DB와 ignored artifact 경로인 `core/outputs/ablation_study_20260610/`에서 수행했다. Persistent 제품 DB `~/.webmcp-studio/db/workflows.sqlite`는 읽기 전용으로만 확인했으며, 현재 workflow 14개, page analysis 7개, knowledge entry 13개가 있었다.

핵심 결과:

| 예제 | Ablation | 성공률 변화 | 평균 wall time 변화 |
|---|---:|---:|---:|
| Naver stock fixture | `cold-init static` -> 저장 DB `run-version` | 100% -> 100% | 283.3ms -> 225.7ms, 20.3% 감소 |
| Naver map route fixture | `known_workflow_create` -> 저장 DB `run-version` | 100% -> 100% | 282.3ms -> 227.0ms, 19.6% 감소 |
| Dynamic ad local browser | modal 전용 static selector -> runtime dynamic action | 33.3% -> 100% | 12,894.7ms -> 5,709.0ms, 55.7% 감소 |

Dynamic ad의 시간 감소는 static selector가 banner/rail variant에서 15초 timeout을 밟기 때문이다. 즉 동적 UI에서는 runtime script generation이 순수 속도 최적화라기보다 실패 timeout을 제거해 성공률과 평균 실행 시간을 동시에 개선했다.

## Core Logic 조사

### 저장소와 DB

- `storage.py`는 기본 DB 경로를 `WEBMCP_STUDIO_DB_PATH`가 있으면 그 값, 없으면 `~/.webmcp-studio/db/workflows.sqlite`로 잡는다.
- 주요 테이블은 `workflow_tools`, `workflow_tool_versions`, `workflow_tool_steps`, `workflow_runs`, `step_runs`, `page_analyses`, `workflow_knowledge_entries`, `workflow_creation_sessions`, `evolution_sessions`다.
- `WorkflowMaterializer`는 같은 `skill_name` 또는 `slug`가 이미 있으면 새 workflow를 만들지 않고 기존 `latest_version_id`를 재사용한다.

### 생성 경로

- `cold-init`: static 또는 Naver browser discovery로 fixed workflow를 materialize한 뒤 첫 실행까지 수행한다.
- `intelligent-cold-init`/`create-workflow`: trace를 page analysis와 recent script-generation knowledge로 enrich한 뒤 `LLMWorkflowSynthesizer`에 전달한다.
- `synthesis.py`는 Naver Map route처럼 알려진 task shape를 감지하면 generic LLM backend를 호출하지 않고 `known_naver_map_route` workflow JSON을 반환한다.
- `agent-json` synthesizer는 Codex 세션 안에서 nested `codex exec`를 피하면서 사람이 만든 workflow JSON을 materialize하는 경로다.

### Page Analysis와 Knowledge

- URL key는 query/fragment 제거 후 host/path를 kebab-case로 변환한다. 예: `https://example.com/search?q=x` -> `example-com-search`.
- page analysis는 page type, stable markers, selector strategy, assertion strategy, extraction tips, risk notes를 저장한다.
- script-generation knowledge는 성공/실패한 workflow evidence에서 재사용 가능한 팁을 만든다. 좋은 entry는 URL shape, wait marker, selector/handler, failure mode, output assertion을 포함한다.
- 실험에서 memory enrich overhead는 예제당 약 7.0-7.7ms였고, prompt context는 약 1.6k-2.6k chars 증가했다.

| 예제 | Enrich overhead | Prompt 증가 | 확인된 효과 |
|---|---:|---:|---|
| Naver stock | 7.0ms | +2,578 chars | `증권정보`, `현재가`, direct search URL, handler tip 포함 |
| Books product | 7.7ms | +1,631 chars | URL key와 selector/wait knowledge 포함 |
| Dynamic controls | 7.5ms | +2,026 chars | async wait marker knowledge 포함 |

### 실행 경로

- `WorkflowRuntime.run_latest`는 `WorkflowSkillLoader.search()`로 stable workflow를 고르고, `run-version`은 검색 없이 지정 version을 로드한다.
- `WorkflowExecutor`는 `goto`, `wait_for_text`, `run_handler`, `assert_output`, `render_report`를 deterministic하게 수행한다.
- `click`, `fill`, `press`, `select_suggestion`은 browser evaluation loop가 켜졌을 때 실제 브라우저에서 수행되고, 일반 executor에서는 evidence만 기록한다.
- `llm_browser_action`은 workflow DB에 script를 저장하지 않는다. DB에는 instruction/success criteria/allowed operations만 저장하고, browser runtime에서 일회성 JavaScript를 생성해 실행한다.
- `export-js-tool`은 저장 workflow를 `manifest.json`, `workflow.json`, `tool.cjs`로 패키징한다. JS runtime은 deterministic step과 built-in handler를 지원하지만 `llm_browser_action`은 Python browser evaluation runtime을 요구한다.

## 실험 설계

반복 횟수는 mode당 3회다. Dynamic ad는 3개 variant(`modal`, `banner`, `rail`)를 3회씩 실행해서 mode당 9 trial이다.

측정값:

- `wall_ms`: CLI 또는 browser run 전체 wall-clock time.
- `core_duration_ms`: DB에 기록된 `workflow_runs.duration_ms` 또는 create/cold-init payload의 first run duration. JS tool은 DB 기록이 없으므로 공란이다.
- 성공 기준: command exit 0, payload status succeeded/passed, task별 required output key 존재.

Raw artifacts:

- `core/outputs/ablation_study_20260610/results.json`
- `core/outputs/ablation_study_20260610/summary.md`
- `core/outputs/ablation_study_20260610/memory_prompt_ablation.json`
- `core/outputs/ablation_study_20260610/browser/**`

## 결과

### 1. Naver Stock Report

Fixture: `core/tests/fixtures/naver_stock_text.txt`

| Mode | n | 성공 | 평균 wall | 중앙 wall | 평균 core |
|---|---:|---:|---:|---:|---:|
| `cold_init_static` | 3 | 3/3 | 283.3ms | 271ms | 20.0ms |
| `stored_db_run_version` | 3 | 3/3 | 225.7ms | 207ms | 14.3ms |
| `exported_js_tool` | 3 | 3/3 | 249.7ms | 250ms | n/a |

저장 DB workflow 재사용은 cold init 대비 평균 wall time을 57.6ms 줄였다. 이 fixture는 LLM/browser discovery가 없는 static cold-init이라 절대 차이는 작다. 실제 Codex synthesis 또는 live browser discovery가 포함되면 재사용 이득은 훨씬 커진다.

JS tool은 cold init보다는 빨랐지만 DB `run-version`보다는 느렸다. 이 실험에서는 Node 프로세스 시작 비용이 Python DB 재사용보다 커서, JS export는 속도 최적화보다는 배포/패키징 가치가 더 크다.

### 2. Naver Map Transit Route

Fixture: `core/tests/fixtures/naver_map_route_text.txt`

| Mode | n | 성공 | 평균 wall | 중앙 wall | 평균 core |
|---|---:|---:|---:|---:|---:|
| `known_workflow_create` | 3 | 3/3 | 282.3ms | 282ms | 34.7ms |
| `stored_db_run_version` | 3 | 3/3 | 227.0ms | 227ms | 34.7ms |
| `exported_js_tool` | 3 | 3/3 | 247.3ms | 248ms | n/a |

`known_workflow_create`는 generic LLM 호출을 우회하는 known-workflow fast path다. 그래도 creation session, trace enrichment, materialization을 거치므로 저장 DB 실행보다 평균 55.3ms 느렸다.

저장 workflow는 성공률을 유지하면서 create overhead를 제거했다. JS tool도 성공률은 같았지만 DB 실행보다 약간 느렸다.

### 3. Dynamic Ad Local Browser

Local site: `core/demo_sites/dynamic_ad_demo/index.html`

| Mode | n | 성공 | 평균 wall | 중앙 wall | 실패 원인 |
|---|---:|---:|---:|---:|---|
| `stored_static_modal_selector` | 9 | 3/9 | 12,894.7ms | 16,510ms | banner/rail에서 `[data-testid='sponsor-close']` timeout |
| `runtime_dynamic_action` | 9 | 9/9 | 5,709.0ms | 5,706ms | 없음 |

Static selector baseline은 modal variant에서 학습한 selector만 저장한 상태를 시뮬레이션했다. modal은 성공했지만 banner와 rail은 close button label/attribute가 달라 15초 timeout으로 실패했다.

Runtime dynamic action은 workflow에 script를 저장하지 않고 instruction과 success criteria만 저장했다. 실험에서는 Codex CLI 대신 local heuristic planner를 사용해 브라우저 runtime 경로를 deterministic하게 검증했다. 따라서 실제 Codex dynamic planner를 쓰면 모델 생성 latency가 추가될 수 있다. 그래도 이 구조가 variable UI chrome에서 성공률을 크게 올린다는 점은 확인됐다.

## 해석

저장 workflow 재사용은 static fixture에서도 약 20% wall time을 줄였다. 이 수치는 subprocess startup이 지배적인 작은 fixture에서 나온 보수적 수치다. 실제 browser discovery, Codex synthesis, eval/evolve가 포함된 cold path에서는 재사용 이득이 초 단위로 커질 가능성이 높다.

Page analysis와 knowledge memory는 실행 시간보다 생성 품질에 영향을 주는 축이다. 현재 core에서는 creation trace마다 page analysis를 upsert하고 recent knowledge 5개를 prompt에 넣는다. Overhead는 10ms 미만으로 낮고, prompt에는 URL key, stable marker, selector strategy, risk note가 실제 포함됐다. Live LLM 기반 성공률 ablation은 별도 비용/시간이 필요하며, Codex 세션 안에서는 nested `codex exec`를 기본 경로로 쓰지 않는다는 운영 지침을 따라 이번에는 제외했다.

Runtime dynamic action은 변동 UI에서 성공률을 33.3%에서 100%로 올렸다. 실패 timeout까지 포함한 평균 시간은 55.7% 감소했다. 단, 안정적인 selector가 이미 있는 페이지라면 deterministic stored selector가 더 빠를 수 있으므로, dynamic action은 광고/팝업/변동 chrome처럼 selector가 흔들리는 단계에 제한하는 편이 맞다.

## 권장사항

1. 저장 DB workflow 재사용을 기본 실행 경로로 유지한다. `run-version`은 생성/검색 비용을 피하고 성공률 손실이 없었다.
2. Naver stock은 direct search URL, `증권정보`/`현재가`/ticker wait marker, `naver_stock.extract_stock_card` handler를 유지한다.
3. Naver Map route는 known workflow fast path와 `naver_map.extract_subway_duration` handler를 유지한다. Generic LLM 호출을 피하는 현재 구조가 적절하다.
4. `llm_browser_action`은 변동 UI chrome에만 쓴다. 안정적인 form/click step은 selector 기반 deterministic step으로 유지해야 한다.
5. Page analysis/knowledge memory는 overhead가 낮으므로 계속 켠다. 다만 실험성을 높이려면 `WEBMCP_DISABLE_PAGE_MEMORY=1` 같은 내부 benchmark flag를 추가해 live LLM 생성 성공률을 비교할 수 있게 하는 것이 좋다.
6. JS tool export는 portability와 external runtime packaging 용도로 본다. 이 실험에서는 Python DB `run-version`보다 빠르지 않았다.
7. 성능 regression을 잡기 위해 이 harness를 정식 benchmark로 승격한다면, dynamic 실패 timeout을 줄인 별도 benchmark profile과 live VLM profile을 분리해야 한다.

## 재현 명령

```bash
cd /Users/mingukjang/git/spica_at_home/webmcp
core/reference/webwright/.venv/bin/python core/outputs/ablation_study_20260610/run_ablation.py
```

기준 unit test:

```bash
cd /Users/mingukjang/git/spica_at_home/webmcp/core
python3 -m unittest tests.test_page_memory tests.test_workflow_creation_runtime_service -q
```
