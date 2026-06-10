# WebMCP Memory Ablation Study - 2026-06-10

## 정정

초기 보고서와 harder rerun은 저장 workflow와 runtime dynamic action 효과를 주로 보여줬고, 처음 요청에 포함된 "노하우"와 "page analysis"의 with/without ablation을 제대로 분리하지 못했다. 이 문서는 그 누락분을 보완한다.

## 실험 질문

생성 전에 memory가 있을 때와 없을 때 workflow synthesis 결과와 실제 실행 성공률이 어떻게 달라지는가?

분리한 조건:

| Mode | Page analysis context | Script-generation knowledge | 의도 |
|---|---:|---:|---|
| `none` | 없음 | 없음 | memory 없는 생성 |
| `page_analysis_only` | 있음 | 없음 | current page text 분석만 있는 생성 |
| `knowledge_only` | 없음 | 있음 | reusable 노하우만 있는 생성 |
| `page_analysis_plus_knowledge` | 있음 | 있음 | page 분석과 노하우가 모두 있는 생성 |

태스크는 쉬운 fixture가 아니라 harder rerun의 3개 multi-variant browser task를 재사용했다.

- Dynamic ad review: `modal`, `banner`, `rail`
- Checkout wizard: `classic`, `compact`, `enterprise`
- Ticket triage: `table`, `cards`, `compact`

각 mode는 task별 3 variants를 1회씩 실행했다. 전체 36 browser trials다.

Raw artifacts:

- `core/outputs/ablation_memory_20260610/results.json`
- `core/outputs/ablation_memory_20260610/summary.md`
- `core/outputs/ablation_memory_20260610/run_memory_ablation.py`
- `core/outputs/ablation_memory_20260610/browser/**`

## 결과 요약

전체 aggregate:

| Memory mode | 성공률 | 평균 wall time | 생성된 workflow |
|---|---:|---:|---|
| `none` | 3/9, 33.3% | 12,942.2ms | static variant-A selectors |
| `page_analysis_only` | 3/9, 33.3% | 12,815.1ms | static variant-A selectors |
| `knowledge_only` | 9/9, 100% | 3,544.1ms | runtime dynamic action |
| `page_analysis_plus_knowledge` | 9/9, 100% | 3,515.7ms | runtime dynamic action |

Task별 상세:

| Task | Mode | 성공률 | 평균 wall time | Workflow kind |
|---|---|---:|---:|---|
| Dynamic ad review | `none` | 1/3, 33.3% | 13,161.3ms | static selectors |
| Dynamic ad review | `page_analysis_only` | 1/3, 33.3% | 12,781.3ms | static selectors |
| Dynamic ad review | `knowledge_only` | 3/3, 100% | 3,368.0ms | runtime dynamic action |
| Dynamic ad review | `page_analysis_plus_knowledge` | 3/3, 100% | 3,354.0ms | runtime dynamic action |
| Checkout wizard | `none` | 1/3, 33.3% | 12,980.7ms | static selectors |
| Checkout wizard | `page_analysis_only` | 1/3, 33.3% | 12,963.7ms | static selectors |
| Checkout wizard | `knowledge_only` | 3/3, 100% | 3,349.7ms | runtime dynamic action |
| Checkout wizard | `page_analysis_plus_knowledge` | 3/3, 100% | 3,332.3ms | runtime dynamic action |
| Ticket triage | `none` | 1/3, 33.3% | 12,684.7ms | static selectors |
| Ticket triage | `page_analysis_only` | 1/3, 33.3% | 12,700.3ms | static selectors |
| Ticket triage | `knowledge_only` | 3/3, 100% | 3,914.7ms | runtime dynamic action |
| Ticket triage | `page_analysis_plus_knowledge` | 3/3, 100% | 3,860.7ms | runtime dynamic action |

`none` 대비 `knowledge_only` 개선:

| Task | 성공률 변화 | 평균 wall time 변화 |
|---|---:|---:|
| Dynamic ad review | +66.7 percentage points | 13,161.3ms -> 3,368.0ms, 74.4% 감소 |
| Checkout wizard | +66.7 percentage points | 12,980.7ms -> 3,349.7ms, 74.2% 감소 |
| Ticket triage | +66.7 percentage points | 12,684.7ms -> 3,914.7ms, 69.1% 감소 |

## 해석

### 1. 노하우는 효과가 컸다

`knowledge_only`만 켜도 세 태스크 모두 static selector workflow 대신 runtime dynamic action workflow가 생성됐다. 실행 성공률은 33.3%에서 100%로 올라갔고, 평균 wall time은 실패 timeout을 피하면서 약 69.1-74.4% 줄었다.

이 결과는 `workflow_knowledge_entries`에 저장되는 script-generation knowledge가 실제 synthesis decision에 영향을 줄 수 있음을 보여준다. 특히 "variant-safe runtime dynamic action", "one DOM variant selector가 sibling variant에서 깨진다" 같은 reusable tip이 중요했다.

### 2. Page analysis만으로는 이번 태스크에서 효과가 없었다

`page_analysis_only`는 `none`과 성공률이 같았다. 이유는 현재 page analysis가 current page text에서 stable marker/page type 정도를 만들지만, multi-variant DOM에서 어떤 selector가 깨지고 dynamic action이 필요한지까지는 충분히 담지 못했기 때문이다.

Prompt 길이는 page analysis가 들어가면서 약 3.0k chars에서 약 4.0k chars로 늘었다. 하지만 이번 prompt-aware synthesis에서는 actionable prior knowledge가 없으면 static variant-A selector workflow로 남았다.

### 3. Page analysis + knowledge는 knowledge_only와 거의 같았다

`page_analysis_plus_knowledge`는 모두 100% 성공했다. 다만 `knowledge_only`와 큰 차이는 없었다. 이번 태스크에서는 결정적인 정보가 page analysis보다 knowledge entry에 있었기 때문이다.

### 4. 현재 core에는 page analysis 재사용 한계가 있다

추가 overwrite check에서 중요한 문제가 보였다. Verified prior page analysis를 먼저 넣어도, creation path와 같은 `PageAnalysisStore.upsert_from_trace()`를 호출하면 같은 URL key record가 current trace 기반 generic analysis로 갱신되며 verified hints가 사라졌다.

측정 결과:

| Task | before `page_type` | after `page_type` | dynamic hints before -> after |
|---|---|---|---:|
| Dynamic ad review | `verified_prior_run` | `generic_page` | 1 -> 0 |
| Checkout wizard | `verified_prior_run` | `generic_page` | 1 -> 0 |
| Ticket triage | `verified_prior_run` | `generic_page` | 1 -> 0 |

즉 "page analysis를 미리 해놨을 때"의 효과가 현재 core path에서는 기대만큼 나오기 어렵다. `workflow_knowledge_entries`는 recent lookup으로 prompt에 들어가지만, verified page analysis는 creation 시점의 fresh trace upsert에 의해 약화될 수 있다.

## 결론

이번 ablation에서 노하우 memory는 분명히 효과가 있었다.

- No memory: 33.3% success, 평균 12.94초
- Page analysis only: 33.3% success, 평균 12.82초
- Knowledge only: 100% success, 평균 3.54초
- Page analysis + knowledge: 100% success, 평균 3.52초

반대로 page analysis만의 효과는 이번 core 구현에서는 거의 없었다. 이건 page analysis 개념이 무의미하다는 뜻이 아니라, 현재 reuse path가 verified page analysis를 잘 보존/조회하지 못한다는 신호다.

## 권장 수정

1. `WorkflowCreationRuntime._enrich_trace_with_page_memory()`에서 단순 `upsert_from_trace()`만 하지 말고, 기존 verified page analysis를 먼저 lookup해 merge해야 한다.
2. `enrich_page_analysis_with_workflow_evidence()`로 만들어진 `wait_markers`, `verified_selectors`, `dynamic_action_hints`, `risk_notes`는 fresh trace 분석보다 우선 보존해야 한다.
3. Page analysis와 script-generation knowledge를 별도 ablation flag로 끌 수 있게 해야 한다. 예: `WEBMCP_DISABLE_PAGE_ANALYSIS_CONTEXT=1`, `WEBMCP_DISABLE_WORKFLOW_KNOWLEDGE=1`.
4. 실제 Codex synthesizer profile에서도 같은 실험을 반복해야 한다. 이번 harness는 model variability를 제거하려고 prompt-aware local synthesizer를 썼다.

## 재현 명령

```bash
cd /Users/mingukjang/git/spica_at_home/webmcp
core/reference/webwright/.venv/bin/python core/outputs/ablation_memory_20260610/run_memory_ablation.py
```
