# 📖 이 시스템은 무엇인가요?

## 쉬운 설명

OpenClaw는 "여러 메신저를 하나로 묶은 개인 AI 운영센터"에 가깝습니다.
사람이 WhatsApp, Telegram, Discord 등 어디서 말을 걸어도, Gateway가 동일한 AI 두뇌로 연결해 답하게 해줍니다.

## 이 시스템이 하는 일

- 입력: 다양한 채널에서 들어온 메시지/이벤트
- 처리: Gateway가 라우팅 규칙으로 세션/에이전트를 결정하고 에이전트 런타임 실행
- 행동: 모델이 툴(브라우저, 파일, 메시지, 노드, 크론 등)을 호출
- 출력: 원래 채널/스레드로 응답 전송, 필요 시 서브에이전트/ACP 세션으로 분업

## 전체 구조 다이어그램

아래 그림은 OpenClaw의 기본 데이터 흐름을 보여줍니다.

```mermaid
graph TD
    A[👤 사용자 메시지
(채널)] --> B[🧭 Gateway WS/API]
    B --> C[🧠 라우팅
(bindings/sessionKey)]
    C --> D[🤖 Agent Runtime]
    D --> E[🛠️ Tool 호출
(browser/exec/sessions/...)]
    E --> F[📤 채널 응답 + 이벤트]
    F --> A
    style A fill:#e8f5e9
    style F fill:#e3f2fd
```

## 디렉토리 구조

대형 레포라 핵심 폴더만 보면 이해가 빠릅니다.

```text
openclaw/
├── src/
│   ├── agents/           ← 에이전트 런타임, 프롬프트, 툴 정책
│   ├── gateway/          ← WS/HTTP 제어평면 서버
│   ├── auto-reply/       ← 인바운드 디스패치/응답 큐
│   ├── routing/          ← 채널/계정/peer -> agent 매핑
│   ├── channels/         ← 채널 메타/플러그인 레지스트리
│   └── plugins/          ← 플러그인 로딩/런타임 API
├── extensions/           ← 채널/기능 확장 패키지(33개)
├── skills/               ← 기본 스킬 묶음(52개)
├── docs/                 ← 개념/도구/채널 문서
└── apps/                 ← macOS/iOS/Android 앱 코드
```

## 핵심 용어 설명

| 용어 | 쉬운 설명 |
|------|----------|
| Gateway | 모든 채널/클라이언트 연결을 받는 중앙 관제 서버 |
| SessionKey | 대화 문맥 저장과 동시성 제어를 위한 고유 키 |
| AgentId | 독립 워크스페이스/세션 저장소를 가지는 AI 두뇌 단위 |
| Subagent | 메인 에이전트가 백그라운드로 위임하는 하위 실행 세션 |
| ACP Session | Codex/Claude Code 같은 외부 코딩 하네스를 붙이는 런타임 |
| Skill | 에이전트가 특정 작업을 잘 하도록 주입되는 지식 패키지 |
| Tool Policy | 어떤 툴을 허용/차단할지 결정하는 보안 규칙 |
