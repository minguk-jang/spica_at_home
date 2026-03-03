# 구현된 기능 목록

> 현재까지 구현되고 완성된 모든 함수와 기능들을 정리한 문서입니다.

## 📦 selector-core.js
### 셀렉터 생성 엔진

웹 요소에서 다양한 형식의 셀렉터를 생성합니다.

#### 헬퍼 함수

**`escapeAttrValue(str)`**
- 용도: CSS 속성 선택자의 속성값을 올바르게 이스케이프
- 입력: 문자열
- 출력: 이스케이프된 문자열
- 버그 수정: CSS.escape()는 식별자용이므로, 속성값용으로 백슬래시와 큰따옴표 이스케이프

**`escapeXPathText(text)`**
- 용도: XPath 문자열 표현에서 따옴표 처리
- 입력: 텍스트
- 출력: XPath용 문자열 (따옴표로 감싸거나 concat 함수 사용)
- 버그 수정: XPath 1.0에서 따옴표 혼합 처리

**`getNthOfType(element)`**
- 용도: 요소의 동일 태그 형제 중 위치 계산
- 입력: DOM 요소
- 출력: `div:nth-of-type(3)` 형식의 셀렉터 또는 빈 문자열
- 버그 수정: nth-child가 아닌 nth-of-type 올바르게 사용

**`buildFullCssPath(element)`**
- 용도: 요소의 전체 CSS 경로 생성
- 입력: DOM 요소
- 출력: `#app > div > button:nth-of-type(2)` 형식의 절대 경로
- 동작:
  - ID를 만나면 거기서 중단
  - 형제 요소가 여러 개면 nth-of-type 추가
  - 루트까지 역추적

**`buildXPath(element)`**
- 용도: 요소의 XPath 표현 생성
- 입력: DOM 요소
- 출력: `//button[@id="login"]` 또는 `/html/body/...` 형식
- 버그 수정:
  - ID 앵커가 있으면 `//` 사용
  - 없으면 절대 경로 `/html/body/...` 사용
- 동작: XPath 1.0 호환성

#### 셀렉터 생성 함수

**생성되는 셀렉터 타입들:**

1. **ID 셀렉터** - `#element-id`
   - 존재하면 가장 먼저 반환

2. **클래스 셀렉터** - `.class1.class2`
   - 모든 클래스를 조합하여 생성

3. **태그 셀렉터** - `button`, `div`
   - 요소의 태그명

4. **속성 셀렉터** - `[data-testid="value"]`
   - 중요 속성들을 선택:
     - 테스트용: data-testid, data-id, data-cy, data-test
     - 접근성: aria-label, aria-labelledby, role
     - 기본: name, type, placeholder, value
     - 링크/미디어: href, src, alt, title, for

5. **nth-of-type** - `div:nth-of-type(3)`
   - 동일 태그 형제 중 위치

6. **Full Path** - `#app > div > button:nth-of-type(2)`
   - ID 또는 루트까지의 절대 경로

7. **XPath** - `//button[@id="login"]`
   - ID 기반 또는 절대 경로 기반

8. **Text XPath** - `//button[contains(text(),'로그인')]`
   - 텍스트 내용 기반 (공백 정규화)

#### 검증 함수

**`validateSelector(selector, type)`**
- 용도: 생성된 셀렉터 검증
- 입력: 셀렉터 문자열, 타입 (css/xpath)
- 출력: `{valid: boolean, message: string}`
- 동작:
  - CSS 셀렉터 문법 검사
  - XPath 문법 검사
  - 실제 요소 선택 가능 여부 확인

---

## 📄 content.js
### 컨텐츠 스크립트 - 웹페이지에서 클릭 감지

웹페이지에 주입되어 클릭 이벤트를 감지하고 셀렉터를 수집합니다.

#### 상태 관리

- `collecting` - 수집 활성 여부
- `testClickInProgress` - Test 버튼의 programmatic click 진행 중 여부 ✨ NEW
- `lastHighlighted` - 마지막으로 하이라이트된 요소
- `statusBar` - 상태 표시 바
- `styleElement` - 주입된 스타일 요소

#### UI 헬퍼 함수

**`injectStyles()`**
- 용도: CSS 스타일 주입
- 스타일:
  - 상태 바: 상단 3px 그래디언트 애니메이션
  - 하이라이트: 파란색 outline (3px)

**`removeStyles()`**
- 용도: 주입된 스타일 제거

**`createStatusBar()`**
- 용도: 수집 활성 상태를 표시하는 상단 바 생성
- 표시: 파란색~초록색 그래디언트 애니메이션

**`removeStatusBar()`**
- 용도: 상태 바 제거

**`clearHighlight()`**
- 용도: 마지막 하이라이트 제거

#### 이벤트 핸들러

**`handleClick(e)`**
- 용도: 웹페이지 클릭 이벤트 처리
- 동작:
  1. 수집 모드 확인
  2. Test 버튼의 programmatic click 감지 시 무시 ✨ NEW
  3. 자신의 UI 클릭 무시
  4. 클릭된 요소에 하이라이트 적용
  5. `selector-core.js`를 사용해 모든 셀렉터 생성
  6. 결과를 Background로 전송

**`handleMessage(message, sender, sendResponse)`**
- 용도: Background와의 메시지 처리
- 메시지 타입:
  - `START_COLLECTING` - 수집 시작
  - `STOP_COLLECTING` - 수집 중지
  - `PING` - 스크립트 존재 확인
  - `VALIDATE_SELECTOR` - 선택자 검증
  - `TEST_CLICK_SELECTOR` - 선택자로 요소를 찾아 실제 클릭 실행 ✨ NEW

#### 수집 제어

**`startCollecting()`**
- 스타일 주입
- 상태 바 생성
- 클릭 이벤트 리스너 등록
- 마우스 무브 리스너 등록 (호버 표시)

**`stopCollecting()`**
- 스타일 제거
- 상태 바 제거
- 이벤트 리스너 제거
- 하이라이트 제거

#### 선택자 검증

**`validateSelector(selector, type)`**
- 용도: 셀렉터가 실제로 요소를 선택할 수 있는지 확인
- CSS 셀렉터: `document.querySelector()` 테스트
- XPath: `document.evaluate()` 테스트
- 반환: 유효한 요소 수

---

## 🖥️ background.js
### Service Worker - 확장 프로그램 백그라운드 프로세스

탭 관리, 메시지 라우팅, 상태 관리를 담당합니다.

#### 상태 관리

**`getCollectingTabId()`**
- 용도: 현재 수집 중인 탭 ID 조회
- 출력: `tabId` 또는 `null`
- 저장 위치: `chrome.storage.local`

**`setCollectingTabId(tabId)`**
- 용도: 수집 중인 탭 ID 설정
- 입력: `tabId` 또는 `null` (초기화)

**`getLastTabId()`** ✨ NEW
- 용도: 마지막으로 수집했던 탭 ID 조회
- 출력: `tabId` 또는 `null`
- 저장 위치: `chrome.storage.local`
- 용도: Test 버튼이 수집 중지 후에도 마지막 탭에서 테스트 가능하도록 함

**`setLastTabId(tabId)`** ✨ NEW
- 용도: 마지막 수집 탭 ID 설정
- 입력: `tabId` 또는 `null` (초기화)

#### 콘텐츠 스크립트 관리

**`ensureContentScript(tabId)`**
- 용도: 탭에 콘텐츠 스크립트가 주입되어 있는지 확인
- 동작:
  1. PING 메시지 전송 시도
  2. 응답 없으면 `selector-core.js`와 `content.js` 주입
- 상황: 동적 탭 이동이나 새로 열린 탭에서 필요

#### 메시지 처리

**`chrome.runtime.onMessage.addListener()`**

수신 메시지 타입:

1. **`START_COLLECTING`** (사이드패널에서)
   - 현재 활성 탭에서 수집 시작
   - 이전 탭 수집 중지
   - 콘텐츠 스크립트 주입
   - 수집 탭 ID 저장

2. **`STOP_COLLECTING`** (사이드패널에서)
   - 현재 수집 중인 탭에 중지 신호 전송
   - 수집 탭 ID 초기화

3. **`GET_COLLECTING_STATE`** (사이드패널에서)
   - 현재 수집 상태 반환
   - 탭 유효성 확인
   - 응답: `{collecting: boolean, tabId?: number}`

4. **`VALIDATE_SELECTOR`** (사이드패널에서)
   - 메시지를 수집 중인 탭으로 포워딩
   - 선택자 검증 결과 반환

5. **`TEST_CLICK_SELECTOR`** (사이드패널에서) ✨ NEW
   - 현재 수집 중인 탭 또는 마지막 수집 탭에서 선택자로 요소를 찾아 `.click()` 실행
   - 수집 중지 후에도 마지막 탭 ID로 테스트 가능
   - 응답: `{success: true}` 또는 `{success: false, error: string}`
   - 오렌지 아웃라인 시각 피드백 제공

6. **`SELECTORS_COLLECTED`** (콘텐츠 스크립트에서)
   - 사이드패널로 포워딩
   - 히스토리 업데이트용

#### 탭 이벤트

**`chrome.tabs.onRemoved.addListener()`**
- 용도: 탭 종료 감지
- 동작:
  - 수집 중인 탭이 종료되면 상태 초기화
  - 마지막 수집 탭이 종료되면 `lastTabId` 정리 ✨ NEW
  - 사이드패널에 상태 변화 알림

**`chrome.tabs.onActivated.addListener()`**
- 용도: 탭 전환 감지
- 동작: 사이드패널에 활성 탭 정보 알림

#### UI 업데이트

**`notifySidePanel(type, data)`**
- 용도: 사이드패널에 상태 변화 알림
- 메시지 타입:
  - `COLLECTING_STATE_CHANGED`
  - `TAB_SWITCHED`
  - `STOPPED_BY_TAB_CLOSE`

---

## 🎛️ sidepanel.js
### 사이드패널 UI 및 상호작용

사용자 인터페이스 제어, 히스토리 관리, 파일 내보내기를 담당합니다.

#### 상태 관리

- `collecting` - 수집 활성 여부
- `history` - 수집 히스토리 배열
- `lastProcessedTimestamp` - 마지막 처리 시간 (중복 방지)

#### 테마 관리 ✨ NEW

**`initTheme()`**
- 용도: 페이지 로드 시 테마 초기화
- 동작:
  1. localStorage에서 'sc-theme' 키로 저장된 테마 불러오기
  2. 값이 없으면 기본값 'dark' 사용
  3. `data-theme` 속성을 HTML 요소에 설정
- 실행 시점: DOMContentLoaded 이전

**테마 토글 이벤트 핸들러**
- 용도: 사용자가 테마 전환 버튼 클릭 시 처리
- 동작:
  1. `theme-transitioning` 클래스 추가 (부드러운 전환 애니메이션)
  2. 현재 테마 확인 (dark ↔ light)
  3. `data-theme` 속성 변경
  4. localStorage에 새 테마 저장
  5. 350ms 후 `theme-transitioning` 클래스 제거
- CSS 연동: `[data-theme="dark"]`, `[data-theme="light"]` 선택자로 자동 스타일 적용

#### DOM 요소 참조

**제어 요소**
- `toggleBtn` - 수집 시작/중지
- `savBtn` - JSON 저장
- `dirBtn` - 디렉토리 설정
- `exportBtn` - 내보내기

**상태 표시**
- `statusDot` - 활성 상태 점
- `statusText` - 상태 텍스트
- `footerStatus` - 하단 상태

**표시 영역**
- `elementCard` - 요소 정보 카드
- `selectorsGrid` - 셀렉터 그리드
- `historyPanel` - 히스토리 패널
- `historyList` - 히스토리 목록

#### 초기화

**`DOMContentLoaded` 이벤트**
1. 저장된 히스토리 로드
2. 디렉토리 핸들 복원
3. 수집 상태 확인 (Background 쿼리)

#### UI 업데이트

**`setCollectingUI(active)`**
- 용도: 수집 상태에 따라 UI 업데이트
- 변경사항:
  - 버튼 텍스트: "Start Collecting" ↔ "Stop Collecting"
  - 상태 점: 활성/비활성
  - 상태 텍스트: "수집 중..." ↔ "대기 중"

**`displayElementInfo(info)`**
- 용도: 클릭된 요소 정보 표시
- 표시 항목:
  - 태그명: `<button>`
  - ID: `#button-id`
  - 클래스: `.class1.class2`
  - URL: 현재 페이지 URL

**`displaySelectors(selectors, validation)`**
- 용도: 생성된 셀렉터들을 그리드에 표시
- 각 셀렉터마다:
  - 타입 뱃지
  - 셀렉터 문자열 (클릭하여 복사)
  - 유효성 표시 (✓/✗ 아이콘, 클릭하여 토글) ✨ NEW
  - Test 버튼 (셀렉터로 요소를 찾아 클릭) ✨ NEW

**`displayHistory()`**
- 용도: 히스토리 목록 업데이트
- 표시: 최신 순서로 아이템 나열

#### 데이터 관리

**`loadHistoryFromStorage()`**
- 용도: IndexedDB에서 히스토리 로드
- 저장 키: `selectorHistory`

**`saveHistoryToStorage()`**
- 용도: 히스토리를 IndexedDB에 저장
- 제한: 최대 20개 항목 유지

**`addToHistory(item)`**
- 용도: 새로운 수집 항목 히스토리에 추가
- 동작:
  - 중복 방지 (타임스탬프 확인)
  - 최대 20개 유지
  - 즉시 저장

**`clearHistory()`**
- 용도: 히스토리 전체 삭제
- 확인: 사용자 확인 후 실행

#### 파일 내보내기

**`exportHistory()`**
- 용도: 수집된 데이터를 JSON으로 내보내기
- 동작:
  1. 파일명 생성: `selectors_YYYYMMDD_HHMMSS.json`
  2. 파일 시스템 API 사용 (fs-storage.js)
  3. 성공/실패 알림

**`updateSaveButton()`**
- 용도: 저장 버튼 활성화/비활성화
- 조건: 히스토리 존재 && 디렉토리 설정됨

#### 이벤트 리스너

**`toggleBtn` 클릭**
- 수집 시작/중지 신호를 Background로 전송

**`savBtn` 클릭**
- 현재 요소의 셀렉터 저장 (히스토리에 추가)

**`dirBtn` 클릭**
- `fs-storage.js`의 `selectDirectory()` 호출
- 사용자가 디렉토리 선택

**`exportBtn` 클릭**
- `exportHistory()` 실행

**`clearHistoryBtn` 클릭**
- `clearHistory()` 실행

#### 유효성 아이콘 토글 ✨ NEW

**아이콘 클릭 동작**
- 용도: 사용자가 Test 결과를 바탕으로 수동으로 검증 상태 변경
- 동작:
  1. ✓ 클릭 → ✗로 토글
  2. ✗ 클릭 → ✓로 토글
  3. 클래스 변경 (`valid` ↔ `invalid`)
- 스타일: hover 시 아이콘 확대 (scale 1.25)
- 커서: pointer로 변경하여 클릭 가능 표시

#### Test 버튼 이벤트 핸들러 ✨ NEW

**`selectorsGrid` 클릭 이벤트**
- 용도: Test 버튼 클릭 처리
- 동작:
  1. 버튼 텍스트 변경: "Test" → "..." (로딩)
  2. 버튼 비활성화
  3. `chrome.runtime.sendMessage()` → Background → Content Script
  4. 요소 찾기 및 `.click()` 실행
  5. 응답에 따라 상태 표시:
     - 성공: "OK!" + 녹색 배경 (test-success 클래스)
     - 실패: "Fail" + 빨간색 배경 (test-fail 클래스)
     - 오류: "Err" + 빨간색 배경
  6. 1.5초 후 "Test"로 복원
- 안전성:
  - `testBtn.isConnected` 확인 (DOM에서 제거된 경우 처리)
  - `try-catch`로 예외 처리

#### 메시지 처리

**`chrome.runtime.onMessage.addListener()`**

수신 메시지:

1. **`SELECTORS_COLLECTED`**
   - 콘텐츠 스크립트에서 받은 수집 데이터
   - 히스토리에 추가
   - UI에 표시

2. **`COLLECTING_STATE_CHANGED`**
   - 수집 상태 변화 알림
   - UI 업데이트

3. **`TAB_SWITCHED`**
   - 탭 전환 감지
   - 필요하면 상태 확인

#### 유효성 검증

**`validateSelectorsRealTime()`**
- 용도: 각 셀렉터의 유효성 실시간 확인
- 동작:
  1. 현재 활성 탭의 콘텐츠 스크립트로 검증 요청
  2. 결과 표시 (✓/✗)

#### 저장 Modal ✨ NEW

**Modal DOM 요소**
- `saveModal` - Modal overlay
- `saveNameInput` - 이름 입력 필드
- `summaryTotal` - 총 entry 수 표시
- `summaryUrls` - URL 목록 표시
- `summaryTags` - 태그 분포 표시

**`openSaveModal()`**
- 용도: 저장 Modal 열기 및 요약 정보 표시
- 동작:
  1. Modal 표시 (display: flex)
  2. 입력 필드 초기화 및 포커스
  3. calculateSummary() 호출하여 요약 정보 계산
  4. 요약 정보 렌더링 (총 entry 수, URL 목록, 태그 분포)

**`closeSaveModal()`**
- 용도: Modal 닫기
- 동작: Modal 숨기기 (display: none)

**`calculateSummary(historyData)`**
- 용도: 히스토리 데이터에서 요약 정보 계산
- 입력: history 배열
- 반환: `{ totalEntries, urls, tagCounts }`
- 동작:
  1. URL 중복 제거 (Set 사용)
  2. 태그 빈도 계산
  3. 총 entry 수 계산

**파일명 검증**
- 실시간 입력 검증: `/^[a-zA-Z0-9-]*$/` 정규식
- 허용 문자: 영문, 숫자, 하이픈(-)만
- 한글 및 특수문자 입력 시 즉시 제거
- 유효하지 않은 입력 시 `invalid` 클래스 추가

**`confirmSaveBtn` 이벤트 핸들러**
- 용도: Modal에서 저장 확정
- 동작:
  1. 입력된 이름 가져오기 및 검증
  2. 파일명 생성: `selectors-{name}-{timestamp}.json`
  3. 이름이 없으면: `selectors-{timestamp}.json`
  4. JSON 데이터에 `name` 필드 포함
  5. FsStorage.saveJson() 호출
  6. 성공 메시지 표시 및 Modal 닫기

**Modal 닫기 트리거**
- X 버튼 클릭
- 취소 버튼 클릭
- Escape 키
- Overlay 클릭
- Enter 키 (저장 실행)

---

## 🔧 lib/idb-helper.js
### IndexedDB 데이터베이스 래퍼

확장 프로그램의 데이터 저장소로 사용됩니다.

#### 설정

- **DB 이름**: `SelectorCollectorDB`
- **DB 버전**: `1`
- **스토어 이름**: `keyval`

#### 함수

**`openDB()`**
- 용도: IndexedDB 연결 열기
- 반환: Promise<IDBDatabase>
- 동작:
  - DB가 없으면 자동 생성
  - 스토어가 없으면 자동 생성

**`get(key)`**
- 용도: 데이터 조회
- 입력: 키 (문자열)
- 출력: Promise<any>
- 예: `await IdbHelper.get('selectorHistory')`

**`set(key, value)`**
- 용도: 데이터 저장
- 입력: 키, 값
- 출력: Promise<void>
- 예: `await IdbHelper.set('selectorHistory', data)`

**`del(key)`**
- 용도: 데이터 삭제
- 입력: 키
- 출력: Promise<void>
- 예: `await IdbHelper.del('selectorHistory')`

#### 사용 사례

1. **히스토리 저장**
   ```javascript
   await IdbHelper.set('selectorHistory', historyArray);
   ```

2. **디렉토리 핸들 저장**
   ```javascript
   await IdbHelper.set('directoryHandle', dirHandle);
   ```

3. **사용자 설정 저장**
   ```javascript
   await IdbHelper.set('userPreferences', {maxHistory: 20});
   ```

---

## 💾 lib/fs-storage.js
### File System Access API 래퍼

파일 시스템에 데이터를 저장합니다.

#### 상태

- `dirHandle` - 선택된 디렉토리의 FileSystemDirectoryHandle

#### 함수

**`selectDirectory()`**
- 용도: 사용자에게 디렉토리 선택 다이얼로그 표시
- 반환: Promise<boolean>
- 동작:
  1. 파일 선택 다이얼로그 표시
  2. 선택된 디렉토리 핸들 저장
  3. IndexedDB에도 저장
  4. true/false 반환
- 예외: AbortError (사용자 취소) - false 반환

**`ensurePermission()`**
- 용도: 디렉토리 접근 권한 확인/요청
- 반환: Promise<boolean>
- 동작:
  1. 핸들이 없으면 false
  2. 권한 확인 (`queryPermission`)
  3. 없으면 요청 (`requestPermission`)
  4. 결과 반환

**`saveJson(filename, data)`**
- 용도: JSON 데이터를 파일로 저장
- 입력: 파일명, 데이터 객체
- 반환: Promise<void>
- 동작:
  1. 권한 확인
  2. 파일 생성/오버라이트
  3. JSON 형식으로 저장 (들여쓰기 2칸)
- 예외: "디렉토리 접근 권한이 없습니다"

**`restoreHandle()`**
- 용도: IndexedDB에서 저장된 디렉토리 핸들 복원
- 반환: Promise<boolean>
- 동작: IndexedDB에서 핸들 로드, 성공 여부 반환

**`isReady()`**
- 용도: 디렉토리 핸들이 준비되었는지 확인
- 반환: boolean
- 예: `if (FsStorage.isReady()) { ... }`

**`listJsonFiles()`** ✨ 대시보드용
- 용도: 설정된 디렉토리에서 `selectors-*.json` 파일 목록 가져오기
- 반환: Promise<string[]>
- 동작:
  1. 권한 확인
  2. dirHandle.values()로 파일 순회
  3. selectors-로 시작하고 .json으로 끝나는 파일만 필터
  4. 최신 파일부터 정렬 (역순)
- 예외: "Directory access permission not granted"

**`readJson(filename)`** ✨ 대시보드용
- 용도: JSON 파일 읽기 및 메타데이터 반환
- 입력: 파일명 (예: "selectors-2026-02-08.json")
- 반환: Promise<{filename, data, lastModified, size}>
- 동작:
  1. 권한 확인
  2. getFileHandle()로 파일 핸들 가져오기
  3. file.text()로 내용 읽기
  4. JSON.parse()로 파싱
  5. 메타데이터와 함께 반환
- 예외: 파일이 없거나 JSON 파싱 실패 시 에러

**`deleteFile(filename)`** ✨ 대시보드용
- 용도: JSON 파일 삭제
- 입력: 파일명
- 반환: Promise<void>
- 동작:
  1. 권한 확인
  2. dirHandle.removeEntry()로 파일 삭제
- 예외: "Directory access permission not granted"

**`getDirHandle()`** ✨ 대시보드용
- 용도: 현재 디렉토리 핸들 반환
- 반환: Promise<FileSystemDirectoryHandle | null>
- 동작:
  1. dirHandle이 없으면 restoreHandle() 호출
  2. 핸들 반환

**`renameFile(oldName, newName, newInternalName)`** ✨ NEW
- 용도: JSON 파일 이름 변경 (파일 시스템에는 rename API가 없으므로 읽기→저장→삭제 방식)
- 입력:
  - `oldName`: 기존 파일명
  - `newName`: 새 파일명
  - `newInternalName`: JSON 내부 `name` 필드 값 (optional)
- 반환: Promise<boolean>
- 동작:
  1. 권한 확인
  2. 기존 파일 읽기 (getFileHandle → getFile → text → JSON.parse)
  3. JSON 내부 `name` 필드 업데이트 (newInternalName 제공 시)
  4. 새 파일명으로 저장 (saveJson)
  5. 기존 파일 삭제 (deleteFile)
  6. true 반환
- 예외:
  - 파일 읽기 실패
  - 저장 실패
  - 삭제 실패
- 주의: 트랜잭션이 아니므로 중간에 실패하면 두 파일이 모두 존재할 수 있음

#### 사용 사례

1. **디렉토리 선택**
   ```javascript
   const success = await FsStorage.selectDirectory();
   if (success) {
     // 디렉토리 선택됨
   }
   ```

2. **데이터 저장**
   ```javascript
   await FsStorage.saveJson('selectors.json', historyData);
   ```

3. **권한 확인**
   ```javascript
   const canWrite = await FsStorage.ensurePermission();
   ```

---

## 📊 dashboard.js
### 대시보드 - JSON 파일 관리 및 편집

저장된 JSON 파일을 불러와서 편집, 삭제, 파일 간 이동하는 대시보드 UI를 제공합니다.

#### 테마 관리 ✨ NEW

**`initTheme()`**
- 용도: 페이지 로드 시 테마 초기화
- 동작: sidepanel.js와 동일한 로직 (localStorage에서 'sc-theme' 불러오기)
- 사이드패널과 테마 설정 동기화

**테마 토글 이벤트 핸들러**
- 용도: 대시보드에서도 테마 전환 가능
- 동작: sidepanel.js와 동일 (dark ↔ light, localStorage 저장)
- 사이드패널과 동일한 디자인 시스템 공유

#### 상태 관리

- `currentFile` - 현재 편집 중인 파일명
- `currentData` - 현재 편집 중인 entry 배열
- `moveData` - 이동 모드의 좌/우 패널 데이터
  - `{ left: { file, data }, right: { file, data } }`
- `draggedItem` - 드래그 중인 항목 정보

#### 뷰 모드

**메인 뷰 (Main View)**
- 파일 카드 그리드로 JSON 파일 목록 표시
- 각 카드: 파일명, entry 수, 파일 크기, 수정 시간
- 액션: Open, Delete

**상세 뷰 (Detail View)**
- 단일 파일의 모든 entry 표시
- entry별 편집 가능:
  - 셀렉터 값 인라인 수정
  - elementInfo 정보 표시
  - validation 상태 표시 (✅❌❓)
  - entry 삭제, 순서 변경
- Save 버튼으로 파일 저장

**이동 뷰 (Move View)**
- 좌/우 패널에 두 JSON 파일 표시
- 드래그 앤 드롭으로 entry 이동
- Save Both 버튼으로 양쪽 파일 저장

#### 주요 함수

**`init()`**
- 용도: 초기화
- 동작:
  1. FsStorage 준비 확인
  2. 핸들 복원 시도
  3. 파일 목록 로드 또는 Empty State 표시

**`loadFiles()`**
- 용도: JSON 파일 목록 로드 및 표시
- 동작:
  1. FsStorage.listJsonFiles() 호출
  2. 각 파일에 대해 createFileCard() 생성
  3. 파일 셀렉트 드롭다운 업데이트

**`createFileCard(filename)`**
- 용도: 파일 카드 DOM 요소 생성
- 입력: 파일명
- 반환: HTMLElement
- 동작:
  1. FsStorage.readJson()로 메타데이터 읽기
  2. entry 수, 파일 크기, 날짜 표시
  3. Open/Delete 버튼 이벤트 바인딩

**`showDetailView(filename)`**
- 용도: 상세 편집 뷰로 전환
- 동작:
  1. 뷰 전환
  2. loadFileDetail() 호출

**`loadFileDetail(filename)`**
- 용도: 파일 내용 로드 및 entry 렌더링
- 동작:
  1. FsStorage.readJson() 호출
  2. entries 배열 추출
  3. renderEntries() 호출

**`renderEntries(data)`**
- 용도: entry 목록 렌더링
- 동작:
  1. 각 entry에 대해 createEntryElement() 호출
  2. DOM에 추가

**`createEntryElement(entry, index)`**
- 용도: 단일 entry DOM 요소 생성
- 반환: HTMLElement
- 동작:
  1. elementInfo 표시 (tag, text, URL)
  2. selectors 인라인 편집 필드 생성
  3. validation 상태 아이콘 표시
  4. Remove 버튼 이벤트 바인딩
  5. input change 이벤트로 currentData 업데이트

**`renderSelectors(selectors, entryIndex)`**
- 용도: 셀렉터 목록 HTML 생성
- 반환: string (HTML)
- 동작:
  1. selectors 객체 순회
  2. 각 셀렉터마다 key, input, validation icon 생성
  3. validation 데이터와 결합하여 ✅❌❓ 표시

**드래그 앤 드롭 함수**

**`showMoveView()`**
- 용도: 이동 모드로 전환

**`loadMoveFile(side, filename)`**
- 용도: 좌/우 패널에 파일 로드
- 입력: 'left' | 'right', 파일명
- 동작:
  1. FsStorage.readJson() 호출
  2. moveData[side] 업데이트
  3. renderMoveList(side) 호출

**`renderMoveList(side)`**
- 용도: 패널에 entry 목록 렌더링
- 동작:
  1. entry마다 draggable div 생성
  2. dragstart 이벤트 바인딩
  3. drop zone 이벤트 설정

**`handleDragStart(e)`**
- 용도: 드래그 시작 처리
- 동작:
  1. draggedItem에 side, index 저장
  2. dragging 클래스 추가

**`handleDragOver(e)`**
- 용도: 드롭 존 하이라이트
- 동작: drag-over 클래스 추가

**`handleDrop(e, targetSide)`**
- 용도: 드롭 처리 및 entry 이동
- 동작:
  1. 같은 패널이면 무시
  2. 원본에서 splice로 제거
  3. 대상에 push
  4. 양쪽 패널 재렌더링

**저장 함수**

**`saveBtn.addEventListener('click')`**
- 용도: 상세 뷰에서 수정사항 저장
- 동작:
  1. exportData 객체 생성 (exportedAt, totalEntries, entries)
  2. FsStorage.saveJson() 호출
  3. 성공 알림

**`moveSaveBtn.addEventListener('click')`**
- 용도: 이동 뷰에서 양쪽 파일 저장
- 동작:
  1. left 파일 저장
  2. right 파일 저장
  3. 성공 알림

#### 파일명 Rename 기능 ✨ NEW

**UI 요소**
- `renameFileBtn` - Rename 버튼 (연필 아이콘)
- `renameContainer` - Rename 입력 UI (숨김 상태)
- `renameInput` - 새 이름 입력 필드
- `confirmRenameBtn` - 확인 버튼
- `cancelRenameBtn` - 취소 버튼

**`renameFileBtn` 클릭**
- 용도: Rename UI 표시 및 초기화
- 동작:
  1. 파일명 표시 숨기고 Rename UI 표시
  2. 현재 파일명에서 name 부분 추출
  3. 정규식: `/^selectors-(.*)-(\d{4}-\d{2}-\d{2}T.*)\.json$/`
  4. 추출된 name을 input에 설정
  5. input에 포커스

**`confirmRenameBtn` 클릭**
- 용도: Rename 실행
- 동작:
  1. 입력값 가져오기 및 trim
  2. 빈 값 검증
  3. 파일명 규칙 검증 (`/^[a-zA-Z0-9-]+$/`)
  4. 기존 파일명에서 timestamp 부분 추출
  5. 새 파일명 생성: `selectors-{newName}-{timestamp}.json`
  6. FsStorage.renameFile() 호출
  7. 성공 시 currentFile 업데이트 및 UI 초기화
  8. 파일 목록 새로고침

**`cancelRenameBtn` 클릭**
- 용도: Rename 취소
- 동작: resetRenameUI() 호출

**`resetRenameUI()`**
- 용도: Rename UI 숨기고 원래 상태로 복원
- 동작:
  1. renameContainer 숨김
  2. renameFileBtn 및 currentFilenameEl 표시

#### Entry 정보 편집 ✨ NEW

**편집 가능한 필드**
- `Tag` (elementInfo.tagName)
- `Text` (elementInfo.textContent)
- `URL` (elementInfo.url)

**구현 방식**
- 기존 `<span class="info-value">` → `<input class="info-input">`으로 변경
- 각 input에 `data-field`, `data-entry-index` 속성 추가
- `change` 이벤트 리스너로 currentData 업데이트

**이벤트 핸들러**
```javascript
infoInputs.forEach(input => {
  input.addEventListener('change', (e) => {
    const field = e.target.dataset.field;
    const value = e.target.value;
    currentData[index].elementInfo[field] = value;
  });
});
```

**저장 시 보존**
- Save 버튼 클릭 시 currentData를 그대로 저장
- elementInfo 필드의 변경사항이 자동 포함됨

#### 파일 카드에 name 표시 ✨ NEW

**`createFileCard(filename)`** 업데이트
- JSON 파일 읽기 시 `data.name` 필드 확인
- `name` 필드가 있으면:
  - 표시: `{name} ({filename})`
  - 예: `login-page (selectors-login-page-2026-02-08T11-28-00.json)`
- `name` 필드가 없으면:
  - 기존처럼 파일명만 표시

**저장 시 name 필드 보존**
- `loadFileDetail()`에서 `currentData.name = name` 설정
- Save 버튼 클릭 시:
  ```javascript
  const exportData = {
    name: currentData.name || null,
    exportedAt: new Date().toISOString(),
    totalEntries: currentData.length,
    entries: currentData
  };
  ```

#### 사용 예시

```javascript
// 파일 목록 로드
await loadFiles();

// 파일 읽기
const result = await FsStorage.readJson('selectors-2026-02-08.json');
currentData = result.data.entries;

// 셀렉터 수정
currentData[0].selectors['id'] = '#new-id';

// 저장
await FsStorage.saveJson(currentFile, {
  exportedAt: new Date().toISOString(),
  totalEntries: currentData.length,
  entries: currentData
});
```

---

## 📊 구현 현황 요약

| 모듈 | 상태 | 구현 함수 개수 | 최근 업데이트 |
|------|------|---|---|
| selector-core.js | ✅ 완성 | 8+ | - |
| content.js | ✅ 완성 | 11+ | ✨ TEST_CLICK_SELECTOR + testClickInProgress 플래그 |
| background.js | ✅ 완성 | 8+ | ✨ getLastTabId/setLastTabId + TEST_CLICK_SELECTOR 라우팅 |
| sidepanel.js | ✅ 완성 | 19+ | ✨ Test 버튼 + 유효성 아이콘 토글 + Modal + 테마 |
| sidepanel.css | ✅ 완성 | - | ✨ .test-btn + .validation-icon:hover + 테마 |
| dashboard.js | ✅ 완성 | 22+ | ✨ Rename + Entry 편집 + 테마 |
| dashboard.css | ✅ 완성 | - | ✨ 테마 |
| lib/idb-helper.js | ✅ 완성 | 4 | - |
| lib/fs-storage.js | ✅ 완성 | 10 | ✨ renameFile() |

**총 함수/기능: 75+ 개 구현 완료**

### 최근 추가된 기능 (2026-02-08)

#### Test 버튼 및 유효성 토글 (sidepanel.js & content.js) ✨ LATEST
- ✅ Copy 버튼 → Test 버튼으로 교체
- ✅ Test 버튼: 셀렉터로 요소를 찾아 실제 `.click()` 실행
- ✅ 수집 중지 후에도 `lastTabId`로 테스트 가능
- ✅ 오렌지 아웃라인 시각 피드백
- ✅ 로딩/성공/실패 상태 표시 (색상 피드백)
- ✅ 유효성 아이콘(✓/✗) 클릭 토글
- ✅ icon hover 시 scale 애니메이션
- ✅ `testClickInProgress` 플래그로 `handleClick` 간섭 방지
- ✅ `return true` 추가하여 메시지 응답 채널 유지 ✨ BUG FIX

#### 저장 Modal (sidepanel.js)
- ✅ 이름 입력 및 실시간 검증 (영문/숫자/하이픈만)
- ✅ 요약 정보 표시 (총 entry 수, URL 목록, 태그 분포)
- ✅ 파일명 규칙: `selectors-{name}-{timestamp}.json`
- ✅ JSON 내부 `name` 필드 저장
- ✅ Modal UI/UX (Escape, Enter, Overlay 클릭)

#### 대시보드 편집 기능 (dashboard.js)
- ✅ 파일명 Rename (인라인 편집 UI)
- ✅ Entry 정보 편집 (Tag, Text, URL)
- ✅ 파일 카드에 name 표시 지원
- ✅ 저장 시 name 필드 보존

#### 파일 시스템 (fs-storage.js)
- ✅ renameFile() 함수 (읽기→저장→삭제 방식)

#### Test 버튼 기능 ✨ NEW (2026-02-08)

**기능**
- ✅ 각 셀렉터 옆의 Test 버튼으로 실제 요소 클릭 테스트
- ✅ Copy 버튼 → Test 버튼으로 교체 (이미 텍스트 박스 클릭으로 복사 가능)
- ✅ 수집 중지 후에도 마지막 탭에서 테스트 가능
- ✅ 오렌지색 아웃라인 시각 피드백
- ✅ 로딩(…) → 성공(OK!) / 실패(Fail) / 오류(Err) 상태 표시
- ✅ 색상 피드백: 성공 (녹색), 실패/오류 (빨간색)

**흐름**
1. 사이드패널 Test 클릭
2. `chrome.runtime.sendMessage()` (sidepanel → background)
3. `background.js` 메시지 라우팅 (collectingTabId 또는 lastTabId)
4. `content.js`에서 요소 찾기 (`document.querySelector` 또는 `document.evaluate`)
5. 요소 클릭 실행 (testClickInProgress 플래그로 `handleClick` 간섭 방지)
6. 시각 피드백 (오렌지 아웃라인 500ms)
7. 응답 반환 (sidepanel에서 UI 업데이트)

**구현 세부사항**
- content.js: `testClickInProgress` 플래그로 programmatic click 감지
- background.js: fallback logic (`collectingTabId || lastTabId`)
- sidepanel.js: 클릭 이벤트 위임, 상태별 UI 피드백
- sidepanel.css: `.test-btn`, `.test-success`, `.test-fail` 스타일

---

#### 유효성 아이콘 토글 기능 ✨ NEW (2026-02-08)

**기능**
- ✅ ✓/✗ 아이콘 클릭으로 검증 상태 수동 변경
- ✅ hover 시 아이콘 확대 (scale 1.25) 애니메이션
- ✅ 커서 변경 (pointer) - 클릭 가능 표시
- ✅ 즉시 UI 업데이트 (클래스 토글)

**동작**
- `validation-icon` 요소에 `click` 이벤트 리스너
- `valid` / `invalid` 클래스 토글
- 텍스트 변경: "✓" ↔ "✗"
- 아이콘 색상 자동 변경 (CSS)

---

#### 프로덕션 레벨 테마 시스템 ✨ NEW (2026-02-08)

**디자인 시스템**
- ✅ **다크 테마 (Void)**: 전문적인 어두운 색상 팔레트
  - 배경: #09090b, #111116, #19191f
  - 액센트: #2dd4bf (청록색)
  - 텍스트: #ececf0, #8585a0, #525268
- ✅ **라이트 테마 (Stone)**: 부드러운 밝은 색상 팔레트
  - 배경: #f5f3ee, #eae7e0, #ffffff
  - 액센트: #0d9488 (청록색 - 다크)
  - 텍스트: #1c1a16, #6b665e, #a09a91
- ✅ **Typography**: Outfit (UI) + JetBrains Mono (코드)
- ✅ **Signature Accent Bar**: 상단 2px 그래디언트 바
- ✅ **Custom Scrollbar**: 테마별 스크롤바 스타일
- ✅ **Smooth Transitions**: 0.3초 ease 전환 애니메이션

**구현 범위**
- ✅ sidepanel.html/css/js - 완전한 테마 시스템
- ✅ dashboard.html/css/js - 완전한 테마 시스템
- ✅ localStorage 동기화 (`sc-theme` 키)
- ✅ 테마 토글 버튼 (태양/달 아이콘)
- ✅ 모든 UI 컴포넌트 테마 대응

**사용자 경험**
- ✅ 원클릭 테마 전환
- ✅ 설정 영구 저장
- ✅ 사이드패널 ↔ 대시보드 간 테마 동기화
- ✅ 부드러운 색상 전환 애니메이션

