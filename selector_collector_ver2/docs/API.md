# API 문서

> 각 모듈의 공개 인터페이스(API)를 명시합니다.

## 🔍 selector-core.js API

### 개요
웹 요소에서 다양한 형식의 셀렉터를 생성하는 엔진입니다.

### 주요 공개 함수

```javascript
/**
 * 요소에 대한 모든 가능한 셀렉터 생성
 * @param {Element} element - 대상 요소
 * @returns {Object} { css: string[], xpath: string[] }
 */
const selectors = window.selectorCollector.generateSelectors(element);

/**
 * 셀렉터 검증 (CSS, XPath)
 * @param {string} selector - 검증할 셀렉터
 * @param {string} type - 'css' 또는 'xpath'
 * @returns {Object} { valid: boolean, message: string }
 */
const result = window.selectorCollector.validateSelector(selector, type);
```

### 생성되는 셀렉터 타입

| 타입 | 예시 | 장점 | 단점 |
|------|------|------|------|
| ID | `#login-btn` | 가장 유일성 높음 | ID 없으면 미생성 |
| Class | `.btn.primary` | 직관적 | 클래스 변경에 약함 |
| Attribute | `[data-testid="login"]` | 테스트에 용이 | 속성 없으면 미생성 |
| nth-of-type | `div:nth-of-type(2)` | 안정적 | DOM 변경에 약함 |
| Full Path | `#app > div > button` | 명확한 경로 | 경로 복잡할 수 있음 |
| XPath | `//button[@id="login"]` | 강력함 | 복잡함 |
| Text XPath | `//button[contains(text(),'로그인')]` | 텍스트 기반 | 다국어 미지원 |

---

## 📄 content.js API

### 개요
웹페이지에 주입되어 클릭 이벤트를 감지하고 셀렉터를 수집합니다.

### 공개 인터페이스

```javascript
/**
 * 수집 모드 활성화
 */
window.selectorCollector.start();

/**
 * 수집 모드 비활성화
 */
window.selectorCollector.stop();

/**
 * 수집 히스토리 조회
 * @returns {Array} 수집된 항목들
 */
const history = window.selectorCollector.getHistory();

/**
 * 수집 상태 확인
 * @returns {boolean}
 */
const isActive = window.selectorCollector.isActive();
```

### 메시지 인터페이스

Content Script가 수신하는 메시지:

```javascript
// Background에서
chrome.runtime.sendMessage({
  type: 'START_COLLECTING'  // 수집 시작
});

chrome.runtime.sendMessage({
  type: 'STOP_COLLECTING'   // 수집 중지
});

chrome.runtime.sendMessage({
  type: 'PING'              // 스크립트 존재 확인
});

chrome.runtime.sendMessage({
  type: 'VALIDATE_SELECTOR',
  selector: '#button',
  selectorType: 'css'       // 셀렉터 검증
});
```

### 보내는 메시지

```javascript
// Background로
chrome.runtime.sendMessage({
  type: 'SELECTORS_COLLECTED',
  data: {
    element: {
      tagName: 'button',
      id: 'submit',
      className: 'btn primary',
      url: 'https://example.com'
    },
    selectors: {
      css: ['#submit', '.btn.primary', 'button[type="submit"]'],
      xpath: ['//button[@id="submit"]', '//button[contains(text(),"Submit")]']
    },
    timestamp: 1707123456789
  }
});
```

---

## 🖥️ background.js API

### 개요
Service Worker로서 탭 관리, 메시지 라우팅, 상태 관리를 담당합니다.

### 메시지 프로토콜

#### Sidepanel → Background

```javascript
// 수집 시작
chrome.runtime.sendMessage({ type: 'START_COLLECTING' });

// 수집 중지
chrome.runtime.sendMessage({ type: 'STOP_COLLECTING' });

// 현재 상태 확인
chrome.runtime.sendMessage(
  { type: 'GET_COLLECTING_STATE' },
  (response) => {
    // response: { collecting: boolean, tabId?: number }
  }
);

// 셀렉터 검증 (선택적)
chrome.runtime.sendMessage(
  {
    type: 'VALIDATE_SELECTOR',
    selector: '#button',
    selectorType: 'css'
  },
  (response) => {
    // response: { valid: boolean, ... }
  }
);
```

#### Content Script → Background

```javascript
// 셀렉터 수집 완료 알림
chrome.runtime.sendMessage({
  type: 'SELECTORS_COLLECTED',
  data: { /* 수집 데이터 */ }
});
```

#### Background → Sidepanel (브로드캐스트)

```javascript
// 수집 상태 변경
chrome.runtime.sendMessage({
  type: 'COLLECTING_STATE_CHANGED',
  data: { collecting: true }
});

// 탭 전환
chrome.runtime.sendMessage({
  type: 'TAB_SWITCHED',
  data: { activeTabId: 123 }
});
```

---

## 🎛️ sidepanel.js API

### 개요
사용자 인터페이스, 히스토리 관리, 파일 내보내기를 담당합니다.

### 공개 함수

```javascript
/**
 * 수집 시작/중지 토글
 */
window.toggleCollecting();

/**
 * 현재 요소 저장
 */
window.saveElement();

/**
 * 디렉토리 선택
 */
window.selectDirectory();

/**
 * 히스토리 내보내기 (JSON)
 */
window.exportHistory();

/**
 * 히스토리 전체 삭제
 */
window.clearHistory();

/**
 * 히스토리 조회
 * @returns {Array} 수집된 항목들
 */
const items = window.getHistory();
```

### 메시지 수신

```javascript
// Background에서 받는 메시지
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'COLLECTING_STATE_CHANGED') {
    // { collecting: boolean }
  }
  if (message.type === 'SELECTORS_COLLECTED') {
    // { element, selectors, timestamp }
  }
  if (message.type === 'TAB_SWITCHED') {
    // { activeTabId }
  }
});
```

### 이벤트

```javascript
// 수집 버튼 클릭
toggleBtn.addEventListener('click', () => {
  // START/STOP 메시지 Background로 전송
});

// 저장 버튼 클릭
savBtn.addEventListener('click', () => {
  // 현재 요소를 히스토리에 추가
});

// 내보내기 버튼 클릭
exportBtn.addEventListener('click', () => {
  // 히스토리를 JSON으로 내보내기
});

// 디렉토리 선택 버튼 클릭
dirBtn.addEventListener('click', () => {
  // 파일 시스템 다이얼로그 열기
});
```

---

## 🔧 lib/idb-helper.js API

### 개요
IndexedDB 데이터베이스 접근을 추상화합니다.

### 함수

```javascript
/**
 * 값 조회
 * @param {string} key - 저장 키
 * @returns {Promise<any>} 저장된 값
 */
const value = await IdbHelper.get('selectorHistory');

/**
 * 값 저장
 * @param {string} key - 저장 키
 * @param {any} value - 저장할 값
 * @returns {Promise<void>}
 */
await IdbHelper.set('selectorHistory', arrayData);

/**
 * 값 삭제
 * @param {string} key - 삭제할 키
 * @returns {Promise<void>}
 */
await IdbHelper.del('selectorHistory');
```

### 사용 예시

```javascript
// 히스토리 저장
const history = [
  { tagName: 'button', selectors: {...}, timestamp: 1234567890 },
  // ...
];
await IdbHelper.set('selectorHistory', history);

// 히스토리 로드
const loaded = await IdbHelper.get('selectorHistory') || [];

// 디렉토리 핸들 저장
await IdbHelper.set('directoryHandle', dirHandle);

// 설정 저장
await IdbHelper.set('userSettings', { maxHistory: 20 });
```

### 스키마

**키들:**
- `selectorHistory` - Array<{tagName, id, className, selectors, timestamp}>
- `directoryHandle` - FileSystemDirectoryHandle
- `userSettings` - Object with user preferences

---

## 💾 lib/fs-storage.js API

### 개요
File System Access API를 래핑하여 파일 저장을 관리합니다.

### 함수

```javascript
/**
 * 사용자에게 디렉토리 선택 요청
 * @returns {Promise<boolean>} 성공 여부
 */
const success = await FsStorage.selectDirectory();

/**
 * 디렉토리 접근 권한 확인 및 요청
 * @returns {Promise<boolean>} 권한 있는지 여부
 */
const canWrite = await FsStorage.ensurePermission();

/**
 * JSON 데이터를 파일로 저장
 * @param {string} filename - 파일 이름
 * @param {Object} data - 저장할 데이터
 * @returns {Promise<void>}
 * @throws {Error} 권한 없을 시 예외
 */
await FsStorage.saveJson('selectors.json', data);

/**
 * 이전에 선택한 디렉토리 복원
 * @returns {Promise<boolean>} 복원 성공 여부
 */
const restored = await FsStorage.restoreHandle();

/**
 * 디렉토리 준비 상태 확인
 * @returns {boolean} 디렉토리 준비됨 여부
 */
const ready = FsStorage.isReady();

/**
 * JSON 파일 목록 가져오기 (대시보드용)
 * @returns {Promise<string[]>} selectors-*.json 파일명 배열 (최신순)
 * @throws {Error} 권한 없을 시 예외
 */
const files = await FsStorage.listJsonFiles();

/**
 * JSON 파일 읽기 (대시보드용)
 * @param {string} filename - 파일명
 * @returns {Promise<{filename, data, lastModified, size}>} 파일 데이터 및 메타데이터
 * @throws {Error} 파일이 없거나 JSON 파싱 실패 시
 */
const result = await FsStorage.readJson('selectors-2026-02-08.json');

/**
 * JSON 파일 삭제 (대시보드용)
 * @param {string} filename - 파일명
 * @returns {Promise<void>}
 * @throws {Error} 권한 없을 시 예외
 */
await FsStorage.deleteFile('old-file.json');

/**
 * 디렉토리 핸들 반환 (대시보드용)
 * @returns {Promise<FileSystemDirectoryHandle | null>}
 */
const handle = await FsStorage.getDirHandle();
```

### 사용 예시

```javascript
// 1. 디렉토리 선택 (처음 한 번)
if (await FsStorage.selectDirectory()) {
  console.log('디렉토리 선택됨');
}

// 2. 데이터 저장
const data = {
  timestamp: new Date().toISOString(),
  elements: [...],
  count: 42
};
await FsStorage.saveJson('collection_2024.json', data);

// 3. 앱 시작 시 핸들 복원
await FsStorage.restoreHandle();

// 4. 저장 가능 상태 확인
if (FsStorage.isReady()) {
  // 저장 버튼 활성화
}
```

### 권한 모델

```
처음 사용:
1. selectDirectory() 호출
   ↓
2. 사용자 다이얼로그에서 폴더 선택
   ↓
3. IndexedDB에 핸들 저장
   ↓
4. 이후 saveJson() 호출 가능

재시작 후:
1. restoreHandle() 호출
   ↓
2. IndexedDB에서 핸들 로드
   ↓
3. ensurePermission()으로 권한 확인
   ↓
4. 필요시 사용자에게 권한 재요청
```

---

## 🔄 메시지 흐름도

```
사용자 클릭
    ↓
[content.js] ──START_COLLECTING──→ [background.js]
                                        ↑
                                        │
[sidepanel.js] ──TOGGLE/START──→ [background.js]
                ←──STATE_CHANGED──

요소 클릭
    ↓
[content.js] SELECTORS_COLLECTED → [background.js] → [sidepanel.js]
    ↓
[selector-core.js] (셀렉터 생성)
```

---

## 📊 dashboard.js API

### 개요
저장된 JSON 파일을 관리, 편집, 이동하는 대시보드 페이지입니다.

### 뷰 모드

**Main View (메인 뷰)**
- JSON 파일 목록을 카드 형태로 표시
- 각 카드: 파일명, entry 수, 파일 크기, 수정 시간
- 액션: Open (상세 뷰로 이동), Delete (파일 삭제)

**Detail View (상세 편집 뷰)**
- 단일 파일의 모든 entry 표시
- entry별 셀렉터 인라인 편집 가능
- validation 상태 표시 (✅ 유효, ❌ 무효, ❓ 미검증)
- entry 삭제, 순서 변경
- Save 버튼으로 파일 저장

**Move View (이동 뷰)**
- 좌/우 패널에 두 JSON 파일 동시 표시
- 드래그 앤 드롭으로 entry 이동
- Save Both 버튼으로 양쪽 파일 저장

### 함수

```javascript
/**
 * 초기화
 * - FsStorage 준비 확인
 * - 파일 목록 로드 또는 Empty State 표시
 */
async function init();

/**
 * JSON 파일 목록 로드 및 표시
 */
async function loadFiles();

/**
 * 파일 카드 DOM 생성
 * @param {string} filename - 파일명
 * @returns {Promise<HTMLElement>} 파일 카드 요소
 */
async function createFileCard(filename);

/**
 * 상세 편집 뷰로 전환
 * @param {string} filename - 파일명
 */
function showDetailView(filename);

/**
 * 파일 내용 로드 및 entry 렌더링
 * @param {string} filename - 파일명
 */
async function loadFileDetail(filename);

/**
 * Entry 목록 렌더링
 * @param {Array} data - entry 배열
 */
function renderEntries(data);

/**
 * 단일 entry DOM 생성
 * @param {Object} entry - entry 객체 {selectors, validation, elementInfo}
 * @param {number} index - 배열 인덱스
 * @returns {HTMLElement} entry 요소
 */
function createEntryElement(entry, index);

/**
 * 셀렉터 목록 HTML 생성
 * @param {Object} selectors - 셀렉터 객체
 * @param {number} entryIndex - entry 인덱스
 * @returns {string} HTML 문자열
 */
function renderSelectors(selectors, entryIndex);

/**
 * 이동 모드로 전환
 */
function showMoveView();

/**
 * 좌/우 패널에 파일 로드
 * @param {string} side - 'left' 또는 'right'
 * @param {string} filename - 파일명
 */
async function loadMoveFile(side, filename);

/**
 * 패널에 entry 목록 렌더링
 * @param {string} side - 'left' 또는 'right'
 */
function renderMoveList(side);
```

### 드래그 앤 드롭 이벤트

```javascript
/**
 * 드래그 시작
 * - draggedItem에 side, index 저장
 */
function handleDragStart(e);

/**
 * 드롭 존 하이라이트
 */
function handleDragOver(e);

/**
 * 드롭 처리 및 entry 이동
 * - 원본에서 제거, 대상에 추가
 * - 양쪽 패널 재렌더링
 */
function handleDrop(e, targetSide);
```

### 사용 예시

```javascript
// 대시보드 열기 (sidepanel에서)
chrome.tabs.create({ url: 'dashboard.html' });

// 파일 목록 로드
await loadFiles();

// 파일 읽기 및 편집
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

// 파일 삭제
await FsStorage.deleteFile('old-file.json');
await loadFiles(); // 목록 갱신
```

### 데이터 구조

```javascript
// Entry 구조
{
  selectors: {
    tag: "button",
    id: "#submit-btn",
    classes: ".btn.btn-primary",
    "[data-testid]": "button[data-testid=\"submit\"]",
    nthOfType: "button:nth-of-type(2)",
    fullCssPath: "#form > div > button:nth-of-type(2)",
    xpath: "//button[@id=\"submit\"]",
    textXpath: "//button[contains(text(),'로그인')]"
  },
  validation: {
    tag: true,
    id: true,
    classes: true,
    // ...
  },
  elementInfo: {
    tagName: "button",
    id: "submit-btn",
    className: "btn btn-primary",
    textContent: "로그인",
    url: "https://example.com",
    timestamp: "2026-02-08T11:30:40.123Z"
  }
}
```

---

## 📋 체크리스트: API 호환성

- ✅ Content Script 메시지: `START_COLLECTING`, `STOP_COLLECTING`, `PING`, `VALIDATE_SELECTOR`
- ✅ Background 메시지: `GET_COLLECTING_STATE`, `SELECTORS_COLLECTED`
- ✅ Sidepanel 메시지: `START_COLLECTING`, `STOP_COLLECTING`, `VALIDATE_SELECTOR`
- ✅ Dashboard: `chrome.tabs.create()` 사용, FsStorage API 호출
- ✅ IndexedDB 키: `selectorHistory`, `directoryHandle`, `userSettings`
- ✅ 파일 시스템 권한: File System Access API Permissions

