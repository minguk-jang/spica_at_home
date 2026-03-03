// sidepanel.js

let collecting = false;
let history = [];
let lastProcessedTimestamp = null;

// UI Elements
const statusDot = document.getElementById('statusDot');
const statusText = document.getElementById('statusText');
const toggleBtn = document.getElementById('toggleBtn');
const savBtn = document.getElementById('savBtn');
const dirBtn = document.getElementById('dirBtn');
const footerStatus = document.getElementById('footerStatus');

// Theme Toggle
const themeToggle = document.getElementById('themeToggle');
function initTheme() {
    const stored = localStorage.getItem('sc-theme');
    const theme = stored || 'dark';
    document.documentElement.setAttribute('data-theme', theme);
}
initTheme();

if (themeToggle) {
    themeToggle.addEventListener('click', () => {
        const html = document.documentElement;
        html.classList.add('theme-transitioning');
        const current = html.getAttribute('data-theme');
        const next = current === 'dark' ? 'light' : 'dark';
        html.setAttribute('data-theme', next);
        localStorage.setItem('sc-theme', next);
        setTimeout(() => html.classList.remove('theme-transitioning'), 350);
    });
}

const elementCard = document.getElementById('elementCard');
const elTag = document.getElementById('elTag');
const elId = document.getElementById('elId');
const elClass = document.getElementById('elClass');
const elUrl = document.getElementById('elUrl');

const selectorsGrid = document.getElementById('selectorsGrid');

const historyPanel = document.getElementById('historyPanel');
const historyList = document.getElementById('historyList');
const historyCount = document.getElementById('historyCount');
const exportBtn = document.getElementById('exportBtn');
const clearHistoryBtn = document.getElementById('clearHistoryBtn');

// Modal Elements
const saveModal = document.getElementById('saveModal');
const closeModalBtn = document.getElementById('closeModalBtn');
const cancelSaveBtn = document.getElementById('cancelSaveBtn');
const confirmSaveBtn = document.getElementById('confirmSaveBtn');
const saveNameInput = document.getElementById('saveNameInput');
const summaryTotal = document.getElementById('summaryTotal');
const summaryUrls = document.getElementById('summaryUrls');
const summaryTags = document.getElementById('summaryTags');

// ------------------------------------------------------------------------
// Initialization
// ------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', async () => {
    // 1. Load History
    loadHistoryFromStorage();

    // 2. Restore Directory Handle
    const hasHandle = await FsStorage.restoreHandle();
    if (hasHandle) {
        footerStatus.textContent = '디렉토리 설정됨';
        updateSaveButton();
    }

    // 3. Check Collecting State
    chrome.runtime.sendMessage({ type: 'GET_COLLECTING_STATE' }, (response) => {
        if (chrome.runtime.lastError) return; // Background might be asleep
        if (response && response.collecting) {
            setCollectingUI(true);
            collecting = true;
        }
    });
});

// ------------------------------------------------------------------------
// UI Updates
// ------------------------------------------------------------------------

function setCollectingUI(active) {
    collecting = active;
    toggleBtn.textContent = active ? 'Stop Collecting' : 'Start Collecting';
    toggleBtn.classList.toggle('collecting', active);
    statusDot.classList.toggle('active', active);
    statusText.textContent = active ? '수집 중...' : '대기 중';
}

function updateSaveButton() {
    savBtn.disabled = history.length === 0 || !FsStorage.isReady();
}

function displayElementInfo(info) {
    elementCard.style.display = 'block';
    elTag.textContent = `<${info.tagName}>`;
    elId.textContent = info.id ? `#${info.id}` : '';
    elClass.textContent = info.className ? `.${info.className.replace(/\s+/g, '.')}` : '';
    elUrl.textContent = info.url;
}

function displaySelectors(selectors, validation) {
    selectorsGrid.innerHTML = '';
    
    // Order of display
    const order = ['id', 'classes', 'tag'];
    // Add attributes
    Object.keys(selectors).forEach(key => {
        if (key.startsWith('[')) order.push(key);
    });
    order.push('nthOfType', 'fullCssPath', 'xpath', 'textXpath');

    let hasContent = false;

    order.forEach(key => {
        const value = selectors[key];
        if (!value) return;
        hasContent = true;

        const isValid = validation[key];
        const row = document.createElement('div');
        row.className = 'selector-row';

        // Label
        const label = document.createElement('span');
        label.className = 'selector-label';
        // Pretty print label
        label.textContent = key === 'nthOfType' ? 'nth-of-type' : 
                            key === 'fullCssPath' ? 'CSS Path' : 
                            key === 'textXpath' ? 'Text XPath' : 
                            key === 'classes' ? 'Class' :
                            key === 'tag' ? 'Tag' :
                            key === 'xpath' ? 'XPath' :
                            key === 'id' ? 'ID' : key;
        
        // Value
        const code = document.createElement('code');
        code.className = 'selector-value';
        code.textContent = value;
        code.title = '클릭하여 복사';
        code.addEventListener('click', () => copyToClipboard(value, code));

        // Validation Icon (clickable toggle)
        const icon = document.createElement('span');
        icon.className = `validation-icon ${isValid ? 'valid' : 'invalid'}`;
        icon.textContent = isValid ? '✓' : '✗';
        icon.title = '클릭하여 전환';
        icon.addEventListener('click', () => {
            const wasValid = icon.classList.contains('valid');
            icon.classList.toggle('valid', !wasValid);
            icon.classList.toggle('invalid', wasValid);
            icon.textContent = wasValid ? '✗' : '✓';
        });

        // Test Button
        const testBtn = document.createElement('button');
        testBtn.className = 'test-btn';
        testBtn.textContent = 'Test';
        testBtn.dataset.selector = value;
        testBtn.dataset.isXpath = (key === 'xpath' || key === 'textXpath') ? 'true' : 'false';
        
        row.appendChild(label);
        row.appendChild(code);
        row.appendChild(icon);
        row.appendChild(testBtn);

        selectorsGrid.appendChild(row);
    });

    if (!hasContent) {
        selectorsGrid.innerHTML = '<div class="empty-state"><div class="empty-state-icon">&mdash;</div><div class="empty-state-text">셀렉터 없음</div></div>';
    }
}

async function copyToClipboard(text, triggerElement) {
    try {
        await navigator.clipboard.writeText(text);
        
        // Visual feedback
        if (triggerElement.tagName === 'BUTTON') {
            triggerElement.textContent = 'Copied!';
            setTimeout(() => triggerElement.textContent = 'Copy', 1500);
        } else {
            // Flash effect for code element
            const originalBg = triggerElement.style.background;
            triggerElement.style.background = 'var(--accent)';
            triggerElement.style.color = '#fff';
            setTimeout(() => {
                triggerElement.style.background = originalBg;
                triggerElement.style.color = '';
            }, 200);
        }
    } catch (err) {
        console.error('Copy failed', err);
    }
}

// ------------------------------------------------------------------------
// History Management
// ------------------------------------------------------------------------

function addToHistory(entry) {
    // Deduplication check
    if (lastProcessedTimestamp === entry.elementInfo.timestamp) return;
    lastProcessedTimestamp = entry.elementInfo.timestamp;

    history.unshift(entry);
    if (history.length > 100) history.pop();
    
    updateHistoryUI();
    saveHistoryToStorage();
    updateSaveButton();
}

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

function updateHistoryUI() {
    historyCount.textContent = history.length;
    historyList.innerHTML = '';

    history.forEach((entry, index) => {
        const div = document.createElement('div');
        div.className = 'history-item';
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

        const tag = document.createElement('div');
        tag.className = 'history-item-tag';
        tag.textContent = `<${entry.elementInfo.tagName}>`;

        const detail = document.createElement('div');
        detail.className = 'history-item-detail';
        const idStr = entry.elementInfo.id ? `#${entry.elementInfo.id}` : '';
        const classStr = entry.elementInfo.className ? `.${entry.elementInfo.className.split(' ')[0]}` : ''; // Show first class only
        detail.textContent = `${idStr}${classStr} ${entry.elementInfo.textContent}`;

        const time = document.createElement('div');
        time.className = 'history-time';
        const date = new Date(entry.elementInfo.timestamp);
        time.textContent = date.toLocaleTimeString();

        div.appendChild(time); // Float right, so append first or handle with flex
        div.appendChild(tag);
        div.appendChild(detail);
        
        historyList.appendChild(div);
    });
}

function saveHistoryToStorage() {
    chrome.storage.local.set({ selectorHistory: history });
}

function loadHistoryFromStorage() {
    chrome.storage.local.get('selectorHistory', (result) => {
        if (result.selectorHistory) {
            history = result.selectorHistory;
            updateHistoryUI();
            updateSaveButton();
        }
    });
}

// ------------------------------------------------------------------------
// Event Listeners
// ------------------------------------------------------------------------

// Toggle Start/Stop
toggleBtn.addEventListener('click', async () => {
    if (collecting) {
        chrome.runtime.sendMessage({ type: 'STOP_COLLECTING' });
        setCollectingUI(false);
    } else {
        chrome.runtime.sendMessage({ type: 'START_COLLECTING' });
        setCollectingUI(true);
    }
});

// Set Directory
dirBtn.addEventListener('click', async () => {
    try {
        const selected = await FsStorage.selectDirectory();
        if (selected) {
            footerStatus.textContent = '디렉토리 설정됨';
            updateSaveButton();
        }
    } catch (err) {
        footerStatus.textContent = `오류: ${err.message}`;
    }
});

// Save JSON
savBtn.addEventListener('click', () => {
    if (history.length === 0) return;
    openSaveModal();
});

// Modal Logic
function openSaveModal() {
    saveModal.style.display = 'flex';
    saveNameInput.value = '';
    saveNameInput.focus();
    
    // Calculate Summary
    const summary = calculateSummary(history);
    
    summaryTotal.textContent = `${summary.totalEntries}개`;
    
    summaryUrls.innerHTML = '';
    summary.urls.forEach(url => {
        const div = document.createElement('div');
        div.className = 'summary-url-item';
        div.textContent = url;
        div.title = url;
        summaryUrls.appendChild(div);
    });
    
    const tags = Object.entries(summary.tagCounts)
        .map(([tag, count]) => `${tag}(${count})`)
        .join(', ');
    summaryTags.textContent = tags || '-';
}

function closeSaveModal() {
    saveModal.style.display = 'none';
}

function calculateSummary(historyData) {
    const urls = [...new Set(historyData.map(e => e.elementInfo?.url).filter(Boolean))];
    const tagCounts = {};
    historyData.forEach(e => {
        const tag = e.elementInfo?.tagName || 'UNKNOWN';
        tagCounts[tag] = (tagCounts[tag] || 0) + 1;
    });
    return { totalEntries: historyData.length, urls, tagCounts };
}

// Modal Event Listeners
closeModalBtn.addEventListener('click', closeSaveModal);
cancelSaveBtn.addEventListener('click', closeSaveModal);

saveNameInput.addEventListener('input', () => {
    const value = saveNameInput.value;
    const isValid = /^[a-zA-Z0-9-]*$/.test(value);
    
    if (!isValid) {
        saveNameInput.classList.add('invalid');
        // Remove invalid characters immediately
        saveNameInput.value = value.replace(/[^a-zA-Z0-9-]/g, '');
    } else {
        saveNameInput.classList.remove('invalid');
    }
});

saveNameInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
        confirmSaveBtn.click();
    } else if (e.key === 'Escape') {
        closeSaveModal();
    }
});

// Confirm Save
confirmSaveBtn.addEventListener('click', async () => {
    const name = saveNameInput.value.trim();
    // Validate again just in case
    if (name && !/^[a-zA-Z0-9-]+$/.test(name)) {
        alert('이름에는 영문, 숫자, 하이픈(-)만 사용할 수 있습니다.');
        return;
    }

    const timestamp = new Date();
    const timestampStr = timestamp.toISOString().replace(/[:.]/g, '-').slice(0, 19);
    
    let filename;
    if (name) {
        filename = `selectors-${name}-${timestampStr}.json`;
    } else {
        filename = `selectors-${timestampStr}.json`;
    }

    const data = {
        name: name || null,
        exportedAt: timestamp.toISOString(),
        totalEntries: history.length,
        entries: history
    };

    try {
        await FsStorage.saveJson(filename, data);
        footerStatus.textContent = `저장됨: ${filename}`;
        closeSaveModal();
        setTimeout(() => footerStatus.textContent = '준비됨', 3000);
    } catch (err) {
        alert(`저장 실패: ${err.message}`);
    }
});

// Close modal on outside click
saveModal.addEventListener('click', (e) => {
    if (e.target === saveModal) {
        closeSaveModal();
    }
});

// Export JSON (Download)
exportBtn.addEventListener('click', (e) => {
    e.stopPropagation(); // Don't collapse details
    if (history.length === 0) return;

    const data = {
        exportedAt: new Date().toISOString(),
        totalEntries: history.length,
        entries: history
    };
    
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `selectors-export-${new Date().toISOString().slice(0,10)}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
});

// Clear History
clearHistoryBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    if (confirm('히스토리를 모두 삭제하시겠습니까?')) {
        history = [];
        updateHistoryUI();
        saveHistoryToStorage();
        updateSaveButton();
        selectorsGrid.innerHTML = '<div class="empty-state"><div class="empty-state-icon">&lt;/&gt;</div><div class="empty-state-text">삭제됨</div></div>';
        elementCard.style.display = 'none';
    }
});

// Test Button Delegate
selectorsGrid.addEventListener('click', async (e) => {
    const testBtn = e.target.closest('.test-btn');
    if (!testBtn || testBtn.disabled) return;

    const selector = testBtn.dataset.selector;
    const isXPath = testBtn.dataset.isXpath === 'true';

    // UI Feedback: Loading
    testBtn.textContent = '...';
    testBtn.disabled = true;
    testBtn.classList.remove('test-success', 'test-fail');

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
            console.warn('Test click failed:', response ? response.error : 'Unknown error');
        }
    } catch (err) {
        testBtn.textContent = 'Err';
        testBtn.classList.add('test-fail');
        console.error('Test click error:', err);
    }

    // Reset after delay
    setTimeout(() => {
        if (testBtn.isConnected) {
            testBtn.textContent = 'Test';
            testBtn.disabled = false;
            testBtn.classList.remove('test-success', 'test-fail');
        }
    }, 1500);
});

// Dashboard Button
const dashboardBtn = document.getElementById('dashboardBtn');
if (dashboardBtn) {
    dashboardBtn.addEventListener('click', () => {
        chrome.tabs.create({ url: 'dashboard.html' });
    });
}

// Message Listener
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === 'SELECTORS_COLLECTED') {
        const { selectors, validation, elementInfo } = message.data;
        displayElementInfo(elementInfo);
        displaySelectors(selectors, validation);
        addToHistory({ selectors, validation, elementInfo });
    }
    else if (message.type === 'STOPPED_BY_TAB_CLOSE' || (message.type === 'COLLECTING_STATE_CHANGED' && !message.data.collecting)) {
        setCollectingUI(false);
    }
});
