# WebMCP Harder Ablation Study - 2026-06-10

## 왜 다시 했는가

이전 ablation은 Naver stock/map fixture처럼 정적 텍스트와 known handler가 강한 예제를 포함했다. 그 결과 100% 성공률이 쉽게 나왔고, 실제 WebMCP의 중요한 차이인 "DOM이 바뀌는 브라우저 태스크에서 저장 selector가 얼마나 깨지는가"를 충분히 보지 못했다.

이번 rerun은 정적 fixture를 제외하고, 모두 로컬 브라우저에서 실제 DOM state를 바꾸는 태스크로 구성했다. 각 태스크는 3개 variant를 가진다. Variant A에서 녹화한 static selector workflow와, workflow DB에는 instruction/success criteria만 저장하고 runtime에서 browser action을 생성하는 dynamic workflow를 비교했다.

Raw artifacts:

- `core/outputs/ablation_harder_20260610/results.json`
- `core/outputs/ablation_harder_20260610/summary.md`
- `core/outputs/ablation_harder_20260610/run_harder_ablation.py`
- `core/outputs/ablation_harder_20260610/browser/**`

## 태스크

| 태스크 | 복잡도 | Variants | Static baseline 실패 포인트 |
|---|---|---|---|
| Dynamic ad review | 광고 dismiss 후 review form 작성, checkbox 승인, 완료 marker 확인 | `modal`, `banner`, `rail` | modal 전용 `[data-testid='sponsor-close']` |
| Checkout wizard | plan 선택, 이름/email/coupon 입력, 약관 승인, 주문 완료 | `classic`, `compact`, `enterprise` | classic 전용 `#plan-pro`, `#full-name`, `#coupon-code` |
| Ticket triage | async ticket load, open/high 필터, ETA sort, earliest ticket 선택, review | `table`, `cards`, `compact` | table 전용 `#filter-open`, `#ticket-ops-17` |

반복은 각 variant 2회다. 따라서 mode당 `n=6`, 전체 36 browser trials다.

## 결과

| 태스크 | Mode | 성공률 | 평균 wall time | 중앙 wall time |
|---|---|---:|---:|---:|
| Dynamic ad review | static variant-A selectors | 2/6, 33.3% | 12,783.7ms | 16,493.5ms |
| Dynamic ad review | runtime dynamic action | 6/6, 100% | 3,416.3ms | 3,421.5ms |
| Checkout wizard | static variant-A selectors | 2/6, 33.3% | 12,934.2ms | 16,487.0ms |
| Checkout wizard | runtime dynamic action | 6/6, 100% | 3,374.7ms | 3,391.0ms |
| Ticket triage | static variant-A selectors | 2/6, 33.3% | 12,771.2ms | 16,572.0ms |
| Ticket triage | runtime dynamic action | 6/6, 100% | 4,108.3ms | 3,952.0ms |

개선폭:

| 태스크 | 성공률 변화 | 평균 wall time 변화 |
|---|---:|---:|
| Dynamic ad review | +66.7 percentage points | 12,783.7ms -> 3,416.3ms, 73.3% 감소 |
| Checkout wizard | +66.7 percentage points | 12,934.2ms -> 3,374.7ms, 73.9% 감소 |
| Ticket triage | +66.7 percentage points | 12,771.2ms -> 4,108.3ms, 67.8% 감소 |

## Variant별 실패

Static baseline은 variant A에서만 성공했다.

- Dynamic ad: `modal` 성공, `banner`/`rail` 실패. 실패 원인은 `[data-testid='sponsor-close']` selector timeout.
- Checkout: `classic` 성공, `compact`/`enterprise` 실패. 실패 원인은 `#plan-pro` selector timeout.
- Ticket triage: `table` 성공, `cards`/`compact` 실패. 실패 원인은 `#filter-open` selector timeout.

Runtime dynamic action은 세 태스크의 모든 variant에서 성공했다.

## 해석

이번 실험은 이전 fixture 중심 결과보다 WebMCP core의 실질적인 ablation 차이를 더 잘 보여준다.

1. 저장 static selector는 빠를 수 있지만, 학습한 DOM variant를 벗어나면 실패율이 급격히 오른다.
2. 실패는 단순 assertion failure가 아니라 Playwright locator timeout으로 나타난다. 그래서 성공률만 낮아지는 것이 아니라 평균 runtime도 크게 나빠진다.
3. Runtime dynamic action은 workflow DB에 generated script를 저장하지 않고 instruction/success criteria만 저장한다. 이 구조는 variant가 바뀌는 광고, checkout UI, async triage UI에서 성공률을 크게 개선했다.
4. Dynamic path가 항상 더 빠른 것은 아니다. Variant A처럼 selector가 정확히 맞는 경우 static path는 5-6초, dynamic path는 3-4초였다. 이번 dynamic path가 더 빠른 주된 이유는 실패 timeout을 피했기 때문이다.
5. 이번 harness는 Codex model latency를 제외하고 core runtime 구조만 보기 위해 local deterministic dynamic planner를 사용했다. 실제 Codex planner를 쓰면 성공률은 task/prompt 품질에 영향을 받고 latency는 증가할 수 있다.

## 결론

"성공률 100% 유지"만 본 이전 stock/map fixture 실험은 쉬운 편이었다. 복잡한 multi-variant browser task에서는 static selector 재사용 성공률이 33.3%까지 떨어졌고, runtime dynamic action은 100%를 유지했다. 평균 실행 시간도 dynamic action 쪽이 67.8-73.9% 줄었다. 이는 WebMCP의 "불안정한 UI는 script를 저장하지 않고 runtime action으로 처리한다"는 설계가 실제로 효과가 있음을 보여준다.

다음 단계로 더 강한 검증을 하려면 local deterministic planner 대신 실제 Codex app-server dynamic planner 또는 app-server VLM evaluator를 켠 live profile을 따로 돌려야 한다. 이 경우 모델 latency와 prompt failure가 포함되므로 core-only benchmark와 분리해서 기록해야 한다.

## 재현 명령

```bash
cd /Users/mingukjang/git/spica_at_home/webmcp
core/reference/webwright/.venv/bin/python core/outputs/ablation_harder_20260610/run_harder_ablation.py
```
