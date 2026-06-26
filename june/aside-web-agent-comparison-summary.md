# Aside, Webwright, browser-use 비교 요약

조사일: 2026-06-26  
주제: Aside 동작 원리 단서와 Webwright/browser-use 대비 핵심 비교

## 핵심 결론

Aside는 오픈소스 browser agent framework가 아니다. 공개된 것은 Aside 본체 코드가 아니라 `at-inc/aside-benchmarks`의 benchmark 결과와 일부 evaluation runner다. 따라서 browser-use처럼 import해서 쓰거나 Webwright처럼 fork해서 내부 loop를 고칠 수는 없다.

하지만 공개 trajectory를 보면 Aside는 vision-only click agent가 아니라 **code-as-action browser agent**에 가깝다. LLM이 `repl`에서 JavaScript/Playwright-like code를 실행하고, `snapshot(page)`으로 DOM/accessibility tree를 읽고, `read_file`, `write_todos`, `websearch` 같은 도구를 조합한다. 이 점은 browser-use보다 Webwright와 더 닮아 있다.

## 세 줄 판단

- **Aside**: 제품형 AI browser. 성능과 UX는 흥미롭지만 core 비공개.
- **Webwright**: Aside식 동작 원리를 따라 만들 때 가장 좋은 공개 reference.
- **browser-use**: 지금 바로 자동화를 붙일 때 가장 실용적인 오픈소스 라이브러리/플랫폼.

## Aside에서 확인된 공개 단서

- CLI/MCP/REPL 제공: `aside`, `aside exec`, `aside mcp`, `aside repl`
- benchmark runner는 `aside exec --model ... --thinking ... --log-dump events.jsonl "<task>"` 형태로 실행
- 내부 log는 `toolCall`/`toolResult` message 구조
- 주요 action은 `repl("title", "code")`
- code 안에서 `openTab`, `snapshot`, `page.locator`, `page.evaluate`, `fetch` 사용
- snapshot은 `button "Search" [ref=e13]` 같은 text-first DOM/AX tree
- 큰 출력은 temp file에 저장하고 `read_file(offset, limit)`로 다시 읽음
- 일부 error path에 `browser-v3/cdp/client.ts`가 보여 CDP 기반 browser daemon 가능성이 큼
- memory, password manager, permission mode, task pause/resume은 제품 계층에서 제공

## benchmark 수치

Aside benchmark repo 기준:

| Benchmark | 결과 |
|---|---:|
| Online-Mind2Web | 297/300 pass, 99.0% |
| BU Bench V1 | 93/100 pass, 93.0% |
| Odysseys | 151/200 perfect, 75.5%; rubric pass 88.8% |

Webwright README 기준:

| Benchmark | 결과 |
|---|---:|
| Online-Mind2Web | GPT-5.4로 86.7% |
| Odysseys | GPT-5.4로 60.1% |

주의: 모델, 실행 조건, website 상태, grader가 달라 직접 수치만으로 공정 비교하기는 어렵다.

## 비교 요약

| 기준 | Aside | Webwright | browser-use |
|---|---|---|---|
| 공개성 | 본체 비공개, benchmark 공개 | 오픈소스 | 오픈소스 |
| 정체성 | AI browser 제품 | browser agent framework | browser automation agent SDK/platform |
| 핵심 방식 | JS REPL + snapshot + product browser | Python/Playwright code-as-action | Python agent loop + custom tools |
| 상태 관리 | browser profile, memory, task files | workspace files, screenshots, logs | browser session/profile, history |
| 인증 처리 | password manager autofill boundary | 별도 구현 필요 | profile/cloud browser 기반 |
| 제품성 | 높음 | 낮음 | 중간, cloud 제품 있음 |
| 구현 참고 가치 | UX/안전/제품 계층 | agent loop/architecture | SDK/운영/생태계 |

## 가장 중요한 설계 교훈

1. 좌표 클릭보다 `DOM/AX snapshot + code execution`이 장기 작업에 강하다.
2. agent에게 `repl` 또는 script 실행권을 주면 shadow DOM, API 호출, scraping, batch action에 강해진다.
3. snapshot이 길어지므로 temp file과 paginated read가 필요하다.
4. 긴 task에서는 `todo`와 tab state를 명시적으로 관리해야 한다.
5. 실제 제품에서는 password raw value를 agent에게 주면 안 되고, autofill boundary가 필요하다.
6. permission mode와 approval checkpoint 없이는 로그인된 실제 브라우저에서 쓰기 어렵다.

## 추천 방향

자체 구현을 한다면:

1. Webwright식 code-as-action loop를 기본 골격으로 삼는다.
2. browser-use의 Python SDK, custom tools, cloud browser 운영 방식을 참고한다.
3. Aside의 memory, password manager, permission mode, task transcript UX를 제품 계층으로 설계한다.
4. Online-Mind2Web/BU Bench/Odysseys 중 작은 subset으로 regression benchmark를 만든다.

## 출처

- Aside benchmark repo: https://github.com/at-inc/aside-benchmarks
- Aside Odysseys runner: https://github.com/at-inc/aside-benchmarks/tree/main/odysseys/runner
- Aside developer docs: https://docs.aside.com/help/developers
- Aside task/security/memory/password docs: https://docs.aside.com/help/tasks
- Webwright repo: https://github.com/microsoft/Webwright
- browser-use repo: https://github.com/browser-use/browser-use

