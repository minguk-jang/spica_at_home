# AI Recorder - Chrome Extension

Chrome DevTools Recorder와 유사한 기능을 제공하는 Chrome Extension입니다. 사용자의 클릭, 입력 등 상호작용을 녹화하고, `document.querySelector(selector).click()`으로 재실행 가능한 CSS 셀렉터를 자동으로 생성합니다.

## 주요 기능

### 1. 사용자 상호작용 녹화
- **클릭 이벤트**: 모든 클릭 동작 캡처
- **입력 이벤트**: input/textarea의 값 변경 (500ms 디바운싱)
- **키보드 이벤트**: Enter/Escape 키 입력
- **녹화 중 시각적 피드백**: 페이지 상단 빨간색 애니메이션 바

### 2. 스마트 CSS 셀렉터 생성
우선순위 체인으로 유니크하고 안정적인 셀렉터 생성:
1. ID 셀렉터 (자동생성 패턴 제외)
2. 테스트 속성 (data-testid, data-qa, data-cy)
3. name 속성 (폼 요소)
4. ARIA 속성 (role, aria-label)
5. 유니크 클래스 조합 (CSS-in-JS/Tailwind 유틸리티 제외)
6. 속성 조합 (type, placeholder, href)
7. 부모 컨텍스트 포함 계층적 셀렉터
8. nth-child 경로 (최후 수단)

### 3. 자동 스텝 그룹핑
키워드 기반 휴리스틱으로 스텝을 의미있는 그룹으로 자동 분류:
- **Login Flow**: 로그인/인증 관련 동작
- **Search Process**: 검색 관련 동작
- **Navigation**: 네비게이션/메뉴 이동
- **Form Input**: 폼 입력 동작
- **User Actions**: 기타 사용자 동작

### 4. 리플레이 기능
녹화된 스텝을 순서대로 재실행 (500ms 간격):
- 클릭 이벤트 디스패치
- 입력 값 설정 및 이벤트 트리거
- 키보드 이벤트 시뮬레이션
- Enter 키 시 form submit 자동 처리

### 5. 편집 가능한 UI
- 스텝 라벨 인라인 편집
- 그룹 접기/펴기
- JSON 형식으로 스텝 정의 미리보기
- 클립보드 복사 기능

## 기술 스택

- **프레임워크**: WXT 0.20.x (Web Extension Tools)
- **UI**: React 19 + TypeScript
- **스타일링**: Tailwind CSS v4
- **아이콘**: Material Symbols Outlined
- **폰트**: Inter
- **저장소**: Chrome Storage API
- **빌드**: Vite 7.3.1

## 프로젝트 구조

```
selector_collector/
├── assets/
│   └── styles.css              # Tailwind + 커스텀 스타일
├── components/
│   ├── Header.tsx              # 상단 헤더
│   ├── ControlBar.tsx          # Record/Replay 버튼바
│   ├── StepGroup.tsx           # 스텝 그룹 컴포넌트
│   ├── StepItem.tsx            # 개별 스텝 아이템
│   ├── JsonPanel.tsx           # JSON 미리보기 패널
│   └── Footer.tsx              # 상태바
├── entrypoints/
│   ├── popup/
│   │   ├── index.html          # 팝업 HTML
│   │   ├── main.tsx            # React 진입점
│   │   └── App.tsx             # 메인 App 컴포넌트
│   ├── content.ts              # Content script (이벤트 녹화/리플레이)
│   └── background.ts           # Service worker (메시지 라우팅)
├── hooks/
│   └── useRecording.ts         # 녹화 상태 관리 훅
├── utils/
│   ├── types.ts                # TypeScript 타입 정의
│   ├── selector.ts             # CSS 셀렉터 생성 알고리즘
│   ├── storage.ts              # Chrome Storage 래퍼
│   └── messaging.ts            # 메시지 유틸리티
└── public/
    └── icon/                   # 확장 프로그램 아이콘
```

## 설치 및 실행

```bash
# 의존성 설치
npm install

# 개발 모드 (자동 리로드)
npm run dev

# 프로덕션 빌드
npm run build

# TypeScript 타입 체크
npm run compile
```

개발 모드 실행 후:
1. Chrome에서 `chrome://extensions/` 접속
2. "개발자 모드" 활성화
3. "압축해제된 확장 프로그램을 로드합니다" 클릭
4. `.output/chrome-mv3` 디렉토리 선택

## 사용 방법

1. **녹화 시작**: 팝업에서 "Record" 버튼 클릭
2. **상호작용**: 웹 페이지에서 클릭/입력 등 동작 수행
3. **녹화 중지**: "Stop" 버튼 클릭
4. **리플레이**: "Replay" 버튼으로 녹화된 동작 재실행
5. **편집**: 스텝 라벨 클릭하여 수정
6. **JSON 복사**: JSON 패널에서 복사 아이콘 클릭

## 통신 흐름

```
Content Script ──STEP_RECORDED──> Background ──chrome.storage──> Popup (watch)
Popup ──START_RECORDING──> Background ──START_RECORDING──> Content Script
Popup ──START_REPLAY──> Background ──START_REPLAY──> Content Script
```

## 라이선스

MIT License

## 참고 문서

- [아키텍처 설계](./ARCHITECTURE.md)
- [구현 세부사항](./IMPLEMENTATION.md)
- [개발 가이드](./DEVELOPMENT.md)
