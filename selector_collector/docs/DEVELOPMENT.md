# 개발 가이드

## 개발 환경 설정

### 필수 도구
- Node.js 18+
- npm 9+
- Chrome 브라우저

### 프로젝트 초기 설정
```bash
# 저장소 클론
git clone <repository-url>
cd selector_collector

# 의존성 설치
npm install

# WXT 타입 생성
npm run postinstall
```

## 개발 워크플로우

### 1. 개발 서버 시작
```bash
npm run dev
```

이 명령은:
- WXT 개발 서버 시작
- `.output/chrome-mv3` 디렉토리에 빌드
- 파일 변경 시 자동 리빌드
- 확장 프로그램 자동 리로드 (Chrome에서 설정 필요)

### 2. Chrome에 확장 프로그램 로드
1. Chrome에서 `chrome://extensions/` 열기
2. 우측 상단 "개발자 모드" 토글 활성화
3. "압축해제된 확장 프로그램을 로드합니다" 클릭
4. `.output/chrome-mv3` 디렉토리 선택

### 3. 개발 중 디버깅

#### Popup 디버깅
1. 확장 프로그램 아이콘 클릭
2. 팝업에서 우클릭 → "검사"
3. DevTools 열림 (React DevTools 사용 가능)

#### Background Script 디버깅
1. `chrome://extensions/` 페이지에서
2. AI Recorder 확장 프로그램 찾기
3. "service worker" 링크 클릭
4. DevTools 열림

#### Content Script 디버깅
1. 녹화하려는 웹 페이지에서 F12 (DevTools)
2. Console 탭에서 `[AI Recorder]` 로그 확인
3. Sources 탭에서 `content.js` 브레이크포인트 설정

### 4. 타입 체크
```bash
npm run compile
```

TypeScript 컴파일 없이 타입만 체크합니다.

### 5. 프로덕션 빌드
```bash
npm run build
```

최적화된 프로덕션 빌드를 `.output/chrome-mv3`에 생성합니다.

### 6. ZIP 패키징
```bash
npm run zip
```

Chrome Web Store 업로드용 ZIP 파일을 생성합니다.

## 코드 구조 가이드

### 새로운 컴포넌트 추가

1. `components/` 디렉토리에 파일 생성:
```tsx
// components/NewComponent.tsx
interface NewComponentProps {
  // props 정의
}

export default function NewComponent({ }: NewComponentProps) {
  return <div>New Component</div>;
}
```

2. WXT가 자동으로 전역 import하므로 별도 import 불필요:
```tsx
// App.tsx에서 바로 사용 가능
function App() {
  return <NewComponent />;
}
```

### 새로운 유틸리티 함수 추가

```typescript
// utils/newUtil.ts
export function newUtilFunction() {
  // 구현
}
```

WXT auto-import로 전역 사용 가능:
```typescript
// 다른 파일에서 import 없이 사용
const result = newUtilFunction();
```

### 새로운 타입 추가

```typescript
// utils/types.ts
export interface NewType {
  // 필드 정의
}

// 컴포넌트 이름과 충돌하지 않도록 주의!
// 예: StepGroup(컴포넌트) vs StepGroupData(타입)
```

### 새로운 메시지 타입 추가

1. `utils/types.ts`에 메시지 타입 추가:
```typescript
export type MessageType =
  | 'START_RECORDING'
  | 'STOP_RECORDING'
  | 'NEW_MESSAGE_TYPE';  // 추가
```

2. Background에서 핸들러 구현:
```typescript
// entrypoints/background.ts
async function handleMessage(message: Message, _sender) {
  switch (message.type) {
    case 'NEW_MESSAGE_TYPE':
      // 처리 로직
      return { success: true };
  }
}
```

3. Content Script에서 수신 (필요한 경우):
```typescript
// entrypoints/content.ts
browser.runtime.onMessage.addListener((message: Message) => {
  if (message.type === 'NEW_MESSAGE_TYPE') {
    // 처리 로직
  }
});
```

## 일반적인 개발 작업

### 스타일 수정

Tailwind CSS v4 사용:
```css
/* assets/styles.css */
@theme {
  --color-new-color: #123456;  /* 새 컬러 추가 */
}
```

컴포넌트에서 사용:
```tsx
<div className="bg-new-color text-white">
  Custom color
</div>
```

### 아이콘 변경

Material Symbols 사용:
```tsx
<span className="material-symbols-outlined">
  icon_name
</span>
```

[Material Symbols 검색](https://fonts.google.com/icons)에서 아이콘 이름 확인

### Storage 데이터 구조 변경

1. `utils/types.ts`에서 타입 수정:
```typescript
export interface RecordingState {
  status: RecordingStatus;
  steps: Step[];
  groups: StepGroupData[];
  newField: string;  // 추가
}

export const DEFAULT_RECORDING_STATE: RecordingState = {
  status: 'idle',
  steps: [],
  groups: [],
  activeTabId: null,
  selectedStepId: null,
  newField: 'default',  // 기본값
};
```

2. 기존 사용자의 데이터 마이그레이션 고려:
```typescript
// utils/storage.ts
export async function getState(): Promise<RecordingState> {
  const result = await browser.storage.local.get(STORAGE_KEY);
  const stored = result[STORAGE_KEY] as RecordingState | undefined;

  if (!stored) return DEFAULT_RECORDING_STATE;

  // 마이그레이션
  if (!('newField' in stored)) {
    stored.newField = 'default';
  }

  return stored;
}
```

## 테스트

### 수동 테스트 체크리스트

#### 녹화 기능
- [ ] Record 버튼 클릭 시 빨간 인디케이터 표시
- [ ] 클릭 이벤트 기록
- [ ] Input 값 변경 기록 (디바운싱 확인)
- [ ] Enter 키 기록
- [ ] 녹화 중 팝업 닫았다 열어도 상태 유지
- [ ] Stop 버튼으로 녹화 중지
- [ ] 인디케이터 사라짐 확인

#### 셀렉터 생성
- [ ] ID가 있는 요소: `#id` 형태
- [ ] data-testid 있는 요소: `[data-testid="value"]` 형태
- [ ] name 속성: `input[name="value"]` 형태
- [ ] 클래스만: `button.class-name` 형태
- [ ] 복잡한 경우: 계층적 셀렉터 또는 nth-child

#### 그룹핑
- [ ] 로그인 관련: "Login Flow"
- [ ] 검색 관련: "Search Process"
- [ ] 네비게이션: "Navigation"
- [ ] 폼 입력: "Form Input"

#### 리플레이
- [ ] Replay 버튼 클릭 시 순차 실행
- [ ] 클릭 동작 재현
- [ ] Input 값 입력 재현
- [ ] Enter 키 동작 재현
- [ ] 셀렉터 찾지 못한 경우 콘솔 경고

#### UI 편집
- [ ] 스텝 라벨 클릭하여 수정
- [ ] 그룹 헤더 클릭하여 접기/펴기
- [ ] JSON 패널에 선택된 스텝 표시
- [ ] 복사 버튼으로 JSON 복사

### 크로스 브라우저 테스트
- [ ] Chrome (주 타겟)
- [ ] Firefox (npm run dev:firefox)
- [ ] Edge (Chromium 기반)

## 디버깅 팁

### Console 로그 활용
```typescript
// Content Script
console.log('[AI Recorder Content]', 'message', data);

// Background Script
console.log('[AI Recorder Background]', 'message', data);
```

### Chrome Storage 확인
DevTools Console에서:
```javascript
chrome.storage.local.get('recordingState', console.log);
```

### Storage 초기화
```javascript
chrome.storage.local.clear();
```

### WXT 자동생성 파일 확인
```bash
ls -la .wxt/types/
```

auto-import 타입 정의를 확인하여 이름 충돌 디버깅

## 일반적인 문제 해결

### WXT 빌드 실패

**증상**: `npm run dev` 시 빌드 오류

**해결**:
1. `.wxt` 디렉토리 삭제
2. `node_modules` 삭제
3. `npm install` 재실행
4. `npm run dev` 재시도

### Content Script가 주입되지 않음

**증상**: 녹화 시작해도 이벤트 캡처 안됨

**해결**:
1. `chrome://extensions/` 에서 확장 프로그램 리로드
2. 웹 페이지 새로고침
3. DevTools Console에서 content script 로드 확인

### Tailwind 클래스가 적용 안됨

**증상**: 커스텀 클래스 스타일이 안나옴

**해결**:
1. `assets/styles.css`에 `@theme` 블록 확인
2. 빌드 재시작 (`npm run dev` Ctrl+C 후 재실행)
3. 생성된 CSS 파일 확인: `.output/chrome-mv3/assets/*.css`

### TypeScript 타입 에러

**증상**: `npm run compile` 실패

**해결**:
1. `.wxt/tsconfig.json` 확인
2. `npm run postinstall`로 타입 재생성
3. IDE 재시작 (VSCode 등)

## 성능 프로파일링

### Popup 렌더링 성능
React DevTools Profiler 사용:
1. Popup DevTools 열기
2. Profiler 탭
3. Record 버튼 클릭
4. 스텝 추가/삭제 등 액션 수행
5. Stop 후 flame chart 분석

### Content Script 성능
Performance 탭 사용:
1. 웹 페이지 DevTools 열기
2. Performance 탭
3. Record 시작
4. 녹화 중 여러 액션 수행
5. Stop 후 timeline 분석

## 코드 품질

### 코딩 스타일
- 함수형 컴포넌트 사용 (React)
- async/await 선호 (Promise 체인보다)
- 명확한 타입 정의 (any 지양)
- 단일 책임 원칙 (함수/컴포넌트)

### 파일 구조 원칙
- 컴포넌트는 `components/` (UI 전용)
- 비즈니스 로직은 `utils/` 또는 `hooks/`
- 타입은 `utils/types.ts`에 중앙 집중
- 각 파일은 한 가지 책임만

### Git 커밋 메시지
```
feat: 새로운 기능 추가
fix: 버그 수정
refactor: 코드 리팩토링
style: 스타일 변경
docs: 문서 수정
test: 테스트 추가/수정
chore: 빌드/설정 변경
```

## 배포

### Chrome Web Store 배포

1. **빌드 및 패키징**:
```bash
npm run build
npm run zip
```

2. **Chrome Web Store 업로드**:
- [Chrome Web Store Developer Dashboard](https://chrome.google.com/webstore/devconsole) 접속
- "새 항목" 클릭
- `.output/chrome-mv3.zip` 업로드
- 스크린샷, 설명 등 메타데이터 입력
- 검토 제출

3. **버전 업데이트**:
- `package.json`의 `version` 업데이트
- `wxt.config.ts`에서도 버전 확인
- 변경사항 문서화
- 새 ZIP 빌드 및 업로드

## 추가 리소스

### WXT 문서
- [WXT 공식 문서](https://wxt.dev/)
- [WXT API 레퍼런스](https://wxt.dev/api/)

### Chrome Extension 문서
- [Chrome Extensions API](https://developer.chrome.com/docs/extensions/)
- [Manifest V3 마이그레이션](https://developer.chrome.com/docs/extensions/mv3/intro/)

### React 문서
- [React 공식 문서](https://react.dev/)
- [React Hooks](https://react.dev/reference/react)

### Tailwind CSS
- [Tailwind CSS v4 문서](https://tailwindcss.com/docs)
- [Material Symbols](https://fonts.google.com/icons)
