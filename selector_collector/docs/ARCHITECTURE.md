# 아키텍처 설계

## 전체 구조

AI Recorder는 Chrome Extension Manifest V3를 기반으로 하며, 3개의 주요 컨텍스트로 구성됩니다:

1. **Popup (React UI)**: 사용자 인터페이스
2. **Background Script (Service Worker)**: 중앙 메시지 라우터 및 상태 관리
3. **Content Script**: 웹 페이지 이벤트 캡처 및 리플레이

## 컴포넌트 다이어그램

```
┌─────────────────────────────────────────────────────────────┐
│                          Popup UI                            │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │   Header   │  │ ControlBar │  │   Footer   │            │
│  └────────────┘  └────────────┘  └────────────┘            │
│  ┌──────────────────────────────────────────────┐           │
│  │            StepGroup (접기/펴기)              │           │
│  │  ┌────────────────────────────────────────┐  │           │
│  │  │  StepItem (편집 가능한 라벨)           │  │           │
│  │  │  • 아이콘 • 라벨 • 셀렉터 • 상태      │  │           │
│  │  └────────────────────────────────────────┘  │           │
│  └──────────────────────────────────────────────┘           │
│  ┌──────────────────────────────────────────────┐           │
│  │         JsonPanel (JSON 미리보기)            │           │
│  │         • 복사 버튼 • AI 처리 버튼           │           │
│  └──────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────┘
                            ↕ Messages
┌─────────────────────────────────────────────────────────────┐
│                    Background Script                         │
│  • 메시지 라우팅 (popup ↔ content script)                   │
│  • RecordingState 관리 (Chrome Storage)                     │
│  • 스텝 자동 그룹핑 (휴리스틱 기반)                         │
│  • 리플레이 오케스트레이션 (500ms 간격)                     │
└─────────────────────────────────────────────────────────────┘
                            ↕ Messages
┌─────────────────────────────────────────────────────────────┐
│                      Content Script                          │
│  • 이벤트 리스너 (click, input, keydown)                    │
│  • CSS 셀렉터 생성 (generateSelector)                       │
│  • 라벨 생성 (generateLabel)                                │
│  • 리플레이 엔진 (DOM 조작 + 이벤트 디스패치)               │
│  • 녹화 인디케이터 (빨간 애니메이션 바)                     │
└─────────────────────────────────────────────────────────────┘
```

## 데이터 흐름

### 1. 녹화 시작
```
User clicks "Record"
  → Popup: sendToBackground({ type: 'START_RECORDING' })
  → Background:
      - 현재 탭 조회
      - content script 주입 확인
      - RecordingState 업데이트 (status: 'recording')
      - sendToContentScript({ type: 'START_RECORDING' })
  → Content Script:
      - 이벤트 리스너 등록 (click, input, keydown)
      - 녹화 인디케이터 표시
```

### 2. 스텝 기록
```
User interacts with page
  → Content Script:
      - 이벤트 캡처 (capture phase)
      - generateSelector(element)
      - generateLabel(element, action)
      - sendToBackground({ type: 'STEP_RECORDED', payload })
  → Background:
      - Step 객체 생성 (ID, timestamp 추가)
      - RecordingState.steps 업데이트
      - groupSteps(steps) → 자동 그룹핑
      - Chrome Storage에 저장
  → Popup:
      - watchState로 변경 감지
      - UI 업데이트 (새 스텝 표시)
```

### 3. 리플레이
```
User clicks "Replay"
  → Popup: sendToBackground({ type: 'START_REPLAY' })
  → Background:
      - 현재 탭 조회
      - RecordingState.status = 'replaying'
      - for each step:
          - 500ms delay
          - sendToContentScript({ type: 'REPLAY_STEP', payload })
  → Content Script:
      - querySelector(selector)
      - 액션에 따라 DOM 조작:
          - click: element.click()
          - input: 값 설정 + input/change 이벤트
          - keydown: KeyboardEvent 디스패치
```

## 상태 관리

### RecordingState (Chrome Storage)
```typescript
interface RecordingState {
  status: 'idle' | 'recording' | 'replaying';
  steps: Step[];
  groups: StepGroupData[];
  activeTabId: number | null;
  selectedStepId: string | null;
}
```

- **저장소**: `chrome.storage.local`
- **동기화**: `chrome.storage.onChanged` 이벤트로 Popup과 동기화
- **영속성**: 확장 프로그램 재시작 후에도 유지

### Step 데이터 구조
```typescript
interface Step {
  id: string;              // UUID
  action: 'click' | 'input' | 'keydown' | 'navigate';
  selector: string;        // CSS 셀렉터
  label: string;           // 사용자 편집 가능
  value?: string;          // input 값
  key?: string;            // keydown 키
  url?: string;            // 페이지 URL
  timestamp: number;       // Date.now()
}
```

### StepGroupData 구조
```typescript
interface StepGroupData {
  id: string;              // UUID
  name: string;            // "Login Flow", "Search Process" 등
  icon: string;            // Material Symbol 이름
  steps: Step[];           // 그룹에 속한 스텝들
  collapsed: boolean;      // 접기/펴기 상태
}
```

## CSS 셀렉터 생성 알고리즘

### 우선순위 체인
1. **tryIdSelector**: ID 속성 (자동생성 패턴 제외)
2. **tryTestAttributes**: data-testid, data-qa, data-cy
3. **tryNameAttribute**: name 속성 (input, select 등)
4. **tryAriaAttributes**: role, aria-label 조합
5. **tryClassCombination**: 유니크 클래스 (유틸리티 클래스 제외)
6. **tryAttributeCombination**: type, placeholder, href 등
7. **tryParentContext**: 부모 요소 포함 계층적 셀렉터
8. **nthChildPath**: nth-child 전체 경로 (최후 수단)

### 필터링 패턴
- **자동생성 ID**: `:r[0-9a-z]+:`, `^react-`, `^ember\d+`, 해시값
- **유틸리티 클래스**: `css-`, `sc-`, `emotion-`, Tailwind 임의값
- **특수문자 이스케이프**: `CSS.escape()` 사용

### 유니크성 검증
모든 단계에서 `document.querySelectorAll(selector).length === 1` 확인

## 스텝 자동 그룹핑

### 휴리스틱 규칙
```typescript
function categorizeStep(step: Step): { name: string; icon: string } {
  // Login/Auth
  if (includes('login', 'auth', 'password', 'email', 'sign'))
    return { name: 'Login Flow', icon: 'lock_open' };

  // Search
  if (includes('search', 'find', 'filter'))
    return { name: 'Search Process', icon: 'search' };

  // Navigation
  if (action === 'click' && includes('nav', 'menu', 'link'))
    return { name: 'Navigation', icon: 'explore' };

  // Form
  if (action === 'input' || includes('form', 'input', 'textarea'))
    return { name: 'Form Input', icon: 'edit_note' };

  // Default
  return { name: 'User Actions', icon: 'touch_app' };
}
```

### 그룹핑 로직
- 연속된 같은 카테고리 스텝을 하나의 그룹으로 병합
- 카테고리 변경 시 새 그룹 생성
- 각 그룹에 UUID 할당

## 메시지 타입

### Popup → Background
- `START_RECORDING`: 녹화 시작 요청
- `STOP_RECORDING`: 녹화 중지 요청
- `START_REPLAY`: 리플레이 시작 요청
- `GET_STATE`: 현재 상태 조회

### Background → Content Script
- `START_RECORDING`: 이벤트 리스너 등록
- `STOP_RECORDING`: 이벤트 리스너 제거
- `REPLAY_STEP`: 단일 스텝 재실행

### Content Script → Background
- `STEP_RECORDED`: 새 스텝 기록

## 성능 최적화

### 1. 이벤트 디바운싱
- **input 이벤트**: 500ms 디바운스로 최종 값만 캡처
- 타이핑 중 불필요한 중간 값 기록 방지

### 2. Capture Phase 리스닝
- click 이벤트를 capture phase에서 캡처
- 다른 이벤트 핸들러보다 먼저 실행 보장

### 3. Storage Watch
- `chrome.storage.onChanged`로 변경사항만 감지
- 불필요한 polling 없음

### 4. 조건부 Content Script 주입
- background에서 content script 존재 여부 확인
- 없는 경우에만 `chrome.scripting.executeScript` 호출

## 보안 고려사항

### 1. 셀렉터 이스케이프
- `CSS.escape()`로 모든 특수문자 처리
- XSS 공격 방지

### 2. Permissions
- `activeTab`: 현재 탭에만 접근
- `storage`: 로컬 스토리지만 사용
- `tabs`: 탭 정보 조회용
- `scripting`: content script 주입용
- `host_permissions`: `<all_urls>` (모든 페이지에서 동작)

### 3. Content Security Policy
- Manifest V3 기본 CSP 준수
- inline script 없음, 모든 코드 번들링

## 확장성

### 1. 새로운 액션 타입 추가
- `utils/types.ts`에 StepAction 추가
- `content.ts`에 이벤트 리스너 추가
- `selector.ts`에 라벨 생성 로직 추가

### 2. 새로운 그룹 카테고리
- `background.ts`의 `categorizeStep` 함수 수정
- 키워드 및 아이콘 추가

### 3. 외부 저장소 연동
- `utils/storage.ts` 인터페이스 유지
- 구현체를 API 호출로 대체 가능

### 4. AI 기능 추가
- JsonPanel의 "AI Selector Processing" 버튼 활성화
- LLM API 연동하여 셀렉터 최적화 기능 구현
