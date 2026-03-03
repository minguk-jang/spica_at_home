# Selector Collector v2 - Chrome Extension 구현 계획서

> 이 문서는 `references/trial.md`의 셀렉터 수집 도구를 Chrome Extension (Manifest V3)으로 재구현하기 위한 **완전한 구현 명세**입니다.
> 이 문서만으로 전체 구현을 처음부터 끝까지 수행할 수 있어야 합니다.

---

## 1. 현재 상태

- `manifest.json` — 이미 생성됨 (수정 불필요)
- `icons/` — 디렉토리만 생성됨 (아이콘 파일 미생성)
- `lib/` — 디렉토리만 생성됨 (파일 미생성)
- 나머지 모든 JS/HTML/CSS 파일 — 미생성

### 생성해야 할 파일 목록 (순서대로)

| 순서 | 파일 | 설명 | 의존성 |
|------|------|------|--------|
| 1 | `icons/icon*.png` | 16/32/48/128px 아이콘 | 없음 |
| 2 | `selector-core.js` | 셀렉터 생성 엔진 (버그 수정 포함) | 없음 |
| 3 | `content.js` | Content Script | `selector-core.js` |
| 4 | `background.js` | Service Worker | 없음 |
| 5 | `lib/idb-helper.js` | IndexedDB 헬퍼 | 없음 |
| 6 | `lib/fs-storage.js` | File System Access API 래퍼 | `lib/idb-helper.js` |
| 7 | `sidepanel.css` | 사이드패널 스타일 | 없음 |
| 8 | `sidepanel.html` | 사이드패널 마크업 | `sidepanel.css`, `sidepanel.js` |
| 9 | `sidepanel.js` | 사이드패널 로직 | `lib/fs-storage.js`, `lib/idb-helper.js` |

---

## 2. 프로젝트 구조

```
selector_collector_ver2/
├── manifest.json              ✅ 생성됨
├── background.js              ❌ 미생성
├── content.js                 ❌ 미생성
├── selector-core.js           ❌ 미생성
├── sidepanel.html             ❌ 미생성
├── sidepanel.js               ❌ 미생성
├── sidepanel.css              ❌ 미생성
├── lib/
│   ├── fs-storage.js          ❌ 미생성
│   └── idb-helper.js          ❌ 미생성
├── icons/
│   ├── icon16.png             ❌ 미생성
│   ├── icon32.png             ❌ 미생성
│   ├── icon48.png             ❌ 미생성
│   └── icon128.png            ❌ 미생성
├── references/
│   └── trial.md               (변경 금지)
└── docs/
    ├── readme.md              (변경 금지)
    └── implementation-plan.md (이 문서)
```

---

## 3. 수정할 버그 4개 (trial.md 원본 대비)

### 버그 1: `nth-child` 계산 오류

**원본 코드 (잘못됨):**
```javascript
// 같은 태그만 필터링하면서 nth-child를 사용 → 위치가 틀림
const siblings = [...parent.children].filter(c => c.tagName === element.tagName);
if (siblings.length > 1) {
    const idx = siblings.indexOf(element) + 1;
    selectors.nthChild = `${element.tagName.toLowerCase()}:nth-child(${idx})`;
}
```

**문제:** `nth-child(n)`은 **모든 형제** 중 n번째를 의미하지만, 같은 태그만 필터한 인덱스를 사용.

**수정 코드:**
```javascript
// nth-of-type은 같은 태그 형제 중 순서 → 정확함
const siblings = [...parent.children].filter(c => c.tagName === element.tagName);
if (siblings.length > 1) {
    const idx = siblings.indexOf(element) + 1;
    selectors.nthOfType = `${element.tagName.toLowerCase()}:nth-of-type(${idx})`;
}
```

**fullCssPath에도 동일 적용:**
```javascript
// 수정 전: selector += `:nth-child(${idx})`;
// 수정 후:
selector += `:nth-of-type(${sibs.indexOf(current) + 1})`;
```

### 버그 2: XPath 접두사 오류

**원본 코드 (잘못됨):**
```javascript
if (!xpath.startsWith('//')) xpath = '/' + xpath;
// 결과: /html/body/div → //html/body/div (잘못됨!)
// //는 "어디서든 검색"이라는 의미. /html/body에서 쓰면 안됨.
```

**문제:** ID 앵커가 없는 경우에도 `//`를 붙여서 XPath 의미가 바뀜.

**수정 코드:**
```javascript
let foundId = false;
// ... (while 루프 내에서)
if (current.id) {
    foundId = true;
    // ...
}
// 루프 후:
if (foundId) {
    // ID 앵커 경로: //tag[@id="..."]/... (상대 경로)
    // xpath는 이미 //로 시작함
} else {
    // 절대 경로: /html/body/...
    xpath = '/html/body' + xpath;
}
```

### 버그 3: `CSS.escape()`를 속성값에 잘못 사용

**원본 코드 (잘못됨):**
```javascript
selectors[`[${attr}]`] = `${tag}[${attr}="${CSS.escape(value)}"]`;
// CSS.escape("hello world") → "hello\ world" → CSS 셀렉터에서 불필요한 이스케이프
```

**문제:** `CSS.escape()`는 식별자용. 속성값에는 `"`, `\`만 이스케이프하면 됨.

**수정 코드:**
```javascript
function escapeAttrValue(str) {
    return str.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
}
// 사용:
selectors[`[${attr}]`] = `${tag}[${attr}="${escapeAttrValue(value)}"]`;
```

### 버그 4: XPath 텍스트에서 작은따옴표 미이스케이프

**원본 코드 (잘못됨):**
```javascript
selectors.textContent = `//${tag}[contains(text(),'${text}')]`;
// text가 "it's here"이면 → XPath 문법 에러
```

**수정 코드:**
```javascript
function escapeXPathText(text) {
    if (!text.includes("'")) {
        return `'${text}'`;
    }
    if (!text.includes('"')) {
        return `"${text}"`;
    }
    // 둘 다 포함: concat() 사용
    const parts = text.split("'");
    return `concat('${parts.join("',\"'\",'")}')`;
}
// 사용:
selectors.textXpath = `//${tag}[contains(text(),${escapeXPathText(text)})]`;
```

---

## 4. 각 파일 상세 명세

### 4.1 `selector-core.js`

**패턴:** IIFE → `window.SelectorCore` 글로벌 객체로 노출

**공개 API:**
```javascript
window.SelectorCore = {
    getAllSelectors(element),      // → { id, classes, tag, attributes[], nthOfType, fullCssPath, xpath, textXpath }
    validateAllSelectors(selectors, targetElement),  // → { id: true/false, ... }
};
```

**내부 헬퍼 함수:**
```
escapeAttrValue(str)     - 속성값 이스케이프 (" → \", \ → \\)
escapeXPathText(text)    - XPath 텍스트 이스케이프 (concat 폴백)
buildFullCssPath(el)     - 전체 CSS 경로 (nth-of-type 사용, 버그 1 수정)
buildXPath(el)           - XPath 경로 (ID 앵커 시만 //, 버그 2 수정)
```

**getAllSelectors(element) 반환 형태:**
```javascript
{
    id: "#login-btn",                                    // element.id 있을 때만
    classes: ".btn.btn-primary",                         // className 있을 때만
    tag: "button",                                       // 항상
    // 속성 셀렉터들 (해당하는 것만):
    "[name]": "input[name=\"username\"]",
    "[type]": "input[type=\"text\"]",
    "[data-testid]": "button[data-testid=\"submit\"]",
    // ...기타 속성
    nthOfType: "button:nth-of-type(2)",                  // 같은 태그 형제가 2개 이상일 때만
    fullCssPath: "#app > div > form > button:nth-of-type(1)",
    xpath: "//button[@id=\"login-btn\"]",                // 또는 "/html/body/div/button"
    textXpath: "//button[contains(text(),'Log In')]"     // 리프 노드, 텍스트 50자 미만일 때만
}
```

**검사할 속성 목록:**
```javascript
const IMPORTANT_ATTRS = [
    'name', 'type', 'placeholder', 'value',
    'data-testid', 'data-id', 'data-cy', 'data-test',
    'aria-label', 'aria-labelledby', 'role',
    'href', 'src', 'alt', 'title', 'for'
];
```

**validateAllSelectors(selectors, targetElement) 로직:**
```javascript
// 각 셀렉터 키를 순회
// CSS 셀렉터 (id, classes, tag, [attr], nthOfType, fullCssPath):
//   → try { document.querySelector(selector) === targetElement } catch { false }
// XPath (xpath, textXpath):
//   → try { document.evaluate(selector, document, null, 9, null).singleNodeValue === targetElement } catch { false }
// 반환: { id: true, classes: false, tag: false, ... }
```

**주의사항:**
- 각 셀렉터 타입 생성 시 개별 try/catch (SVG/MathML 등 특수 요소 대응)
- `__sc-highlight` 클래스는 classes 셀렉터에서 제외
- `CSS.escape()`는 ID와 클래스명에만 사용 (식별자)
- 속성값에는 `escapeAttrValue()` 사용 (버그 3)

### 4.2 `content.js`

**상태:**
```javascript
let collecting = false;
let lastHighlighted = null;
```

**메시지 수신 (`chrome.runtime.onMessage`):**

| 메시지 타입 | 동작 |
|------------|------|
| `START_COLLECTING` | `collecting = true`, 표시 바 생성, 클릭 리스너 등록 |
| `STOP_COLLECTING` | `collecting = false`, 표시 바 제거, 클릭 리스너 해제, 하이라이트 제거 |
| `VALIDATE_SELECTOR` | `{ selector, isXPath }` → 해당 셀렉터로 요소 검색 → `{ valid: true/false }` 응답 |
| `PING` | `{ alive: true }` 응답 |

**클릭 핸들러:**
```javascript
function handleClick(e) {
    if (!collecting) return;
    // content.js가 만든 UI 요소 클릭은 무시
    if (e.target.closest('.__sc-status-bar')) return;

    e.preventDefault();
    e.stopPropagation();

    // 이전 하이라이트 제거
    if (lastHighlighted) lastHighlighted.classList.remove('__sc-highlight');

    // 새 하이라이트
    e.target.classList.add('__sc-highlight');
    lastHighlighted = e.target;

    // 셀렉터 수집
    const selectors = SelectorCore.getAllSelectors(e.target);
    const validation = SelectorCore.validateAllSelectors(selectors, e.target);

    // 요소 정보
    const elementInfo = {
        tagName: e.target.tagName.toLowerCase(),
        id: e.target.id || '',
        className: (typeof e.target.className === 'string') ? e.target.className : '',
        textContent: (e.target.textContent || '').trim().slice(0, 50),
        url: window.location.href,
        timestamp: new Date().toISOString()
    };

    // 메시지 전송
    chrome.runtime.sendMessage({
        type: 'SELECTORS_COLLECTED',
        data: { selectors, validation, elementInfo }
    });
}
// 등록: document.addEventListener('click', handleClick, true);
```

**수집 표시 바:**
- `position: fixed; top: 0; left: 0; width: 100%; height: 3px; z-index: 2147483647;`
- 그라디언트 애니메이션: `#58a6ff` ↔ `#238636` 반복
- 클래스명: `__sc-status-bar`

**하이라이트 스타일:**
- `outline: 3px solid #58a6ff !important; outline-offset: 2px;`
- 클래스명: `__sc-highlight`
- 스타일은 content.js에서 동적으로 `<style>` 태그 삽입

### 4.3 `background.js`

```javascript
// 사이드패널 설정
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });

// 수집 상태 (탭별)
// chrome.storage.local에 { collectingTabId: number | null } 저장

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    switch (message.type) {
        case 'START_COLLECTING':
            // 현재 활성 탭에 메시지 전달
            // content script가 없으면 chrome.scripting.executeScript로 주입
            break;

        case 'STOP_COLLECTING':
            // 현재 활성 탭에 메시지 전달
            break;

        case 'SELECTORS_COLLECTED':
            // content script → 사이드패널으로 전달 (그대로 포워딩)
            break;

        case 'VALIDATE_SELECTOR':
            // 사이드패널 → content script로 전달
            break;

        case 'GET_COLLECTING_STATE':
            // 사이드패널 초기화 시 현재 상태 조회
            break;
    }
});
```

**Content Script 동적 주입 로직:**
```javascript
async function ensureContentScript(tabId) {
    try {
        await chrome.tabs.sendMessage(tabId, { type: 'PING' });
    } catch {
        await chrome.scripting.executeScript({
            target: { tabId },
            files: ['selector-core.js', 'content.js']
        });
    }
}
```

**탭 관리:**
- `chrome.tabs.onRemoved` → 수집 중인 탭이 닫히면 상태 리셋
- `chrome.tabs.onActivated` → 탭 전환 시 사이드패널에 상태 동기화

### 4.4 `sidepanel.html`

```html
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <link rel="stylesheet" href="sidepanel.css">
</head>
<body>
    <!-- 헤더 -->
    <header class="header">
        <div class="header-title">
            <h1>Selector Collector</h1>
            <span class="status-dot" id="statusDot"></span>
        </div>
        <span class="status-text" id="statusText">대기 중</span>
    </header>

    <!-- 컨트롤 바 -->
    <div class="controls">
        <button id="toggleBtn" class="btn btn-primary">Start Collecting</button>
        <button id="savBtn" class="btn btn-secondary" disabled>Save</button>
        <button id="dirBtn" class="btn btn-secondary">Set Directory</button>
    </div>

    <!-- 현재 요소 카드 -->
    <div class="element-card" id="elementCard" style="display:none;">
        <div class="element-tag" id="elTag"></div>
        <div class="element-detail" id="elId"></div>
        <div class="element-detail" id="elClass"></div>
        <div class="element-detail element-url" id="elUrl"></div>
    </div>

    <!-- 셀렉터 그리드 -->
    <div class="selectors-grid" id="selectorsGrid"></div>

    <!-- 히스토리 패널 (접이식) -->
    <details class="history-panel" id="historyPanel">
        <summary class="history-summary">
            히스토리 (<span id="historyCount">0</span>)
            <button id="exportBtn" class="btn-icon" title="JSON 내보내기">Export</button>
            <button id="clearHistoryBtn" class="btn-icon btn-danger" title="히스토리 지우기">Clear</button>
        </summary>
        <div class="history-list" id="historyList"></div>
    </details>

    <!-- 푸터 -->
    <footer class="footer">
        <span id="footerStatus">준비됨</span>
    </footer>

    <script src="lib/idb-helper.js"></script>
    <script src="lib/fs-storage.js"></script>
    <script src="sidepanel.js"></script>
</body>
</html>
```

### 4.5 `sidepanel.css`

**테마 변수:**
```css
:root {
    --bg-primary: #0d1117;
    --bg-secondary: #161b22;
    --bg-tertiary: #21262d;
    --border: #30363d;
    --text-primary: #c9d1d9;
    --text-secondary: #8b949e;
    --accent: #58a6ff;
    --green: #238636;
    --green-text: #7ee787;
    --red: #f85149;
    --orange: #f0883e;
    --font-mono: 'Fira Code', Consolas, 'Courier New', monospace;
}
```

**주요 컴포넌트:**
- `body`: `background: var(--bg-primary)`, `padding: 0`, `font-size: 13px`
- `.header`: 상단 고정, 배경 `var(--bg-secondary)`, 하단 border
- `.status-dot`: 8px 원, 수집 중이면 `background: var(--green)` + 펄싱 애니메이션
- `.controls`: `display: flex; gap: 8px; padding: 12px;`
- `.btn-primary`: `background: var(--green)`, 수집 중이면 `background: var(--red)`
- `.element-card`: `background: var(--bg-tertiary)`, `border-radius: 6px`, `margin: 0 12px`
- `.selectors-grid`: 각 행 = `.selector-row` > `.selector-label` + `.selector-value` + `.validation-icon` + `.copy-btn`
- `.selector-value`: `font-family: var(--font-mono)`, `background: var(--bg-primary)`, `word-break: break-all`
- `.validation-icon.valid`: `color: var(--green-text)` (체크마크 ✓)
- `.validation-icon.invalid`: `color: var(--red)` (X 마크 ✗)
- `.history-panel`: `<details>` 스타일링, 접이식
- `.history-item`: `padding: 8px`, hover 시 `background: var(--bg-tertiary)`
- `.footer`: 하단 고정, `font-size: 11px`, `color: var(--text-secondary)`
- 스크롤: `body` 전체 스크롤, `::-webkit-scrollbar` 커스텀 (4px 너비)

### 4.6 `sidepanel.js`

**초기화:**
```javascript
document.addEventListener('DOMContentLoaded', async () => {
    // 1. UI 요소 참조 캐싱
    // 2. 이벤트 리스너 등록
    // 3. chrome.storage.local에서 히스토리 로드
    // 4. background에 현재 수집 상태 조회 (GET_COLLECTING_STATE)
    // 5. 저장 디렉토리 핸들 복원 시도
});
```

**메시지 수신:**
```javascript
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === 'SELECTORS_COLLECTED') {
        const { selectors, validation, elementInfo } = message.data;
        displayElementInfo(elementInfo);
        displaySelectors(selectors, validation);
        addToHistory({ selectors, validation, elementInfo });
    }
});
```

**displaySelectors(selectors, validation):**
```javascript
// selectorsGrid 초기화
// 셀렉터 타입 표시 순서: id → classes → tag → 속성들 → nthOfType → fullCssPath → xpath → textXpath
// 각 행 HTML:
// <div class="selector-row">
//     <span class="selector-label">ID</span>
//     <code class="selector-value" title="클릭하여 복사">#login-btn</code>
//     <span class="validation-icon valid">✓</span>
//     <button class="copy-btn" data-selector="#login-btn">Copy</button>
// </div>
```

**복사 기능:**
```javascript
// 이벤트 위임 (selectorsGrid에 단일 리스너)
selectorsGrid.addEventListener('click', async (e) => {
    const copyBtn = e.target.closest('.copy-btn');
    if (!copyBtn) return;
    const selector = copyBtn.dataset.selector;
    await navigator.clipboard.writeText(selector);
    copyBtn.textContent = 'Copied!';
    setTimeout(() => copyBtn.textContent = 'Copy', 1500);
});
```

**히스토리 관리:**
```javascript
let history = [];  // 최대 100개

function addToHistory(entry) {
    history.unshift(entry);
    if (history.length > 100) history.pop();
    updateHistoryUI();
    saveHistoryToStorage();
}

function saveHistoryToStorage() {
    chrome.storage.local.set({ selectorHistory: history });
}

function loadHistoryFromStorage() {
    chrome.storage.local.get('selectorHistory', (result) => {
        history = result.selectorHistory || [];
        updateHistoryUI();
    });
}
```

**히스토리 UI:**
```javascript
// historyList에 각 항목 렌더링
// 각 항목: 태그명 + id/class 요약 + 타임스탬프
// 클릭하면 해당 항목의 셀렉터를 selectorsGrid에 표시
// exportBtn: 전체 히스토리 JSON 다운로드 (Blob + URL.createObjectURL)
```

**Start/Stop 토글:**
```javascript
toggleBtn.addEventListener('click', async () => {
    if (collecting) {
        chrome.runtime.sendMessage({ type: 'STOP_COLLECTING' });
        setCollectingUI(false);
    } else {
        chrome.runtime.sendMessage({ type: 'START_COLLECTING' });
        setCollectingUI(true);
    }
    collecting = !collecting;
});

function setCollectingUI(active) {
    toggleBtn.textContent = active ? 'Stop Collecting' : 'Start Collecting';
    toggleBtn.classList.toggle('collecting', active);
    statusDot.classList.toggle('active', active);
    statusText.textContent = active ? '수집 중...' : '대기 중';
}
```

**파일 저장 연동:**
```javascript
dirBtn.addEventListener('click', async () => {
    const selected = await FsStorage.selectDirectory();
    if (selected) {
        footerStatus.textContent = '디렉토리 설정됨';
        savBtn.disabled = false;
    }
});

savBtn.addEventListener('click', async () => {
    if (history.length === 0) return;
    const data = {
        exportedAt: new Date().toISOString(),
        totalEntries: history.length,
        entries: history
    };
    const filename = `selectors-${new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)}.json`;
    try {
        await FsStorage.saveJson(filename, data);
        footerStatus.textContent = `저장됨: ${filename}`;
    } catch (err) {
        footerStatus.textContent = `저장 실패: ${err.message}`;
    }
});
```

### 4.7 `lib/idb-helper.js`

```javascript
// IIFE → window.IdbHelper
const IdbHelper = (() => {
    const DB_NAME = 'SelectorCollectorDB';
    const DB_VERSION = 1;
    const STORE_NAME = 'keyval';

    function openDB() {
        return new Promise((resolve, reject) => {
            const req = indexedDB.open(DB_NAME, DB_VERSION);
            req.onupgradeneeded = () => {
                req.result.createObjectStore(STORE_NAME);
            };
            req.onsuccess = () => resolve(req.result);
            req.onerror = () => reject(req.error);
        });
    }

    async function get(key) {
        const db = await openDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(STORE_NAME, 'readonly');
            const req = tx.objectStore(STORE_NAME).get(key);
            req.onsuccess = () => resolve(req.result);
            req.onerror = () => reject(req.error);
        });
    }

    async function set(key, value) {
        const db = await openDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(STORE_NAME, 'readwrite');
            tx.objectStore(STORE_NAME).put(value, key);
            tx.oncomplete = () => resolve();
            tx.onerror = () => reject(tx.error);
        });
    }

    return { get, set };
})();
```

### 4.8 `lib/fs-storage.js`

```javascript
// IIFE → window.FsStorage
// 의존성: IdbHelper (같은 페이지에서 먼저 로드)

const FsStorage = (() => {
    const DIR_HANDLE_KEY = 'directoryHandle';
    let dirHandle = null;

    async function selectDirectory() {
        try {
            dirHandle = await window.showDirectoryPicker({ mode: 'readwrite' });
            await IdbHelper.set(DIR_HANDLE_KEY, dirHandle);
            return true;
        } catch (err) {
            if (err.name === 'AbortError') return false;  // 사용자 취소
            throw err;
        }
    }

    async function ensurePermission() {
        if (!dirHandle) {
            dirHandle = await IdbHelper.get(DIR_HANDLE_KEY);
        }
        if (!dirHandle) return false;

        const opts = { mode: 'readwrite' };
        if ((await dirHandle.queryPermission(opts)) === 'granted') return true;
        if ((await dirHandle.requestPermission(opts)) === 'granted') return true;
        return false;
    }

    async function saveJson(filename, data) {
        if (!await ensurePermission()) {
            throw new Error('디렉토리 접근 권한이 없습니다');
        }
        const fileHandle = await dirHandle.getFileHandle(filename, { create: true });
        const writable = await fileHandle.createWritable();
        await writable.write(JSON.stringify(data, null, 2));
        await writable.close();
    }

    async function restoreHandle() {
        try {
            dirHandle = await IdbHelper.get(DIR_HANDLE_KEY);
            return !!dirHandle;
        } catch {
            return false;
        }
    }

    return { selectDirectory, ensurePermission, saveJson, restoreHandle };
})();
```

### 4.9 아이콘 생성

Canvas API를 사용하여 프로그래밍 방식으로 생성하거나, 간단한 SVG → PNG 변환 사용.

**디자인:** 파란색 (#58a6ff) 배경에 커서(pointer) 아이콘 또는 타겟(crosshair) 모양.

**생성 방법 (Node.js canvas 또는 단순 데이터 URL):**
- `sharp` 라이브러리나 `canvas` 패키지가 없으면 base64 인코딩된 최소 PNG를 직접 작성
- 또는 1x1 단색 PNG를 각 크기로 생성 (최소 기능 확보)

---

## 5. 통신 프로토콜

### 메시지 흐름

```
┌─────────────┐     ┌──────────────┐     ┌────────────────┐
│  sidepanel   │ ←→  │  background   │ ←→  │ content script  │
│  (sidepanel  │     │  (service     │     │ (content.js +   │
│    .js)      │     │   worker)     │     │  selector-core) │
└─────────────┘     └──────────────┘     └────────────────┘
```

### 메시지 타입 정의

```javascript
// 사이드패널 → background (chrome.runtime.sendMessage)
{ type: 'START_COLLECTING' }
{ type: 'STOP_COLLECTING' }
{ type: 'GET_COLLECTING_STATE' }
{ type: 'VALIDATE_SELECTOR', data: { selector: string, isXPath: boolean } }

// background → content script (chrome.tabs.sendMessage)
{ type: 'START_COLLECTING' }
{ type: 'STOP_COLLECTING' }
{ type: 'VALIDATE_SELECTOR', data: { selector: string, isXPath: boolean } }
{ type: 'PING' }

// content script → background (chrome.runtime.sendMessage)
{ type: 'SELECTORS_COLLECTED', data: { selectors, validation, elementInfo } }

// content script → background → 사이드패널 (포워딩)
// background가 수신 후 chrome.runtime.sendMessage로 재전송
// (사이드패널은 같은 익스텐션의 runtime 메시지를 수신 가능)

// content script 응답 (sendResponse)
{ alive: true }                      // PING 응답
{ valid: true/false }                // VALIDATE_SELECTOR 응답
```

### background.js 메시지 라우팅 상세

```javascript
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    // sender.tab이 있으면 → content script에서 온 메시지
    // sender.tab이 없으면 → 사이드패널/팝업에서 온 메시지

    if (message.type === 'SELECTORS_COLLECTED' && sender.tab) {
        // content → 사이드패널 포워딩
        // chrome.runtime.sendMessage()로 재전송 (사이드패널이 수신)
    }

    if (message.type === 'START_COLLECTING' && !sender.tab) {
        // 사이드패널 → 활성 탭의 content script로 전달
        // chrome.tabs.query({ active: true, currentWindow: true })
        // → ensureContentScript(tab.id)
        // → chrome.tabs.sendMessage(tab.id, message)
    }

    // return true; // 비동기 응답 시
});
```

---

## 6. JSON 출력 형식

```json
{
  "exportedAt": "2026-02-07T14:32:05.123Z",
  "totalEntries": 3,
  "entries": [
    {
      "elementInfo": {
        "tagName": "button",
        "id": "login-btn",
        "className": "btn btn-primary",
        "textContent": "Log In",
        "url": "https://example.com/login",
        "timestamp": "2026-02-07T14:32:05.123Z"
      },
      "selectors": {
        "id": "#login-btn",
        "classes": ".btn.btn-primary",
        "tag": "button",
        "nthOfType": "button:nth-of-type(1)",
        "fullCssPath": "#app > div > form > button:nth-of-type(1)",
        "xpath": "//button[@id=\"login-btn\"]",
        "textXpath": "//button[contains(text(),'Log In')]"
      },
      "validation": {
        "id": true,
        "classes": true,
        "tag": false,
        "nthOfType": true,
        "fullCssPath": true,
        "xpath": true,
        "textXpath": true
      }
    }
  ]
}
```

---

## 7. 에러 처리

| 시나리오 | 위치 | 처리 방법 |
|----------|------|-----------|
| Content Script 미로딩 | `background.js` | `ensureContentScript()` → `chrome.scripting.executeScript` |
| 탭 닫힘/네비게이션 | `background.js` | `chrome.tabs.onRemoved` / `onUpdated` → 상태 리셋, 에러 catch |
| SVG/MathML 특수 요소 | `selector-core.js` | 각 셀렉터 타입별 try/catch, 실패 시 해당 키 생략 |
| `querySelector` 예외 | `selector-core.js` | validation에서 try/catch → `false` 반환 |
| `document.evaluate` 예외 | `selector-core.js` | validation에서 try/catch → `false` 반환 |
| 디렉토리 선택 취소 | `lib/fs-storage.js` | `AbortError` catch → `false` 반환, UI에 표시 안 함 |
| 파일 쓰기 실패 | `sidepanel.js` | catch → footer에 에러 메시지 표시 |
| 권한 거부 | `lib/fs-storage.js` | `ensurePermission()` → `false` 반환 → save 시 에러 throw |
| `className`이 SVGAnimatedString | `selector-core.js` | `typeof el.className === 'string'` 체크 |
| 메시지 전송 실패 | 각 위치 | `chrome.runtime.lastError` 체크 또는 try/catch |

---

## 8. 구현 순서 체크리스트

작업 시 아래 순서를 따르고, 각 항목 완료 후 체크합니다.

- [ ] **1. 아이콘 생성** — `icons/icon16.png`, `icon32.png`, `icon48.png`, `icon128.png`
- [ ] **2. selector-core.js** — IIFE, getAllSelectors, validateAllSelectors, 4개 버그 수정
- [ ] **3. content.js** — 클릭 캡처, 하이라이트, 표시 바, 메시지 송수신
- [ ] **4. background.js** — 사이드패널 설정, 메시지 라우팅, 동적 주입
- [ ] **5. lib/idb-helper.js** — IndexedDB get/set
- [ ] **6. lib/fs-storage.js** — selectDirectory, ensurePermission, saveJson
- [ ] **7. sidepanel.css** — 다크 테마 스타일 전체
- [ ] **8. sidepanel.html** — 마크업 (스크립트 참조 포함)
- [ ] **9. sidepanel.js** — 셀렉터 표시, 복사, 히스토리, 파일 저장 연동

---

## 9. 검증 절차

1. `chrome://extensions/` → 개발자 모드 → "압축해제된 확장 프로그램을 로드합니다" → 프로젝트 폴더 선택
2. 아무 웹사이트 방문 → 익스텐션 아이콘 클릭 → 사이드패널 열림 확인
3. "Start Collecting" 클릭 → 페이지 상단 그라디언트 바 + 사이드패널 상태 변경 확인
4. 페이지 요소 클릭 → 사이드패널에 셀렉터 + 검증 아이콘 표시 확인
5. **버그 수정 검증:**
   - 테이블에서 두 번째 `<td>` 클릭 → `td:nth-of-type(2)` 확인 (nth-child 아님)
   - ID 없는 깊은 요소 → XPath가 `/html/body/...`로 시작 확인 (`//html/body` 아님)
   - `data-testid="hello world"` 속성 요소 → 속성값에 불필요한 백슬래시 없음 확인
   - 텍스트에 작은따옴표 포함 요소 (`it's`) → XPath 에러 없이 생성 확인
6. 복사 버튼 클릭 → 클립보드에 셀렉터 복사 확인
7. "Set Directory" → 폴더 선택 → "Save" → JSON 파일 생성 + 형식 확인
8. 히스토리 축적 (여러 요소 클릭) → Export → JSON 다운로드 확인
9. 익스텐션 재시작 → 디렉토리 핸들 유지 + 히스토리 유지 확인
10. "Stop Collecting" → 클릭이 정상적으로 동작하고 셀렉터 수집 안 됨 확인

---

## 10. 기존 manifest.json 내용 (참조)

```json
{
  "manifest_version": 3,
  "name": "Selector Collector",
  "version": "2.0.0",
  "description": "클릭한 웹 요소의 모든 CSS/XPath 셀렉터를 수집하고 검증합니다",
  "permissions": ["activeTab", "sidePanel", "scripting", "storage"],
  "host_permissions": ["<all_urls>"],
  "background": {
    "service_worker": "background.js"
  },
  "side_panel": {
    "default_path": "sidepanel.html"
  },
  "content_scripts": [
    {
      "matches": ["<all_urls>"],
      "js": ["selector-core.js", "content.js"],
      "run_at": "document_idle"
    }
  ],
  "action": {
    "default_title": "Selector Collector",
    "default_icon": {
      "16": "icons/icon16.png",
      "32": "icons/icon32.png",
      "48": "icons/icon48.png",
      "128": "icons/icon128.png"
    }
  },
  "icons": {
    "16": "icons/icon16.png",
    "32": "icons/icon32.png",
    "48": "icons/icon48.png",
    "128": "icons/icon128.png"
  }
}
```
