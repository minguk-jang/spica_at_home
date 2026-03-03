# 🔄 워크플로우

## 워크플로우가 뭔가요?

워크플로우는 "입력부터 결과까지의 처리 순서"입니다.  
`browser-use`는 `Agent` 모드와 `CodeAgent` 모드의 두 가지 주요 실행 흐름이 있습니다.

## 메인 워크플로우 (Agent)

이 다이어그램은 일반 `Agent.run()` 루프를 단순화한 것입니다.

```mermaid
flowchart TD
    Start([🚀 시작]) --> Init[브라우저 세션 시작]
    Init --> Register[스킬/액션 등록]
    Register --> InitActions{초기 액션 존재?}
    InitActions -->|예| RunInit[초기 액션 실행]
    InitActions -->|아니오| Loop
    RunInit --> Loop[스텝 루프 진입]

    Loop --> Build[메시지 조합
history+state+prompt]
    Build --> LLM[LLM 호출]
    LLM --> Parse[ActionModel 파싱]
    Parse --> Act[multi_act 실행]
    Act --> Update[history/plan/failure 갱신]
    Update --> DoneCheck{done/is_done?}
    DoneCheck -->|예| Judge{judge 사용?}
    Judge -->|예| JudgeRun[judge 검증]
    Judge -->|아니오| End
    JudgeRun --> End([✅ 종료])
    DoneCheck -->|아니오| Limit{실패/스텝 한계?}
    Limit -->|아니오| Loop
    Limit -->|예| End
```

## 에이전트 간 상호작용 흐름

이 그림은 Agent, LLM, Tools, BrowserSession 사이 메시지 흐름을 보여줍니다.

```mermaid
sequenceDiagram
    actor U as 👤 사용자
    participant A as 🧠 Agent
    participant M as 📝 MessageManager
    participant L as 🤖 LLM
    participant T as 🛠️ Tools
    participant B as 🌐 BrowserSession

    U->>A: task
    A->>M: 현재 상태/히스토리 전달
    M->>L: prompt 구성 후 호출
    L-->>A: action[] JSON
    A->>T: act/multi_act
    T->>B: 이벤트 실행(click/input/navigate)
    B-->>T: 실행 결과/오류
    T-->>A: ActionResult
    A->>A: history 축적 + 다음 step 계획
    A-->>U: done 결과
```

## CodeAgent 워크플로우

`CodeAgent`는 "코드 셀 실행"이라는 점에서 일반 Agent와 다릅니다.

```mermaid
flowchart LR
    A[Task] --> B[LLM이 Python 코드 생성]
    B --> C[코드 블록 추출/정리]
    C --> D[Namespace에서 실행]
    D --> E[브라우저 상태 갱신]
    E --> F{done() 호출됨?}
    F -->|아니오| B
    F -->|예| G[최종 결과 + 첨부파일 반환]
```

## 오류 처리 흐름

```mermaid
flowchart LR
    Task[작업 실행] --> Success{성공?}
    Success -->|예| Continue[다음 스텝]
    Success -->|아니오| Recover{복구 가능?}
    Recover -->|예| Retry[재시도/재연결]
    Recover -->|아니오| FailCount[연속 실패 카운트 증가]
    Retry --> Task
    FailCount --> Limit{max_failures 초과?}
    Limit -->|아니오| Task
    Limit -->|예| Stop[중단 또는 마지막 응답 시도]
```

## 주요 시나리오별 흐름

1. **일반 웹 자동화**: `Agent -> Tools -> BrowserSession -> ActionResult`
2. **코드 기반 자동화**: `CodeAgent -> evaluate/navigate/click -> namespace 누적`
3. **MCP 연동**: `MCPClient가 외부 도구 스키마를 Action으로 변환 후 Agent가 동일 루프에서 사용`
4. **CLI 지속 세션**: `skill_cli/server.py`가 IPC로 세션을 유지해 명령 간 브라우저 상태 재사용
