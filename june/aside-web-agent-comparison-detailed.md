# Aside, Webwright, browser-use 비교 상세 보고서

조사일: 2026-06-26  
주제: Aside 동작 원리 단서와 Webwright, browser-use 대비 분석  
범위: 공개 웹 문서, GitHub 공개 저장소, Aside benchmark artifact 기준

## 1. 결론 요약

Aside는 browser-use처럼 가져다 쓰는 오픈소스 라이브러리가 아니라, AI agent가 내장된 독립 브라우저 제품이다. 현재 공개된 것은 Aside 본체 코드가 아니라 `at-inc/aside-benchmarks` 저장소의 benchmark 결과, 일부 평가 runner, trajectory, screenshots다. 따라서 Aside의 내부 planner, browser daemon, memory, credential 처리 코드는 직접 검증할 수 없다.

그럼에도 공개 artifact에서 보이는 동작 방식은 꽤 선명하다. Aside는 단순한 vision-only click agent라기보다, 브라우저에 연결된 CLI/daemon 위에서 LLM이 `repl`, `openTab`, `snapshot`, `page.locator`, `page.evaluate`, `fetch`, `read_file`, `write_todos` 같은 도구를 사용하는 code-as-action 계열 agent로 보인다. 이 점은 browser-use보다 Webwright와 더 가까운 방향이다. 다만 Webwright가 "coding model + terminal + disposable browser"라는 연구/프레임워크 형태라면, Aside는 여기에 일반 사용자용 브라우저, 로그인 세션, memory, password autofill, permission mode, task UI를 붙인 제품형 구현에 가깝다.

핵심 해석은 다음과 같다.

- Aside의 공개 benchmark 성능은 높지만, agent core가 공개되지 않았기 때문에 오픈소스 재현성은 낮다.
- 구현 철학은 "DOM/AX snapshot + code execution + browser daemon + task transcript" 조합으로 추정된다.
- Webwright는 Aside를 따라 만들 때 가장 유용한 공개 reference다. 특히 code-as-action, workspace-as-state, run artifact 우선 설계가 유사하다.
- browser-use는 즉시 사용 가능한 Python agent/library 생태계로 강점이 크지만, Aside/Webwright식 "자유로운 코드 실행 agent"보다는 패키지화된 agent loop와 브라우저 세션 중심성이 더 강하다.
- 자체 browser agent를 만든다면 Webwright의 agent loop를 기본 골격으로 삼고, browser-use의 tool/custom integration과 cloud browser 운영 노하우, Aside의 product UX/memory/credential boundary를 조합하는 방향이 실용적이다.

## 2. 조사 대상 개요

| 항목 | Aside | Webwright | browser-use |
|---|---|---|---|
| 성격 | AI browser 제품 | 오픈소스 browser-agent framework | 오픈소스 browser automation agent/library |
| 공개 코드 | 본체 비공개로 보임. benchmark repo만 공개 | 공개 | 공개 |
| 라이선스 | `aside-benchmarks`는 MIT. 제품 본체는 별도 | MIT | MIT |
| 주요 언어/런타임 | 제품 본체 미공개. 공개 runner는 TypeScript | Python + Playwright | Python, Rust core beta, browser automation runtime |
| 주요 인터페이스 | 앱, CLI, MCP, REPL | CLI/terminal agent loop | Python API, CLI, cloud agent |
| 강점 | 제품 UX, memory, password manager, permission, 높은 공개 benchmark 수치 | 작고 투명한 code-as-action 구조, 재현성, 연구/개발 친화성 | 생태계, 사용성, custom tools, production/cloud 옵션 |
| 약점 | core 비공개, benchmark 재현성 제한 | 제품 UX/credential/memory는 별도 구현 필요 | 내부 agent loop 추상화가 더 크고, code-as-action 자유도는 Webwright 대비 낮음 |

GitHub API 확인 기준 공개 저장소 상태:

| 저장소 | 설명 | 라이선스 | Stars | 최근 push |
|---|---|---:|---:|---|
| `at-inc/aside-benchmarks` | Aside browser agent benchmark results | MIT | 24 | 2026-06-23 |
| `microsoft/Webwright` | SWE-style browser agent framework | MIT | 5,665 | 2026-06-03 |
| `browser-use/browser-use` | AI agents용 browser automation | MIT | 100,735 | 2026-06-26 |

숫자는 2026-06-26 조회 기준이라 이후 변할 수 있다.

## 3. Aside는 정확히 무엇인가

Aside는 AI agent가 내장된 브라우저 제품이다. 공식 문서 기준으로 사용자는 브라우저 작업을 task로 실행할 수 있고, task는 여러 단계의 browsing, web search, file step, credential autofill, approval request를 수행할 수 있다. CLI, MCP, REPL도 제공된다. 개발자 문서에는 다음과 같은 실행 방식이 나온다.

```bash
aside "Open localhost:3000 and run a smoke test"
aside exec --account u1 -m openai-codex/gpt-5.5 "Plan this workflow"
aside mcp
aside repl "const p = await openTab('https://example.com')"
```

이 구조는 Aside가 단순한 앱 UI만 제공하는 것이 아니라, 외부 coding agent나 benchmark runner가 호출할 수 있는 automation surface를 갖고 있음을 의미한다.

Aside 제품의 주요 차별점은 다음이다.

- 일반 브라우저 프로필을 기반으로 task를 실행한다.
- incognito/default mode, read-only/guard/full-access permission mode를 제공한다.
- memory가 browsing history, chats, task activity를 context로 재사용할 수 있다.
- password manager는 agent에게 raw password를 넘기지 않고 autofill payload를 통해 로그인하게 한다.
- task 중 approval, follow-up, pause/resume, generated file preview를 지원한다.
- MCP 서버와 REPL을 통해 다른 agent/coding tool과 연결될 수 있다.

즉 Aside는 "browser agent framework"라기보다 "agent-native browser product"에 가깝다.

## 4. Aside 공개 benchmark 결과

`at-inc/aside-benchmarks`는 Aside browser agent를 세 개의 open-web browser-agent benchmark에서 평가한 결과를 공개한다.

- Online-Mind2Web
- Odysseys
- BU Bench V1

공개 README 기준 주요 수치는 다음과 같다.

| Benchmark | Aside 공개 결과 |
|---|---:|
| Online-Mind2Web | 300 tasks 중 297 pass, 2 fail, 1 impossible. Pass rate 99.0%, impossible 제외 99.3% |
| Odysseys | 200 tasks 중 perfect tasks 151, perfect-task rate 75.5%, rubric pass 88.8% |
| BU Bench V1 | `gpt-5.5` run: 100 tasks 중 93 pass, 6 fail, 1 impossible. Pass rate 93.0%, impossible 제외 93.9% |

중요한 caveat가 있다.

- benchmark는 live website에서 실행되므로 시간이 지나면 결과가 달라질 수 있다.
- 공개된 것은 결과와 일부 runner이지 Aside agent core가 아니다.
- Online-Mind2Web와 BU Bench V1 결과는 Aside 제품/runner와 특정 모델 조합의 결과로 봐야 한다.
- 다른 논문/벤치마크처럼 독립 재현 가능한 open harness인지 여부는 제한적이다.

그래도 trajectory와 runner는 동작 방식에 대한 힌트를 제공한다.

## 5. 공개 artifact에서 드러난 Aside 동작 원리

### 5.1 CLI가 agent entrypoint로 사용된다

Odysseys runner는 Aside를 library import하지 않는다. 대신 `aside` CLI를 shell out한다. runner README는 "Aside CLI가 PATH에 있어야 하며 daemon package에 의존하지 않는다"고 설명한다.

runner의 핵심 실행 방식은 다음 구조다.

```ts
const prompt = `Go to ${task.website}, ${task.confirmed_task}`;
const args = [
  ...config.asideArgs,
  'exec',
  '--model',
  `${config.provider}/${config.modelId}`,
  '--thinking',
  config.thinkingLevel,
  '--log-dump',
  join(taskDir, 'events.jsonl'),
  prompt,
];
```

의미:

- `aside exec`가 task 단위 agent run을 시작한다.
- model provider/model id/thinking level을 외부에서 지정한다.
- `--log-dump events.jsonl`로 내부 message/tool event를 덤프할 수 있다.
- benchmark runner는 Aside core를 직접 호출하지 않고 CLI protocol을 사용한다.

### 5.2 내부 message log는 toolCall/toolResult 구조다

`trajectory.ts`는 `events.jsonl`을 읽고 `message_end` event에서 assistant message와 tool result를 추출한다. 구조는 `role: assistant`, `role: toolResult`, `content` part, `toolCallId`를 중심으로 되어 있다. 이는 OpenAI-style/agent-framework-style message stream에 가깝다.

trajectory generator는 assistant content 중 `toolCall` part를 찾고, 해당 `toolCallId`의 tool result를 붙여 action history를 만든다. 이때 image result도 별도 screenshot 파일로 저장할 수 있다.

이것이 의미하는 바:

- Aside agent loop는 내부적으로 LLM message와 tool call을 명확히 기록한다.
- browser action은 model output text가 아니라 typed tool call로 실행된다.
- 평가와 디버깅을 위해 action, response, screenshot을 재구성할 수 있다.

### 5.3 `repl`이 핵심 action surface다

공개 trajectory에서 가장 중요한 도구는 `repl`이다. 예시:

```text
tool: repl("Open GitHub search", "
await openTab('https://github.com/numpy/numpy/issues?...');
const s = await snapshot(page);
console.log(s.tree);
")
```

다른 예시에서는 다음과 같은 패턴이 나온다.

```js
await openTab('https://streeteasy.com/for-sale/brooklyn');
const s1 = await snapshot(page);
console.log(s1.tree.substring(0, 5000));
```

```js
const info = await page.evaluate(() => {
  function walk(node) {
    const out = [];
    if (node.shadowRoot) {
      out.push({ tag: node.tagName, hasShadow: true, html: node.shadowRoot.innerHTML.substring(0, 3000) });
    }
    for (const child of (node.children || [])) out.push(...walk(child));
    return out;
  }
  return walk(document.body);
});
console.log(JSON.stringify(info, null, 2));
```

이것은 Aside가 `click next coordinate` 방식이 아니라, agent가 JavaScript/Playwright-like code를 작성하고 실행하는 방식임을 강하게 시사한다. 특히 shadow DOM처럼 일반 accessibility tree로 접근하기 어려운 페이지에서는 `page.evaluate`를 직접 사용한다.

### 5.4 관찰은 DOM/AX snapshot 중심이다

trajectory의 snapshot 출력은 다음과 같은 tree 형식이다.

```text
- title: "Google" [url=https://www.google.com/]
- search:
  - combobox "Search" [ref=e8] [focused]
  - button "Google Search" [ref=e13]
```

또 다른 예시:

```text
- textbox "Where to?. Results available." [ref=e10]
- button "Dates" [ref=e11]
- button "Guests, 2 guests" [ref=e12]
- button "Search" [ref=e13]
```

특징:

- DOM/accessibility tree를 text-first representation으로 변환한다.
- clickable/focusable 요소에 `ref=e...` 같은 stable-ish reference를 부여한다.
- `snapshot(page, { interactive: true })`로 interactive 요소 중심 관찰을 할 수 있다.
- 일부 trajectory에서 `snapshot.diff`를 사용한다.

이 구조는 token 효율과 조작 안정성을 동시에 노린다. screenshot-only agent와 달리 버튼 이름, role, 현재 URL, element reference를 model이 직접 읽을 수 있다.

### 5.5 CDP 기반 browser daemon 흔적이 있다

한 trajectory의 error에는 다음 경로가 나온다.

```text
/Users/awm/Develop/bro-components/apps/daemon/src/browser-v3/cdp/client.ts
CDP websocket disconnected
```

이것은 Aside 내부 browser controller가 Chrome DevTools Protocol 또는 그에 준하는 CDP websocket client를 사용한다는 강한 단서다. 공개 코드가 아니므로 확정은 아니지만, `page.locator`, `page.evaluate`, `openTab`, `snapshot` API와 잘 맞는다.

### 5.6 큰 출력은 temp file로 넘기고 `read_file`로 페이지네이션한다

긴 snapshot은 다음처럼 저장된다.

```text
[Output too large (192.4KB). Full output saved to:
/Users/awm/.aside/u/0/agents/main/sessions/.../tmp/repl-result-....txt]
```

그 다음 agent는 다음 도구를 사용한다.

```text
Action: read_file("path":"tmp/repl-result-....txt","offset":1,"limit":200)
```

이것은 장기 작업에서 매우 중요한 설계다. browser snapshot은 쉽게 수십만 byte가 되므로, agent context에 전부 넣는 대신 파일 artifact로 저장하고 필요한 구간만 읽는다. Webwright의 "workspace-as-state"와 유사한 패턴이다.

### 5.7 task planning과 상태 관리가 도구화되어 있다

Odysseys trajectory에는 `write_todos`가 등장한다.

```text
write_todos(... "Open Google...", "Find one CheapCharts...", "View Epic homepage..." ...)
```

이는 긴 web task를 여러 subtask로 나누고 상태를 명시적으로 추적하는 구조다. 단순 react loop보다 긴 horizon에서 안정적이다.

### 5.8 web search, YouTube search 등 browser 외부 도구도 쓴다

BU Bench trajectory에는 `websearch`, `youtube.search` 같은 tool call이 등장한다. 즉 Aside는 "브라우저만 조작하는 agent"가 아니라, search API, site-specific helper, file tool, browser REPL을 함께 쓰는 multi-tool agent다.

이것은 benchmark 성능에 중요하다. 실제 web task는 페이지 조작만으로 끝나지 않고, 검색, 검증, tab 관리, API 호출, 파일 읽기, 중간 산출물 저장이 필요하다.

## 6. Aside와 Webwright 비교

Webwright는 Microsoft가 공개한 browser-agent framework다. README는 Webwright를 "coding models를 state-of-the-art browser agents로 바꾸는" 접근으로 설명한다. 핵심은 agent에게 terminal/workspace를 주고, Playwright script를 직접 작성/실행/수정하게 하는 것이다.

Webwright의 공개 설명에서 중요한 문장들은 다음 방향을 가리킨다.

- browser는 agent가 spawn하는 환경일 뿐이고, state는 local workspace에 둔다.
- action은 free-form Python, 즉 agent가 Playwright script를 직접 작성한다.
- loop는 write code -> execute -> inspect screenshots -> repair다.
- run artifact, screenshots, trajectories를 disk에 남긴다.
- core loop가 작고 디버그하기 쉽다.

### 6.1 구조적 유사점

| 항목 | Aside | Webwright |
|---|---|---|
| 핵심 action | `repl`에서 JS/Playwright-like code 실행 | terminal에서 Python/Playwright script 작성/실행 |
| 관찰 | `snapshot(page)`, screenshot, logs | screenshot, DOM/Playwright observation, run artifacts |
| 상태 | task session, tabs, temp files, memory, browser profile | local workspace, scripts, screenshots, logs |
| 긴 작업 처리 | todo, temp file, read_file, multi-tab, resume/follow-up | script iteration, file artifacts, browser 재생성 가능 |
| 제품성 | 브라우저 앱 + permission + password + memory | 연구/프레임워크 중심 |
| 공개성 | 본체 비공개 | 전체 공개 |

Aside는 Webwright의 아이디어를 제품화한 형태와 닮았다. 다만 코드 언어가 다르다. Aside의 공개 trajectory는 JS/TypeScript/Playwright-like REPL이고, Webwright는 Python/Playwright 중심이다.

### 6.2 차이점

Webwright는 "브라우저는 disposable하고, workspace가 state"라는 관점을 강하게 밀어붙인다. agent가 필요하면 새 browser session을 띄우고, 실패하면 script와 screenshot을 고쳐 다시 실행한다. 이 방식은 개발자와 benchmark에는 좋지만 일반 사용자의 로그인 세션, password vault, browser history, approval flow를 자연스럽게 다루려면 추가 제품 계층이 필요하다.

Aside는 반대로 실제 사용자의 브라우저 프로필과 task UI를 중심에 둔다. password manager, memory, permission mode, follow-up queue/steer 같은 기능은 Webwright에는 없는 product layer다. 그래서 Aside는 end-user browser automation에는 강하지만, 연구자가 내부 loop를 수정하거나 재현하기는 어렵다.

### 6.3 benchmark 비교

Webwright README 기준:

- Online-Mind2Web: GPT-5.4로 86.7%
- Odysseys: GPT-5.4로 60.1%
- code-as-action이 screenshot+xy-coordinate baseline보다 강하다고 보고

Aside benchmark repo 기준:

- Online-Mind2Web: 99.0%
- Odysseys: perfect-task 75.5%, rubric pass 88.8%
- BU Bench V1: 93.0%

표면 수치만 보면 Aside가 높다. 그러나 비교할 때 주의해야 한다.

- 사용 모델, run budget, task execution 환경, grader가 다를 수 있다.
- Aside는 제품 본체가 비공개라 독립 재현성이 낮다.
- Webwright는 공개 harness라는 점이 더 중요하다.

따라서 "기술을 배우기 위한 reference"는 Webwright가 낫고, "제품 방향의 목표 상태"는 Aside가 더 선명하다.

## 7. Aside와 browser-use 비교

browser-use는 Python 생태계에서 가장 널리 알려진 open-source browser agent/library 중 하나다. README 기준으로 open-source agent, cloud agent, CLI, custom tools, cloud browsers, profile sync, CAPTCHA/stealth/proxy 운영 옵션을 제공한다.

browser-use의 기본 포지션은 다음이다.

- Python API로 `Agent(task=..., llm=..., browser_profile=...)`를 실행한다.
- custom tools나 deep code-level integration이 필요한 경우 open-source agent를 쓴다.
- 복잡한 task와 scale, stealth, proxy, CAPTCHA 쪽은 hosted cloud agent/browser를 권장한다.
- BU Bench V1 benchmark를 공개한다.

### 7.1 구조적 차이

| 항목 | Aside | browser-use |
|---|---|---|
| 사용 방식 | 브라우저 제품, CLI, MCP, REPL | Python package, CLI, cloud |
| open-source | 본체 비공개로 보임 | 공개 |
| action 방식 | 공개 trajectory상 `repl` code-as-action 비중 큼 | autonomous agent loop over DOM/AX snapshots, indexed click/type actions 중심으로 설명됨 |
| code 실행 자유도 | REPL에서 직접 JS/Playwright-like code 작성 | custom tools와 Python integration 가능. 기본 loop는 package abstraction |
| auth | 제품 password manager/autofill boundary | browser profile, cloud browser/profile sync 등 |
| memory | 제품 memory 설정 제공 | cloud agent 쪽 persistent filesystem/memory 언급 |
| 제품성 | end-user AI browser | library/cloud automation platform |
| 재현성 | benchmark artifact만 공개 | 라이브러리 자체 공개 |

browser-use는 오늘 바로 browser automation을 코드에 붙이기 좋다. 반면 Aside는 사용자가 브라우저에서 실제 로그인 상태, history, password, memory를 기반으로 task를 맡기는 제품으로 설계되어 있다.

### 7.2 기술적으로 배울 지점

browser-use에서 배울 점:

- Python SDK 형태의 낮은 진입 장벽
- custom tools와 domain-specific integration
- cloud browser, stealth, proxy, CAPTCHA 같은 production 운영 고려
- 많은 사용자와 사례에서 오는 실전 안정성

Aside에서 배울 점:

- 일반 브라우저 UX에 agent를 붙이는 방식
- credential boundary: raw password를 agent에게 주지 않고 autofill만 허용
- permission mode와 approval flow
- long-horizon task UX: pause, resume, follow-up, file artifacts
- code-as-action REPL과 text-first snapshot을 제품에 녹이는 방식

## 8. 세 시스템의 핵심 차이

| 기준 | Aside | Webwright | browser-use |
|---|---|---|---|
| 가장 가까운 정체성 | AI browser product | browser-agent research framework | browser automation agent SDK/platform |
| 가장 중요한 설계 선택 | 제품 브라우저 안에서 agent를 안전하게 실행 | coding model에게 terminal/workspace를 줌 | Python API로 browser agent를 쉽게 사용 |
| observation | DOM/AX snapshot, screenshots, logs | screenshots/logs/artifacts 중심 | DOM/AX snapshots 중심 |
| action | JS REPL, tool calls, browser daemon | Python/Playwright script | package agent loop, click/type/tool actions, custom tools |
| state | browser profile + session + memory + task files | workspace files + scripts + screenshots | browser session/profile + agent history |
| credentials | password manager autofill boundary | 별도 구현 필요 | profile/cloud browser 기반 |
| debug/replay | benchmark artifact 일부만 공개 | run artifacts 우선 | history/log는 있으나 framework abstraction 내부 |
| 벤치마크 성능 | 높음. 단, 본체 비공개 | 공개 harness 기준 강함 | 강력한 생태계와 benchmark 공개 |
| 개발자가 fork하기 | 어려움 | 쉬움 | 쉬움 |
| end-user product로 쓰기 | 강함 | 약함 | cloud/product 옵션 있음 |

## 9. Aside 동작 원리에 대한 재구성

공개 근거만으로 재구성하면 Aside agent loop는 다음과 비슷할 가능성이 크다.

```text
User task
  -> Aside app / CLI / MCP
  -> task session 생성
  -> selected model + thinking level 설정
  -> agent loop
       - todo/task state 관리
       - browser snapshot 수집
       - repl/websearch/read_file/write_todos/password autofill 등 tool call 선택
       - browser daemon이 CDP/Playwright-like API로 action 실행
       - 결과, screenshot, large output을 artifact로 저장
       - 필요한 경우 승인/사용자 입력 대기
  -> final answer
  -> memory candidate 추출/저장
```

이 구조에서 성능에 기여했을 것으로 보이는 요소:

1. Text-first DOM/AX snapshot  
   시각 모델만 쓰는 방식보다 버튼/링크/폼의 의미를 안정적으로 읽는다.

2. Code-as-action REPL  
   반복 클릭을 여러 turn으로 예측하지 않고, 작은 script로 한 번에 처리한다. shadow DOM, API call, DOM scraping에도 강하다.

3. Long-context 회피용 artifact 저장  
   큰 snapshot을 temp file로 저장하고 필요한 offset만 읽는다.

4. Explicit todo/task decomposition  
   benchmark의 긴 task에서 빠뜨리는 요구사항을 줄인다.

5. Multi-tool composition  
   browser, web search, file, site-specific helper를 함께 쓴다.

6. Product-level browser state  
   로그인 세션, history, password manager, memory를 agent가 안전하게 활용한다.

7. Permission/approval boundary  
   실제 사용자 환경에서 agent를 돌리는 데 필요한 안전 장치가 agent loop 밖 제품 계층에 있다.

## 10. 자체 구현 관점의 시사점

Webwright/browser-use/Aside를 비교하면 자체 browser agent 설계의 우선순위가 분명해진다.

### 10.1 최소 MVP

MVP는 Webwright식으로 시작하는 것이 좋다.

- Playwright 기반 browser runner
- text-first accessibility/DOM snapshot
- free-form code execution tool
- screenshots and logs as artifacts
- one run directory per task
- final answer와 action history 저장

이 단계에서는 browser-use를 그대로 쓰거나, Webwright를 fork해 code-as-action loop를 검증할 수 있다.

### 10.2 성능을 올리는 추가 요소

- `snapshot(diff=true)` 또는 previous snapshot 대비 diff 제공
- element ref 기반 click/fill helper
- large output temp file + paginated read
- todo tool
- tab registry와 active page state
- site-specific helper, 예: YouTube search, GitHub issue search
- deterministic evaluator와 regression benchmark

### 10.3 제품화를 위해 필요한 요소

Aside의 강점은 agent core보다 제품 계층에 있다.

- permission mode: read-only, guard, full-access
- file root allowlist
- network/browser rule
- password autofill boundary
- approval checkpoint: payment, posting, messaging, destructive action
- memory review/edit/delete
- incognito/default profile 분리
- task transcript와 generated files UI

이 계층 없이는 실제 사용자의 로그인된 브라우저에서 agent를 안정적으로 돌리기 어렵다.

## 11. 추천 판단

목표가 "browser-use 같은 오픈소스 agent를 바로 써서 자동화하기"라면 browser-use가 가장 빠르다. custom tools나 Python integration이 필요할 때 좋고, cloud browser 운영 옵션도 있다.

목표가 "Aside가 높은 점수를 낸 원리를 연구하고 비슷한 agent loop를 직접 구현하기"라면 Webwright가 가장 좋은 출발점이다. 공개 코드가 작고, code-as-action의 장점이 명확하며, benchmark와 artifact 설계가 투명하다.

목표가 "일반 사용자가 매일 쓰는 브라우저 안에서 agent에게 일을 맡기는 제품"이라면 Aside가 가장 참고할 만하다. 단, 내부 코드는 공개되지 않았기 때문에 benchmark artifact와 문서에서 UX/architecture pattern을 추출해야 한다.

실무적 조합은 다음이 좋다.

1. Webwright식 code-as-action loop를 기본 골격으로 삼는다.
2. browser-use식 Python SDK/custom tools/cloud browser 운영을 참고한다.
3. Aside식 memory, password boundary, permission, task UX를 제품 계층으로 붙인다.
4. Online-Mind2Web, BU Bench, Odysseys 중 작은 subset부터 자체 regression suite로 만든다.

## 12. 남은 불확실성

- Aside agent planner와 prompt는 공개되어 있지 않다.
- Aside browser daemon의 정확한 구현은 공개되어 있지 않다. CDP 사용은 error path와 API 흔적에 기반한 추정이다.
- benchmark 결과는 live website 상태, 계정 상태, model version, grader 구성에 민감하다.
- `gpt-5.5`, `gpt-5.4`, `Claude Opus 4.8` 등 model naming은 각 repo/공식 문서에 기재된 그대로 인용한 것이며, 외부 독립 검증은 별도 필요하다.
- Aside의 benchmark repo는 MIT지만, 이것이 Aside 제품 코드의 라이선스를 의미하지 않는다.

## 13. 출처

- Aside benchmark repo: https://github.com/at-inc/aside-benchmarks
- Aside Odysseys runner: https://github.com/at-inc/aside-benchmarks/tree/main/odysseys/runner
- Aside developer docs: https://docs.aside.com/help/developers
- Aside task docs: https://docs.aside.com/help/tasks
- Aside permissions docs: https://docs.aside.com/help/security
- Aside memory docs: https://docs.aside.com/help/memory
- Aside password manager docs: https://docs.aside.com/help/password-manager
- Webwright repo: https://github.com/microsoft/Webwright
- browser-use repo: https://github.com/browser-use/browser-use
- browser-use benchmark: https://github.com/browser-use/benchmark

