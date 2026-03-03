# Test 버튼 및 유효성 토글 구현 로그

> **상태**: ✅ **완성** (2026-02-08)

## 배경

현재 사이드패널의 각 셀렉터 행 구조:
```
[ Label ] [ 셀렉터 텍스트(code) ] [ ✓/✗ ] [ Copy ]
```

**문제**: 텍스트 박스(code 요소)를 클릭해도 복사가 되므로, 오른쪽 Copy 버튼이 중복 기능이다.

**목표**: Copy 버튼을 **Test 버튼**으로 교체하여, 해당 셀렉터로 실제 요소를 찾아 `.click()`을 실행하는 기능을 추가한다.

---

## 실현 가능성 분석

### 핵심 질문: 사이드패널에서 웹페이지의 요소를 클릭할 수 있는가?

**답: 가능하다.**

이미 `content.js`에 메시지 핸들러가 있고, `background.js`가 사이드패널 ↔ content script 간 메시지를 중계하고 있다.
기존 `VALIDATE_SELECTOR` 메시지처럼 새로운 메시지 타입 `TEST_CLICK_SELECTOR`를 추가하면 된다.

### 통신 흐름
```
사이드패널 (Test 버튼 클릭)
  → chrome.runtime.sendMessage({ type: 'TEST_CLICK_SELECTOR', data: { selector, isXPath } })
  → background.js (중계)
  → chrome.tabs.sendMessage(tabId, message)
  → content.js (실제 요소 찾아서 .click() 실행)
  → sendResponse({ success: true/false, error? })
```

### 기존 인프라 활용
- `VALIDATE_SELECTOR` 패턴을 그대로 재사용
- `background.js`의 메시지 라우팅 로직 확장
- `content.js`의 switch 문에 새 case 추가

---

## 구현 단계

### 1단계: content.js - TEST_CLICK_SELECTOR 핸들러 추가

**파일**: `content.js` (switch 문, ~줄 147 이후)

```javascript
case 'TEST_CLICK_SELECTOR': {
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
            element.click();
            sendResponse({ success: true });
        } else {
            sendResponse({ success: false, error: 'Element not found' });
        }
    } catch (e) {
        sendResponse({ success: false, error: e.message });
    }
    break;
}
```

### 2단계: background.js - 메시지 라우팅 추가

**파일**: `background.js` (~줄 123, `VALIDATE_SELECTOR` 블록 아래)

`VALIDATE_SELECTOR`와 동일한 패턴으로 `TEST_CLICK_SELECTOR` 추가:

```javascript
else if (message.type === 'TEST_CLICK_SELECTOR') {
    (async () => {
        const tabId = await getCollectingTabId();
        if (tabId) {
            try {
                const response = await chrome.tabs.sendMessage(tabId, message);
                sendResponse(response);
            } catch (e) {
                sendResponse({ success: false, error: e.message });
            }
        } else {
            sendResponse({ success: false, error: 'Not collecting' });
        }
    })();
    return true;
}
```

### 3단계: sidepanel.js - Copy 버튼을 Test 버튼으로 교체

**파일**: `sidepanel.js`

#### 3-1. 버튼 생성 변경 (~줄 156-160)
```javascript
// 기존: Copy Button
// const copyBtn = document.createElement('button');
// copyBtn.className = 'copy-btn';
// copyBtn.textContent = 'Copy';
// copyBtn.dataset.selector = value;

// 변경: Test Button
const testBtn = document.createElement('button');
testBtn.className = 'test-btn';
testBtn.textContent = 'Test';
testBtn.dataset.selector = value;
testBtn.dataset.isXpath = (key === 'xpath' || key === 'textXpath') ? 'true' : 'false';
```

#### 3-2. 이벤트 위임 변경 (~줄 441-446)
```javascript
// 기존: Copy 이벤트 위임
// selectorsGrid.addEventListener('click', async (e) => {
//     const copyBtn = e.target.closest('.copy-btn');
//     if (!copyBtn) return;
//     await copyToClipboard(copyBtn.dataset.selector, copyBtn);
// });

// 변경: Test 이벤트 위임
selectorsGrid.addEventListener('click', async (e) => {
    const testBtn = e.target.closest('.test-btn');
    if (!testBtn) return;

    const selector = testBtn.dataset.selector;
    const isXPath = testBtn.dataset.isXpath === 'true';

    testBtn.textContent = '...';
    testBtn.disabled = true;

    try {
        const response = await chrome.runtime.sendMessage({
            type: 'TEST_CLICK_SELECTOR',
            data: { selector, isXPath }
        });

        if (response && response.success) {
            testBtn.textContent = 'OK!';
            testBtn.classList.add('test-success');
        } else {
            testBtn.textContent = 'Fail';
            testBtn.classList.add('test-fail');
        }
    } catch (err) {
        testBtn.textContent = 'Err';
        testBtn.classList.add('test-fail');
    }

    setTimeout(() => {
        testBtn.textContent = 'Test';
        testBtn.disabled = false;
        testBtn.classList.remove('test-success', 'test-fail');
    }, 1500);
});
```

### 4단계: sidepanel.css - 스타일 변경

**파일**: `sidepanel.css`

기존 `.copy-btn` 스타일을 `.test-btn`으로 변경하고, 성공/실패 상태 스타일 추가:

```css
.test-btn {
    font-family: var(--font-sans);
    font-size: 10px;
    font-weight: 500;
    padding: 3px 8px;
    border-radius: 4px;
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text-tertiary);
    cursor: pointer;
    transition: all 0.12s ease;
    letter-spacing: 0.01em;
}

.test-btn:hover {
    background: var(--accent-muted);
    color: var(--accent);
    border-color: var(--accent);
}

.test-btn.test-success {
    background: rgba(34, 197, 94, 0.15);
    color: #22c55e;
    border-color: #22c55e;
}

.test-btn.test-fail {
    background: rgba(239, 68, 68, 0.15);
    color: #ef4444;
    border-color: #ef4444;
}
```

---

## 수정 파일 목록

| 파일 | 변경 내용 |
|------|----------|
| `content.js` | `TEST_CLICK_SELECTOR` case 추가 |
| `background.js` | 메시지 라우팅 추가 |
| `sidepanel.js` | Copy → Test 버튼 변경, 이벤트 핸들러 변경 |
| `sidepanel.css` | `.copy-btn` → `.test-btn` 스타일 교체 |

---

## 리스크 및 고려사항

| 리스크 | 수준 | 대응 |
|--------|------|------|
| 수집 중이 아닐 때 Test 클릭 | LOW | `Not collecting` 에러 처리 → "Fail" 표시 |
| `.click()`이 페이지 이동을 유발할 수 있음 | MEDIUM | 사용자가 인지하고 사용해야 함 (의도된 동작) |
| XPath 셀렉터의 `.click()` 지원 | LOW | `document.evaluate`로 찾은 요소도 `.click()` 가능 |
| 텍스트 박스 클릭 복사 기능 유지 | NONE | 기존 code 요소 클릭 복사는 그대로 유지 |

---

## 예상 복잡도: LOW

4개 파일에 소규모 변경. 기존 `VALIDATE_SELECTOR` 패턴을 거의 그대로 재사용하므로 구현이 간단하다.

---

## 🎉 구현 완료 요약

### 실제 구현된 내용

#### 1. Test 버튼 기능 (2026-02-08)
- ✅ Copy 버튼 → Test 버튼으로 교체
- ✅ 셀렉터로 요소를 찾아 실제 `.click()` 실행
- ✅ 오렌지색 아웃라인 시각 피드백 (500ms)
- ✅ 로딩(…) → 성공(OK!) / 실패(Fail) / 오류(Err) 상태 표시
- ✅ 색상 피드백: 성공 (녹색), 실패/오류 (빨간색)
- ✅ 1.5초 후 자동 리셋

#### 2. 수집 중지 후 Test 가능 기능
- ✅ `lastTabId` 저장 및 조회
- ✅ `collectingTabId` 없을 때 `lastTabId` fallback
- ✅ 탭 종료 시 `lastTabId` 정리

#### 3. Programmatic Click 간섭 방지
- ✅ `testClickInProgress` 플래그 추가
- ✅ `handleClick`에서 플래그 확인하여 무시
- ✅ `try/finally + setTimeout` 패턴으로 안전한 플래그 관리

#### 4. Chrome Extension 메시지 프로토콜 수정
- ✅ `content.js` 메시지 리스너에 `return true` 추가
- ✅ PING, VALIDATE_SELECTOR, TEST_CLICK_SELECTOR 모두 응답 채널 유지
- ✅ 메시지 응답이 undefined가 되지 않도록 수정 (BUG FIX)

#### 5. 유효성 아이콘 토글 기능 (2026-02-08)
- ✅ ✓/✗ 아이콘 클릭으로 검증 상태 수동 변경
- ✅ 클래스 토글 (`valid` ↔ `invalid`)
- ✅ 텍스트 변경 ("✓" ↔ "✗")
- ✅ hover 시 scale 1.25 애니메이션
- ✅ 커서 pointer로 변경

### 수정 파일 및 커밋

| 파일 | 변경 | 커밋 |
|------|------|------|
| `content.js` | `TEST_CLICK_SELECTOR` 핸들러, `testClickInProgress` 플래그, `return true` 추가 | 075a990 |
| `background.js` | `TEST_CLICK_SELECTOR` 라우팅, `getLastTabId/setLastTabId` 함수 | 075a990 |
| `sidepanel.js` | Test 버튼 UI, 이벤트 핸들러, 유효성 아이콘 토글 | 075a990 + 39eaace |
| `sidepanel.css` | `.test-btn` 스타일, `.test-success/.test-fail`, `.validation-icon:hover` | 075a990 + 39eaace |

### 총 2개 커밋
1. **075a990**: Copy 버튼을 Test 버튼으로 교체 + 수집 중지 후 테스트 가능 + 메시지 응답 채널 수정
2. **39eaace**: 유효성 아이콘 토글 기능 추가

### 발견된 버그 및 수정

| 버그 | 원인 | 수정 |
|------|------|------|
| Test 항상 Fail | `content.js` 메시지 리스너가 `return true`를 하지 않아 응답 채널 미유지 | `sendResponse` 후 `return true` 추가 |
| 수집 중지 후 Test 실패 | `getCollectingTabId()`만 사용하여 수집 중지 시 tabId가 null | `getLastTabId()` 추가 및 fallback 로직 |
| Test 중 `handleClick` 간섭 | `element.click()` 이벤트가 `handleClick`에 의해 감지/재수집됨 | `testClickInProgress` 플래그로 방지 |

### 테스트 결과
✅ Test 버튼: 수집 중/중지 후 모두 정상 동작
✅ 유효성 토글: ✓/✗ 클릭으로 즉시 변경
✅ 시각 피드백: 성공/실패 색상 올바르게 표시
✅ 복사 기능: 텍스트 박스 클릭으로 복사 유지

---

**마지막 업데이트**: 2026-02-08
