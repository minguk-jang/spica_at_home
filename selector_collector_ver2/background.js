// background.js

// ------------------------------------------------------------------------
// Configuration & State
// ------------------------------------------------------------------------

const STORAGE_KEY_COLLECTING_TAB = 'collectingTabId';
const STORAGE_KEY_LAST_TAB = 'lastCollectedTabId';

// Enable side panel to open on action click
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });

// ------------------------------------------------------------------------
// Helpers
// ------------------------------------------------------------------------

async function getCollectingTabId() {
    const result = await chrome.storage.local.get(STORAGE_KEY_COLLECTING_TAB);
    return result[STORAGE_KEY_COLLECTING_TAB] || null;
}

async function setCollectingTabId(tabId) {
    if (tabId === null) {
        await chrome.storage.local.remove(STORAGE_KEY_COLLECTING_TAB);
    } else {
        await chrome.storage.local.set({ [STORAGE_KEY_COLLECTING_TAB]: tabId });
    }
}

async function getLastTabId() {
    const result = await chrome.storage.local.get(STORAGE_KEY_LAST_TAB);
    return result[STORAGE_KEY_LAST_TAB] || null;
}

async function setLastTabId(tabId) {
    if (tabId === null) {
        await chrome.storage.local.remove(STORAGE_KEY_LAST_TAB);
    } else {
        await chrome.storage.local.set({ [STORAGE_KEY_LAST_TAB]: tabId });
    }
}

async function ensureContentScript(tabId) {
    try {
        await chrome.tabs.sendMessage(tabId, { type: 'PING' });
    } catch (e) {
        // Content script not ready, inject it
        await chrome.scripting.executeScript({
            target: { tabId },
            files: ['selector-core.js', 'content.js']
        });
    }
}

async function notifySidePanel(type, data = {}) {
    // Send message to sidepanel (and other extension parts)
    // Sidepanel will listen to runtime messages
    try {
        await chrome.runtime.sendMessage({ type, data });
    } catch (e) {
        // Sidepanel might be closed, ignore
    }
}

// ------------------------------------------------------------------------
// Message Handling
// ------------------------------------------------------------------------

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    // 1. Handle messages from Content Script
    if (sender.tab) {
        if (message.type === 'SELECTORS_COLLECTED') {
            // Forward to sidepanel
            // We use the same type, sidepanel receives it.
            // Note: Sidepanel receives messages from content script directly too.
            // But per plan, we forward it.
            // To avoid duplicates in sidepanel, we might need a flag, 
            // or we assume sidepanel handles it. 
            // We'll send it as is.
            chrome.runtime.sendMessage(message);
        }
        return;
    }

    // 2. Handle messages from Sidepanel / Popup
    if (message.type === 'START_COLLECTING') {
        (async () => {
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            if (!tab) return;

            // Stop collecting in previous tab if any
            const prevTabId = await getCollectingTabId();
            if (prevTabId && prevTabId !== tab.id) {
                try {
                    await chrome.tabs.sendMessage(prevTabId, { type: 'STOP_COLLECTING' });
                } catch (e) { /* ignore */ }
            }

            // Start in current tab
            await ensureContentScript(tab.id);
            await chrome.tabs.sendMessage(tab.id, { type: 'START_COLLECTING' });
            await setCollectingTabId(tab.id);
            await setLastTabId(tab.id);
        })();
    }

    else if (message.type === 'STOP_COLLECTING') {
        (async () => {
            const tabId = await getCollectingTabId();
            if (tabId) {
                try {
                    await chrome.tabs.sendMessage(tabId, { type: 'STOP_COLLECTING' });
                } catch (e) { /* ignore */ }
                await setCollectingTabId(null);
            }
        })();
    }

    else if (message.type === 'GET_COLLECTING_STATE') {
        (async () => {
            const tabId = await getCollectingTabId();
            // We might want to check if the tab still exists/is valid
            if (tabId) {
                try {
                    await chrome.tabs.get(tabId);
                    sendResponse({ collecting: true, tabId });
                } catch (e) {
                    await setCollectingTabId(null);
                    sendResponse({ collecting: false });
                }
            } else {
                sendResponse({ collecting: false });
            }
        })();
        return true; // Keep channel open for async response
    }

    else if (message.type === 'TEST_CLICK_SELECTOR') {
        (async () => {
            let tabId = await getCollectingTabId();
            if (!tabId) tabId = await getLastTabId();
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

    else if (message.type === 'VALIDATE_SELECTOR') {
        // Sidepanel -> Content Script
        (async () => {
            const tabId = await getCollectingTabId();
            if (tabId) {
                try {
                    const response = await chrome.tabs.sendMessage(tabId, message);
                    sendResponse(response);
                } catch (e) {
                    sendResponse({ valid: false, error: e.message });
                }
            } else {
                sendResponse({ valid: false, error: 'Not collecting' });
            }
        })();
        return true;
    }
});

// ------------------------------------------------------------------------
// Tab Events
// ------------------------------------------------------------------------

chrome.tabs.onRemoved.addListener(async (tabId) => {
    const collectingTabId = await getCollectingTabId();
    const lastTabId = await getLastTabId();

    if (collectingTabId === tabId) {
        await setCollectingTabId(null);
        notifySidePanel('STOPPED_BY_TAB_CLOSE');
        notifySidePanel('COLLECTING_STATE_CHANGED', { collecting: false });
    }

    if (lastTabId === tabId) {
        await setLastTabId(null);
    }
});

chrome.tabs.onActivated.addListener(async (activeInfo) => {
    const collectingTabId = await getCollectingTabId();
    // If we switched tabs, the sidepanel (if open) might want to know 
    // if the NEW tab is the collecting one or not.
    // The sidepanel UI "Start/Stop" button reflects the GLOBAL state (one tab collecting).
    // So if we switch to another tab, the collection is still active in the *other* tab.
    // The user might want to know that.
    
    // However, usually "Start Collecting" works on *current* tab.
    // If I switch to Tab B, should the button say "Stop Collecting" (meaning stop Tab A)?
    // Or "Start Collecting" (meaning start Tab B)?
    
    // Plan: "chrome.tabs.onActivated -> 탭 전환 시 사이드패널에 상태 동기화"
    // If collectingTabId matches activeInfo.tabId, then we are viewing the collecting tab.
    // If not, we are viewing a non-collecting tab.
    
    // But the button in sidepanel is global toggle?
    // "toggleBtn ... if (collecting) ... STOP ... else ... START"
    // It seems the sidepanel assumes a single global collecting state.
    // So if ANY tab is collecting, the UI shows "Stop".
    // This implies we don't need to do much on Activated unless we want to highlight "You are not on the collecting tab".
    // But the plan implies "status-dot" or text might change?
    
    // Let's just notify sidepanel to re-check state.
    notifySidePanel('TAB_SWITCHED', { activeTabId: activeInfo.tabId });
});
