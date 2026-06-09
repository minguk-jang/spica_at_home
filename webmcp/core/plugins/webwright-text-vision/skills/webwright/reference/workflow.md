# Text-Default Workflow

이 Webwright variant는 code-as-action 흐름을 유지하되 evidence model을 바꿉니다.
활성 Codex agent는 이미지를 기본적으로 읽지 못한다고 가정하고, Playwright로
페이지 상태를 text와 structured data로 노출해야 합니다. Screenshot은 감사와
vision fallback용 artifact입니다.

## DOM 우선 증거

vision보다 먼저 다음 증거를 사용합니다.

- `locator.inner_text()`로 visible label과 result card를 확인합니다.
- `locator.get_attribute()`로 selected value, ARIA state, href, form attribute를
  확인합니다.
- `locator.is_visible()`, `is_checked()`, `count()`로 UI 상태를 확인합니다.
- `page.url`, title, response JSON, local storage, session state를 확인합니다.
- 접근성 구조가 raw HTML보다 안정적이면 `aria_snapshot`을 사용합니다.

## Vision fallback

critical point가 본질적으로 시각적이거나 DOM이 잘못된 상태를 보여줄 때만 vision
fallback을 사용합니다. 기록은 짧고 정확해야 합니다.

```text
vision_fallback:
  screenshot: final_runs/run_001/screenshots/final_execution_3_results.png
  claim: 선택한 빨간색 swatch가 시각적으로 active 상태다.
  reason: active 상태가 canvas로 렌더링되어 DOM/ARIA에 노출되지 않는다.
```

## 완료 기준

모든 critical point는 다음 중 하나를 가져야 합니다.

- DOM, URL, ARIA, response, action log에서 나온 text evidence
- screenshot path와 정확한 visual claim이 포함된 vision fallback 판단

WebMCP에서 재사용 가능한 결과는 workflow라고 부릅니다. Codex agent skill과
혼동하지 않도록 workflow skill이라는 표현은 쓰지 않습니다.
