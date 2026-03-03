# 🔄 워크플로우

## 워크플로우가 뭔가요?

워크플로우는 "입력 데이터가 어떤 순서로 처리돼 결과 점수가 되는지"를 보여주는 실행 순서도입니다.

## 메인 워크플로우

아래는 `evaluation/agentnetbench/run.py` 기준 핵심 실행 흐름입니다.

```mermaid
flowchart TD
    Start([Start]) --> Load[Load trajectory JSON files]
    Load --> Pick{model type?}
    Pick -->|opencua| AO[OpenCUA Agent]
    Pick -->|qwen| AQ[Qwen25VL Agent]
    Pick -->|aguvis| AA[Aguvis Agent]
    AO --> StepLoop[Step async inference]
    AQ --> StepLoop
    AA --> StepLoop
    StepLoop --> Parse[parse_response + extract_actions]
    Parse --> Score[ActionEvaluator score]
    Score --> Save[save result JSON]
    Save --> Metrics[aggregate metric.json]
    Metrics --> End([Done])
```

## 에이전트 간 상호작용 흐름

실제 상호작용은 "에이전트끼리 협업"보다 "오케스트레이터가 하나를 선택"하는 구조입니다.

```mermaid
sequenceDiagram
    actor U as User
    participant R as run.py
    participant A as Selected Agent
    participant M as Model API
    participant E as eval.py

    U->>R: --model opencua/qwen/aguvis
    R->>A: step prompt 요청
    A->>M: completion 요청
    M-->>A: raw response
    A-->>R: parsed actions
    R->>E: GT 비교 채점
    E-->>R: 점수 반환
    R-->>U: 결과 파일 출력
```

## 오류 처리 흐름

```mermaid
flowchart LR
    T[Step inference] --> OK{response parse success?}
    OK -->|Yes| EV[evaluate_action]
    OK -->|No| ERR[mark parsing_error]
    ERR --> CONT[next step continue]
    EV --> CONT
    CONT --> FIN[final metrics]
```

## 주요 시나리오별 흐름

- `run.py --model opencua`: OpenCUA 전용 히스토리/이미지 모드 파이프라인
- `run.py --model qwen2.5-vl-*`: `<tool_call>` 함수호출 파싱 파이프라인
- `reeval.py`: 모델 재호출 없이 기존 출력 JSON 재채점
