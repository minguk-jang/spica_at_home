# 🔄 워크플로우

## 워크플로우가 뭔가요?

워크플로우는 "메시지가 들어와서 어떤 단계로 처리되는지"를 보여주는 순서도입니다.
OpenClaw는 채널 입력을 Gateway가 받아 세션 라우팅 후 Agent 런타임을 돌리고, 결과를 같은 채널로 되돌려 보냅니다.

## 메인 워크플로우

아래는 `dispatchInboundMessage` + Gateway chat/agent 경로를 합친 핵심 흐름입니다.

```mermaid
flowchart TD
    Start([🚀 인바운드 이벤트]) --> Normalize[입력 정규화/검증]
    Normalize --> Route{agent/session 라우팅 성공?}
    Route -->|아니오| Reject[오류 응답]
    Route -->|예| Run[runEmbeddedPiAgent 실행]
    Run --> ToolLoop{툴 호출 필요?}
    ToolLoop -->|예| ToolExec[툴 정책 검사 + 실행]
    ToolExec --> Run
    ToolLoop -->|아니오| Stream[delta/block/final 스트림 생성]
    Stream --> Deliver[채널/스레드로 전달]
    Deliver --> End([✅ 완료])
    Reject --> End
```

## 에이전트 간 상호작용 흐름

`sessions_spawn` 사용 시 메인-서브 구조는 아래처럼 동작합니다.

```mermaid
sequenceDiagram
    actor U as 👤 사용자
    participant M as 🧠 Main Agent
    participant S as 🧩 Subagent/ACP
    participant G as 🧭 Gateway

    U->>M: 메인 요청
    M->>S: sessions_spawn(task)
    S-->>G: child run accepted
    S->>S: 독립 세션 작업 수행
    S-->>M: announce/summary 전달
    M-->>U: 최종 통합 응답
```

## 오류 처리 흐름

실패 시에는 failover와 재시도/정책 분기로 복구를 시도합니다.

```mermaid
flowchart LR
    Task[모델/툴 실행] --> OK{성공?}
    OK -->|예| Done[정상 종료]
    OK -->|아니오| Classify[오류 분류
auth/rate/timeout/context]
    Classify --> Retry{재시도/폴백 가능?}
    Retry -->|예| Fallback[모델/프로파일 폴백]
    Fallback --> Task
    Retry -->|아니오| Fail[에러 메시지 + 상태 기록]
```

## 주요 시나리오별 흐름

- 기본 채널 응답: `gateway.server-methods.chat -> dispatchInboundMessage -> runEmbeddedPiAgent`
- 세션 간 위임: `sessions_send` 또는 `sessions_spawn` 후 announce
- ACP 위임: `sessions_spawn(runtime=acp)`에서 정책 검증 후 ACP 세션 생성
- 큐 모드: `collect`, `steer`, `followup`, `interrupt` 정책으로 인바운드 충돌 처리
