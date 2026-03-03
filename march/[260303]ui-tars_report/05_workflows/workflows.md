# 🔄 워크플로우

## 워크플로우가 뭔가요?

워크플로우는 "어떤 순서로 일을 처리하는지"를 보여주는 실행 절차입니다.
UI-TARS 레포의 메인 워크플로우는 모델 추론 자체보다 **응답 후처리 파이프라인**이 중심입니다.

## 메인 워크플로우

아래는 이 저장소 기준 핵심 흐름입니다.

```mermaid
flowchart TD
    Start([🚀 시작]) --> Input[지시 + 스크린샷 준비]
    Input --> Prompt[프롬프트 템플릿 선택]
    Prompt --> Infer[모델 추론]
    Infer --> Check{Action 존재?}
    Check -->|예| Parse[액션 파싱 + 좌표 정규화]
    Check -->|아니오| Fail[파싱 실패 처리]
    Parse --> Code[pyautogui 코드 생성]
    Code --> End([✅ 완료])
    Fail --> End
```

## 컴포넌트 간 상호작용 흐름

이 시퀀스는 사용자 요청이 실제 클릭/타이핑 동작으로 변환되는 시간 흐름입니다.

```mermaid
sequenceDiagram
    actor U as 👤 사용자
    participant M as 🤖 UI-TARS
    participant P as 🔧 Parser
    participant X as 🖥️ Executor

    U->>M: 작업 지시 + 화면
    M-->>P: Thought/Action 텍스트
    P->>P: parse_action_to_structure_output
    P->>P: parsing_response_to_pyautogui_code
    P-->>X: 실행 코드
    X-->>U: GUI 동작 결과
```

## 오류 처리 흐름

파서 코드에서 확인되는 실패/예외 경로를 단순화하면 아래와 같습니다.

```mermaid
flowchart LR
    A[액션 문자열 입력] --> B{문법 파싱 성공?}
    B -->|예| C[구조화 액션 생성]
    B -->|아니오| D[ValueError/None 처리]
    C --> E{지원 액션 타입?}
    E -->|예| F[코드 생성]
    E -->|아니오| G[주석 처리된 Unrecognized action]
```

## 주요 시나리오별 흐름

- 데스크톱 시나리오: `COMPUTER_USE_DOUBAO` -> click/type/hotkey 위주
- 모바일 시나리오: `MOBILE_USE_DOUBAO` -> open_app/press_home/press_back 포함
- 평가 시나리오: `GROUNDING_DOUBAO` -> Action-only 출력으로 단순 평가
