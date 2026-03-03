# 🏗️ 시스템 아키텍처

## 아키텍처란?

아키텍처는 "시스템의 부품과 연결 관계"를 보여주는 설계도입니다.
OpenClaw는 Gateway를 중심으로 Agent/Tool/Channel/Node가 붙는 허브 구조입니다.

## 전체 컴포넌트 구조

이 그림은 OpenClaw의 주요 레이어와 연결 방향을 보여줍니다.

```mermaid
graph LR
    subgraph "입력 레이어"
        A[채널 입력
WhatsApp/Telegram/Slack/Discord]
        B[클라이언트
CLI/WebChat/macOS/iOS/Android]
    end

    subgraph "제어 레이어"
        C[Gateway Server
WS + HTTP + Method Router]
        D[Routing/Session Resolver]
    end

    subgraph "처리 레이어"
        E[Embedded Pi Agent Runtime]
        F[Subagent Runtime]
        G[ACP Runtime]
    end

    subgraph "도구/확장 레이어"
        H[Core Tools
25종]
        I[Plugin Tools]
        J[Nodes/Canvas/Browser]
    end

    A --> C
    B --> C
    C --> D
    D --> E
    E --> F
    E --> G
    E --> H
    H --> I
    H --> J
```

## 데이터 흐름

아래 시퀀스는 일반적인 채널 메시지가 처리되는 시간 순서입니다.

```mermaid
sequenceDiagram
    actor User as 👤 사용자
    participant Ch as 📱 Channel Adapter
    participant Gw as 🧭 Gateway
    participant Rt as 🧠 Route Resolver
    participant Ag as 🤖 Agent Runtime
    participant Tl as 🛠️ Tools

    User->>Ch: 메시지 전송
    Ch->>Gw: 인바운드 이벤트
    Gw->>Rt: agentId/sessionKey 결정
    Rt->>Ag: 실행 컨텍스트 전달
    Ag->>Tl: 필요 툴 호출
    Tl-->>Ag: 툴 결과 반환
    Ag-->>Gw: 응답/스트림 이벤트
    Gw-->>Ch: 채널별 전송
    Ch-->>User: 최종 메시지
```

## 계층별 설명

- 입력 레이어: 다양한 채널과 앱에서 이벤트 수신
- 제어 레이어: Gateway가 인증/검증/라우팅/세션 제어 담당
- 처리 레이어: 기본 에이전트 + 필요 시 Subagent/ACP로 분기
- 도구 레이어: 파일/실행/웹/메시지/노드/플러그인 툴 실행

