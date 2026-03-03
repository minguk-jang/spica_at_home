# 🏗️ 시스템 아키텍처

## 아키텍처란?

아키텍처는 "어떤 부품이 어떤 순서로 일하는지"를 보여주는 설계도입니다.
UI-TARS 레포는 대규모 오케스트레이터보다 "모델 출력 후처리 레이어"가 핵심입니다.

## 전체 컴포넌트 구조

이 그림은 입력-추론-후처리-실행의 4계층 구조를 보여줍니다.

```mermaid
graph LR
    subgraph "입력 레이어"
        A[사용자 지시]
        B[스크린샷]
    end
    subgraph "추론 레이어"
        C[Prompt Template]
        D[UI-TARS Model]
    end
    subgraph "후처리 레이어"
        E[action_parser.parse_action_to_structure_output]
        F[action_parser.parsing_response_to_pyautogui_code]
    end
    subgraph "실행 레이어"
        G[pyautogui Runtime]
    end

    A --> C
    B --> D
    C --> D
    D --> E
    E --> F
    F --> G
```

## 데이터 흐름

아래 시퀀스는 실제 시간 순서대로 "요청 -> 액션 문자열 -> 실행 코드"가 만들어지는 과정을 보여줍니다.

```mermaid
sequenceDiagram
    actor User as 👤 사용자
    participant Prompt as 🧾 Prompt 템플릿
    participant Model as 🤖 UI-TARS 모델
    participant Parser as 🔧 action_parser
    participant Exec as 🖱️ pyautogui

    User->>Prompt: 목표 전달
    Prompt->>Model: 지시 + 액션 스키마 제공
    Model-->>Parser: Thought/Action 텍스트 반환
    Parser->>Parser: 좌표 정규화 + 액션 구조화
    Parser-->>Exec: 실행 코드 문자열 전달
    Exec-->>User: GUI 동작 수행
```

## 계층별 설명

- 입력 레이어: 사용자 목표와 스크린샷을 준비
- 추론 레이어: `COMPUTER_USE_DOUBAO`/`MOBILE_USE_DOUBAO`/`GROUNDING_DOUBAO` 중 하나로 모델 행동 포맷 고정
- 후처리 레이어: 문자열 파싱, 좌표 변환, 액션 타입 분기 처리
- 실행 레이어: 생성된 `pyautogui` 코드로 실제 마우스/키보드 이벤트 수행
