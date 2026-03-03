# 히스토리 클릭 시 웹페이지 요소 하이라이트 구현 계획

> 히스토리 항목을 클릭하면 웹페이지에서 해당 요소를 찾아 스크롤 이동 + 하이라이트하는 기능

## 요구사항 정리

### 핵심 목표
- 히스토리 패널에서 항목 클릭 → 웹페이지에서 해당 요소를 찾아 **스크롤 이동**, **아웃라인 표시**, **펄스 애니메이션**으로 시선 유도
- 수집(collecting) 중이든 아니든 관계없이 동작
- 요소를 못 찾으면 사용자에게 피드백 제공

### 동작 시나리오
1. **수집 중**: collectingTabId 탭에서 셀렉터로 요소를 찾아 하이라이트
2. **수집 중지 후 (같은 페이지)**: lastTabId 또는 현재 활성 탭에서 시도
3. **다른 페이지로 이동**: 현재 활성 탭에서 셀렉터를 시도, 못 찾으면 "Element not found" 표시
4. **탭 닫힌 경우**: 현재 활성 탭에서 시도

---

## 설계 결정사항

### 1. 셀렉터 우선순위 (유효성 검증된 첫 번째 셀렉터)
히스토리 항목의 `validation` 객체를 참조하여 `true`인 셀렉터를 우선순위 순으로 시도:

```
id → classes → tag → [속성 셀렉터] → nthOfType → fullCssPath → xpath → textXpath
```

- CSS 셀렉터를 먼저 시도하고, 실패 시 XPath 시도
- 모든 셀렉터가 실패하면 "Element not found" 표시

### 2. 대상 탭 결정 로직
```
1. collectingTabId가 있으면 → 해당 탭
2. 없으면 → 현재 활성 탭에서 시도
```
- 기존 `TEST_CLICK_SELECTOR`와 유사한 라우팅이지만, **클릭 실행은 하지 않음** (하이라이트만)

### 3. 하이라이트 표시 방식
- **scrollIntoView**: 요소가 뷰포트 중앙에 오도록 부드럽게 스크롤
- **아웃라인**: 3px solid 강조색 (수집 하이라이트와 구분되는 색상)
- **펄스 애니메이션**: 2~3회 깜빡이며 시선 유도, 총 2초간 지속 후 자동 제거
- **반투명 오버레이**: 요소 주변에 살짝 어두운 배경으로 집중 효과 (선택사항)

---

## 구현 계획

### Phase 1: content.js - 하이라이트 메시지 핸들러 추가

#### 1.1 새 메시지 타입 `HIGHLIGHT_ELEMENT` 추가

**파일**: `content.js`

```javascript
case 'HIGHLIGHT_ELEMENT': {
    const { selector, isXPath } = message.data;
    let element = null;
    try {
        if (isXPath) {
            const result = document.evaluate(
                selector, document, null,
                XPathResult.FIRST_ORDERED_NODE_TYPE, null
            );
            element = result.singleNodeValue;
        } else {
            element = document.querySelector(selector);
        }

        if (element) {
            // 이전 하이라이트 제거
            clearHighlight();
            removeHighlightPulse();

            // 스크롤 이동
            element.scrollIntoView({ behavior: 'smooth', block: 'center' });

            // 펄스 아웃라인 하이라이트
            element.classList.add('__sc-highlight-pulse');
            lastHighlighted = element;

            // 2초 후 자동 제거
            setTimeout(() => {
                if (element.classList.contains('__sc-highlight-pulse')) {
                    element.classList.remove('__sc-highlight-pulse');
                }
            }, 2000);

            sendResponse({ success: true });
        } else {
            sendResponse({ success: false, error: 'Element not found' });
        }
    } catch (e) {
        sendResponse({ success: false, error: e.message });
    }
    return true;
}
```

#### 1.2 펄스 애니메이션 CSS 추가

**파일**: `content.js` (injectStyles 내부)

```css
.__sc-highlight-pulse {
    outline: 3px solid #f78166 !important;
    outline-offset: 2px;
    animation: sc-pulse 0.5s ease-in-out 3;
}

@keyframes sc-pulse {
    0%, 100% { outline-color: #f78166; }
    50% { outline-color: transparent; }
}
```

- 기존 `__sc-highlight` (파란색 #58a6ff)와 구분되는 주황색 (#f78166) 사용
- 3회 펄스 후 정지

#### 1.3 removeHighlightPulse 헬퍼 함수

```javascript
function removeHighlightPulse() {
    const prev = document.querySelector('.__sc-highlight-pulse');
    if (prev) prev.classList.remove('__sc-highlight-pulse');
}
```

---

### Phase 2: background.js - 메시지 라우팅 추가

#### 2.1 `HIGHLIGHT_ELEMENT` 메시지 포워딩

**파일**: `background.js`

기존 `TEST_CLICK_SELECTOR` 핸들러와 동일한 패턴으로 추가:

```javascript
else if (message.type === 'HIGHLIGHT_ELEMENT') {
    (async () => {
        // 1. collectingTabId 확인
        let tabId = await getCollectingTabId();
        // 2. 없으면 현재 활성 탭 사용
        if (!tabId) {
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            tabId = tab?.id;
        }
        if (tabId) {
            try {
                await ensureContentScript(tabId);
                const response = await chrome.tabs.sendMessage(tabId, message);
                sendResponse(response);
            } catch (e) {
                sendResponse({ success: false, error: e.message });
            }
        } else {
            sendResponse({ success: false, error: 'No target tab' });
        }
    })();
    return true;
}
```

---

### Phase 3: sidepanel.js - 히스토리 클릭 핸들러 확장

#### 3.1 셀렉터 우선순위 선택 함수

**파일**: `sidepanel.js`

```javascript
function pickBestSelector(selectors, validation) {
    const cssOrder = ['id', 'classes', 'tag'];
    // 속성 셀렉터 추가
    Object.keys(selectors).forEach(key => {
        if (key.startsWith('[')) cssOrder.push(key);
    });
    cssOrder.push('nthOfType', 'fullCssPath');

    const xpathOrder = ['xpath', 'textXpath'];

    // CSS 셀렉터 우선 시도
    for (const key of cssOrder) {
        if (selectors[key] && validation[key]) {
            return { selector: selectors[key], isXPath: false };
        }
    }
    // XPath 시도
    for (const key of xpathOrder) {
        if (selectors[key] && validation[key]) {
            return { selector: selectors[key], isXPath: true };
        }
    }
    // validation 무시하고 아무거나 시도
    for (const key of [...cssOrder, ...xpathOrder]) {
        if (selectors[key]) {
            return { selector: selectors[key], isXPath: xpathOrder.includes(key) };
        }
    }
    return null;
}
```

#### 3.2 히스토리 항목 클릭 이벤트 확장

**파일**: `sidepanel.js` (`updateHistoryUI` 함수 수정)

기존 클릭 핸들러에 하이라이트 요청 추가:

```javascript
div.addEventListener('click', async () => {
    // 기존: 사이드패널 UI 업데이트
    displayElementInfo(entry.elementInfo);
    displaySelectors(entry.selectors, entry.validation);

    // 신규: 웹페이지에서 요소 하이라이트
    const best = pickBestSelector(entry.selectors, entry.validation);
    if (best) {
        try {
            const response = await chrome.runtime.sendMessage({
                type: 'HIGHLIGHT_ELEMENT',
                data: best
            });
            if (!response || !response.success) {
                // 시각적 피드백: 히스토리 항목에 "못 찾음" 표시
                showHistoryItemFeedback(div, false);
            }
        } catch (err) {
            // 메시지 전송 실패 (탭 없음 등)
            showHistoryItemFeedback(div, false);
        }
    }
});
```

#### 3.3 히스토리 항목 피드백 UI

```javascript
function showHistoryItemFeedback(itemDiv, found) {
    if (!found) {
        itemDiv.style.opacity = '0.5';
        const badge = document.createElement('span');
        badge.className = 'history-not-found';
        badge.textContent = '요소 없음';
        itemDiv.appendChild(badge);
        setTimeout(() => {
            itemDiv.style.opacity = '';
            badge.remove();
        }, 2000);
    }
}
```

---

### Phase 4: sidepanel.css - 피드백 스타일

#### 4.1 "요소 없음" 배지 스타일

**파일**: `sidepanel.css`

```css
.history-not-found {
    font-size: 10px;
    color: var(--danger, #f85149);
    background: var(--danger-bg, rgba(248, 81, 73, 0.1));
    padding: 1px 6px;
    border-radius: 3px;
    margin-left: auto;
}
```

---

## 수정 파일 목록

| 파일 | 변경 내용 | 난이도 |
|------|----------|--------|
| `content.js` | `HIGHLIGHT_ELEMENT` 메시지 핸들러 + 펄스 CSS | 낮음 |
| `background.js` | `HIGHLIGHT_ELEMENT` 메시지 라우팅 | 낮음 |
| `sidepanel.js` | `pickBestSelector()`, 히스토리 클릭 확장, 피드백 UI | 중간 |
| `sidepanel.css` | `.history-not-found` 스타일 | 낮음 |

---

## 메시지 플로우

```
사이드패널 히스토리 항목 클릭
        ↓
sidepanel.js: pickBestSelector() → 최적 셀렉터 선택
        ↓
chrome.runtime.sendMessage({ type: 'HIGHLIGHT_ELEMENT', data: { selector, isXPath } })
        ↓
background.js: 대상 탭 결정 (collectingTab → 활성 탭)
        ↓
chrome.tabs.sendMessage(tabId, message)
        ↓
content.js: 셀렉터로 요소 찾기
        ↓
  ┌─ 찾음: scrollIntoView + 펄스 아웃라인 → { success: true }
  └─ 못 찾음: → { success: false, error: 'Element not found' }
        ↓
sidepanel.js: 실패 시 히스토리 항목에 "요소 없음" 배지 표시
```

---

## 리스크 및 고려사항

| 리스크 | 수준 | 대응 |
|--------|------|------|
| 페이지 DOM 변경으로 셀렉터 무효화 | 중간 | 여러 셀렉터 fallback 시도 |
| Content script 미로드 상태 | 낮음 | `ensureContentScript()` 로 자동 주입 |
| SPA에서 DOM 동적 변경 | 중간 | 현재 페이지 기준으로 시도, 실패 피드백 |
| 애니메이션 성능 | 낮음 | CSS animation만 사용 (JS 불필요) |
| 히스토리 항목 빠른 연속 클릭 | 낮음 | 이전 하이라이트 자동 제거 |

---

## 예상 복잡도: **낮음~중간**

- content.js: ~30줄 추가
- background.js: ~20줄 추가
- sidepanel.js: ~50줄 추가
- sidepanel.css: ~10줄 추가

---

## 상태
- **작성일**: 2026-02-08
- **상태**: 📋 계획 수립 완료, 구현 대기
