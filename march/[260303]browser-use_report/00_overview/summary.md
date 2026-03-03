# 📖 이 시스템은 무엇인가요?

## 쉬운 설명

`browser-use`는 "웹 자동화 팀장" 같은 시스템입니다.  
사용자가 "이 사이트에서 정보 찾아줘"라고 말하면, AI가 브라우저를 열고 클릭/입력/스크롤을 하면서 결과를 모아 답을 만듭니다.

## 이 시스템이 하는 일

사용자 입장에서는 보통 이렇게 동작합니다:

1. 작업 지시를 입력한다. (예: "상품 가격을 모아줘")
2. 에이전트가 페이지를 읽고 다음 행동을 계획한다.
3. 툴을 통해 실제 브라우저 행동(클릭, 입력, 이동)을 수행한다.
4. 완료되면 요약 결과와 첨부 파일을 반환한다.

## 전체 구조 다이어그램

아래 그림은 사용자 요청이 실제 브라우저 행동으로 바뀌는 흐름입니다.

```mermaid
graph TD
    A[👤 사용자 요청] --> B[🧠 Agent 루프]
    B --> C[📝 Prompt 구성
agent_history + browser_state]
    C --> D[🤖 LLM 응답
ActionModel]
    D --> E[🛠️ Tools 실행]
    E --> F[🌐 BrowserSession/CDP]
    F --> G[📦 ActionResult + History]
    G --> B
    B --> H[✅ done() 최종 응답]
```

## 디렉토리 구조

각 폴더는 역할이 명확히 분리되어 있습니다.

```text
browser-use/
├── browser_use/
│   ├── agent/                ← 일반 브라우저 에이전트 핵심 루프
│   ├── code_use/             ← 코드 셀 기반 CodeAgent
│   ├── tools/                ← 액션 등록/실행(Controller)
│   ├── browser/              ← BrowserSession, CDP, watchdog
│   ├── mcp/                  ← MCP 서버/클라이언트 통합
│   ├── llm/                  ← 다중 LLM 제공자 어댑터
│   ├── skill_cli/            ← 빠른 CLI + 세션 서버
│   ├── filesystem/           ← 파일 읽기/쓰기/치환 도구
│   └── integrations/gmail/   ← Gmail 액션 통합
├── examples/                 ← 실사용 예제
├── docs/                     ← 공식 문서
└── tests/                    ← 테스트 코드
```

## 핵심 용어 설명

| 용어 | 쉬운 설명 |
|------|----------|
| 에이전트 (Agent) | 작업을 단계별로 계획하고 행동을 고르는 AI 실행기 |
| CodeAgent | 코드를 한 셀씩 실행하며 브라우저를 조작하는 모드 |
| 툴/액션 (Tool/Action) | AI가 호출하는 기능 단위(클릭, 입력, 검색, 추출 등) |
| Registry | 액션을 등록하고 JSON 스키마를 만들어 LLM에 제공하는 계층 |
| BrowserSession | 브라우저/CDP 연결 상태를 관리하는 실행 세션 |
| Watchdog | 팝업, 캡차, 다운로드, 크래시 등을 감시하는 보조 모듈 |
| MCP | 외부 툴 서버를 연결해 액션을 동적으로 확장하는 프로토콜 |
| Flash Mode | 빠른 실행을 위해 출력 스키마를 단순화한 모드 |
