(() => {
    let collecting = false;
    let testClickInProgress = false;
    let lastHighlighted = null;
    let statusBar = null;
    let styleElement = null;

    // ------------------------------------------------------------------------
    // UI Helpers
    // ------------------------------------------------------------------------

    function injectStyles() {
        if (document.getElementById('sc-styles')) return;
        
        const css = `
            .__sc-status-bar {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 3px;
                z-index: 2147483647;
                background: linear-gradient(90deg, #58a6ff, #238636, #58a6ff);
                background-size: 200% 100%;
                animation: sc-gradient 2s linear infinite;
                pointer-events: none;
            }
            @keyframes sc-gradient {
                0% { background-position: 100% 0; }
                100% { background-position: -100% 0; }
            }
            .__sc-highlight {
                outline: 3px solid #58a6ff !important;
                outline-offset: 2px;
            }
            .__sc-highlight-pulse {
                outline: 3px solid #f78166 !important;
                outline-offset: 2px;
                animation: sc-pulse 0.5s ease-in-out 3;
            }
            @keyframes sc-pulse {
                0%, 100% { outline-color: #f78166; }
                50% { outline-color: transparent; }
            }
        `;
        
        styleElement = document.createElement('style');
        styleElement.id = 'sc-styles';
        styleElement.textContent = css;
        document.head.appendChild(styleElement);
    }

    function removeStyles() {
        if (styleElement) {
            styleElement.remove();
            styleElement = null;
        }
    }

    function createStatusBar() {
        if (document.querySelector('.__sc-status-bar')) return;
        
        statusBar = document.createElement('div');
        statusBar.className = '__sc-status-bar';
        document.body.appendChild(statusBar);
    }

    function removeStatusBar() {
        if (statusBar) {
            statusBar.remove();
            statusBar = null;
        }
    }

    function clearHighlight() {
        if (lastHighlighted) {
            lastHighlighted.classList.remove('__sc-highlight');
            lastHighlighted = null;
        }
    }

    function removeHighlightPulse() {
        const prev = document.querySelector('.__sc-highlight-pulse');
        if (prev) prev.classList.remove('__sc-highlight-pulse');
    }

    // ------------------------------------------------------------------------
    // Event Handlers
    // ------------------------------------------------------------------------

    function handleClick(e) {
        if (!collecting) return;
        // Ignore programmatic clicks from Test button
        if (testClickInProgress) return;
        // Ignore clicks on our own UI
        if (e.target.closest('.__sc-status-bar')) return;

        e.preventDefault();
        e.stopPropagation();

        clearHighlight();

        e.target.classList.add('__sc-highlight');
        lastHighlighted = e.target;

        if (!window.SelectorCore) {
            console.error('SelectorCore not loaded');
            return;
        }

        const selectors = window.SelectorCore.getAllSelectors(e.target);
        const validation = window.SelectorCore.validateAllSelectors(selectors, e.target);

        const elementInfo = {
            tagName: e.target.tagName.toLowerCase(),
            id: e.target.id || '',
            className: (typeof e.target.className === 'string') ? e.target.className : '',
            textContent: (e.target.textContent || '').trim().slice(0, 50),
            url: window.location.href,
            timestamp: new Date().toISOString()
        };

        chrome.runtime.sendMessage({
            type: 'SELECTORS_COLLECTED',
            data: { selectors, validation, elementInfo }
        }).catch(err => {
            // Ignore errors if sidepanel is closed or not listening
            // console.debug('Message send failed', err);
        });
    }

    // ------------------------------------------------------------------------
    // Message Listener
    // ------------------------------------------------------------------------

    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
        switch (message.type) {
            case 'PING':
                sendResponse({ alive: true });
                return true;

            case 'START_COLLECTING':
                collecting = true;
                injectStyles();
                createStatusBar();
                document.addEventListener('click', handleClick, true);
                break;

            case 'STOP_COLLECTING':
                collecting = false;
                document.removeEventListener('click', handleClick, true);
                clearHighlight();
                removeStatusBar();
                break;

            case 'VALIDATE_SELECTOR': {
                const { selector, isXPath } = message.data;
                let valid = false;
                try {
                    if (isXPath) {
                        const result = document.evaluate(
                            selector,
                            document,
                            null,
                            XPathResult.FIRST_ORDERED_NODE_TYPE,
                            null
                        );
                        valid = !!result.singleNodeValue;
                    } else {
                        valid = !!document.querySelector(selector);
                    }
                } catch (e) {
                    valid = false;
                }
                sendResponse({ valid });
                return true;
            }

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
                        const originalOutline = element.style.outline;
                        const originalTransition = element.style.transition;

                        element.style.transition = 'outline 0.2s';
                        element.style.outline = '3px solid #f0883e';

                        setTimeout(() => {
                            element.style.outline = originalOutline;
                            element.style.transition = originalTransition;
                        }, 500);

                        testClickInProgress = true;
                        try {
                            element.click();
                        } finally {
                            setTimeout(() => { testClickInProgress = false; }, 0);
                        }
                        sendResponse({ success: true });
                    } else {
                        sendResponse({ success: false, error: 'Element not found' });
                    }
                } catch (e) {
                    testClickInProgress = false;
                    sendResponse({ success: false, error: e.message });
                }
                return true;
            }

            case 'HIGHLIGHT_ELEMENT': {
                injectStyles();
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
        }
    });

})();
