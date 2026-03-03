# 🔄 워크플로우

## 워크플로우가 뭔가요?

워크플로우는 "명령이 실제 결과가 되기까지의 순서"입니다. 이 레포의 핵심은 **세션 데몬 + 액션 디스패처 + 브라우저 매니저** 3단 구조입니다.

## 메인 워크플로우

이 그림은 기본 실행 경로를 보여줍니다.

```mermaid
flowchart TD
    Start([🚀 시작]) --> Input[CLI 명령 입력]
    Input --> Parse[명령 파싱: cli/src/commands.rs]
    Parse --> Ensure[daemon 연결/기동 ensure_daemon]
    Ensure --> Queue[daemon 명령 큐 직렬 처리]
    Queue --> Policy{정책 허용?}
    Policy -->|deny| Deny[오류 응답 반환]
    Policy -->|confirm| Confirm[확인 토큰 발급]
    Policy -->|allow| Dispatch[dispatchAction]
    Dispatch --> Execute[BrowserManager/IOSManager 실행]
    Execute --> Resp[JSON 응답 생성]
    Resp --> End([✅ 완료])
    Deny --> End
    Confirm --> End
```

## 에이전트 간 상호작용 흐름

아래 그림은 실제 실행 시퀀스입니다.

```mermaid
sequenceDiagram
    actor U as 👤 사용자/LLM
    participant R as Rust CLI
    participant D as Node daemon
    participant A as actions
    participant B as browser engine

    U->>R: 명령 입력
    R->>D: JSON + session
    Note over D: auto-launch 필요 시 브라우저 실행
    D->>A: parseCommand + executeCommand
    A->>B: handleX 실행
    B-->>A: 실행 결과
    A-->>D: success/error
    D-->>R: line JSON
    R-->>U: 포맷 출력
```

## 오류 처리 흐름

이 그림은 재시도/폴백 흐름을 보여줍니다.

```mermaid
flowchart LR
    Send[명령 전송] --> Ok{응답 성공?}
    Ok -->|예| Done[완료]
    Ok -->|아니오| Transient{일시 오류?
EAGAIN/EOF/ECONNRESET}
    Transient -->|예| Retry[지수형 대기 후 재시도]
    Retry --> Send
    Transient -->|아니오| Fail[즉시 실패 반환]
```

## 주요 시나리오별 흐름

### 1) Snapshot-ref 루프

```mermaid
flowchart TD
    S1[snapshot -i] --> S2[@e1/@e2 refs 획득]
    S2 --> S3[click/fill 등 실행]
    S3 --> S4[DOM 변경]
    S4 --> S1
```

### 2) Docs Chat 흐름

- 사용자가 docs 질문을 보냄
- `SYSTEM_PROMPT`가 read-only 규칙을 강제
- `bash/readFile` 툴로 mdx 변환 문서를 조회
- 스트리밍 응답 반환
