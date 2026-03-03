<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Selector Collector Tool</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0d1117;
            color: #c9d1d9;
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
        }

        h1 {
            font-size: 1.8rem;
            margin-bottom: 8px;
            color: #58a6ff;
        }

        .subtitle {
            color: #8b949e;
            margin-bottom: 24px;
        }

        .tabs {
            display: flex;
            gap: 8px;
            margin-bottom: 20px;
        }

        .tab {
            padding: 10px 20px;
            background: #21262d;
            border: 1px solid #30363d;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.2s;
        }

        .tab:hover {
            background: #30363d;
        }

        .tab.active {
            background: #238636;
            border-color: #238636;
        }

        .panel {
            display: none;
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 20px;
        }

        .panel.active {
            display: block;
        }

        /* Bookmarklet Section */
        .bookmarklet-section {
            margin-bottom: 24px;
        }

        .bookmarklet-btn {
            display: inline-block;
            padding: 12px 24px;
            background: linear-gradient(135deg, #238636 0%, #2ea043 100%);
            color: white;
            text-decoration: none;
            border-radius: 6px;
            font-weight: 600;
            cursor: grab;
            transition: transform 0.2s;
        }

        .bookmarklet-btn:hover {
            transform: scale(1.02);
        }

        .instructions {
            background: #21262d;
            border-radius: 6px;
            padding: 16px;
            margin-top: 16px;
        }

        .instructions h3 {
            color: #58a6ff;
            margin-bottom: 12px;
            font-size: 1rem;
        }

        .instructions ol {
            padding-left: 20px;
            line-height: 1.8;
        }

        .instructions code {
            background: #30363d;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Fira Code', monospace;
        }

        /* Console Script Section */
        .code-block {
            position: relative;
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 6px;
            overflow: hidden;
        }

        .code-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 12px;
            background: #21262d;
            border-bottom: 1px solid #30363d;
        }

        .code-lang {
            color: #8b949e;
            font-size: 0.85rem;
        }

        .copy-btn {
            padding: 6px 12px;
            background: #30363d;
            border: 1px solid #484f58;
            border-radius: 4px;
            color: #c9d1d9;
            cursor: pointer;
            font-size: 0.85rem;
            transition: all 0.2s;
        }

        .copy-btn:hover {
            background: #484f58;
        }

        .copy-btn.copied {
            background: #238636;
            border-color: #238636;
        }

        .code-content {
            padding: 16px;
            overflow-x: auto;
            max-height: 500px;
            overflow-y: auto;
        }

        .code-content pre {
            font-family: 'Fira Code', Consolas, monospace;
            font-size: 0.9rem;
            line-height: 1.5;
            color: #c9d1d9;
            white-space: pre;
        }

        /* Demo Section */
        .demo-area {
            background: #21262d;
            border-radius: 8px;
            padding: 20px;
            margin-top: 20px;
        }

        .demo-area h3 {
            color: #58a6ff;
            margin-bottom: 16px;
        }

        .demo-elements {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
        }

        .demo-btn {
            padding: 12px 20px;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.2s;
        }

        .demo-btn-1 {
            background: #238636;
            border: none;
            color: white;
        }

        .demo-btn-2 {
            background: transparent;
            border: 2px solid #58a6ff;
            color: #58a6ff;
        }

        .demo-link {
            color: #58a6ff;
            text-decoration: underline;
            padding: 12px 0;
            display: inline-block;
        }

        .demo-input {
            padding: 12px;
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 6px;
            color: #c9d1d9;
            width: 100%;
        }

        .demo-card {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 16px;
        }

        /* Collected Selectors Display */
        .selectors-panel {
            position: fixed;
            bottom: 20px;
            right: 20px;
            width: 450px;
            max-height: 70vh;
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 12px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
            z-index: 10000;
            display: none;
            flex-direction: column;
        }

        .selectors-panel.show {
            display: flex;
        }

        .selectors-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 16px;
            background: #21262d;
            border-bottom: 1px solid #30363d;
            border-radius: 12px 12px 0 0;
        }

        .selectors-header h4 {
            color: #58a6ff;
            font-size: 0.95rem;
        }

        .close-panel {
            background: none;
            border: none;
            color: #8b949e;
            cursor: pointer;
            font-size: 1.2rem;
        }

        .selectors-body {
            flex: 1;
            overflow-y: auto;
            padding: 12px;
        }

        .selector-group {
            margin-bottom: 12px;
        }

        .selector-label {
            font-size: 0.75rem;
            color: #8b949e;
            margin-bottom: 4px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .selector-value {
            display: flex;
            align-items: center;
            gap: 8px;
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 4px;
            padding: 8px 10px;
            font-family: 'Fira Code', monospace;
            font-size: 0.85rem;
            word-break: break-all;
        }

        .selector-value code {
            flex: 1;
            color: #7ee787;
        }

        .selector-copy {
            background: none;
            border: none;
            color: #8b949e;
            cursor: pointer;
            padding: 4px;
            flex-shrink: 0;
        }

        .selector-copy:hover {
            color: #58a6ff;
        }

        .history-section {
            border-top: 1px solid #30363d;
            padding: 12px;
            max-height: 200px;
            overflow-y: auto;
        }

        .history-item {
            padding: 8px;
            background: #21262d;
            border-radius: 4px;
            margin-bottom: 8px;
            font-size: 0.8rem;
            cursor: pointer;
            transition: background 0.2s;
        }

        .history-item:hover {
            background: #30363d;
        }

        .history-tag {
            color: #f0883e;
        }

        .clear-history {
            width: 100%;
            padding: 8px;
            background: #21262d;
            border: 1px solid #30363d;
            border-radius: 4px;
            color: #f85149;
            cursor: pointer;
            margin-top: 8px;
        }

        .clear-history:hover {
            background: #f8514922;
        }

        /* Highlight effect */
        .selector-highlight {
            outline: 3px solid #58a6ff !important;
            outline-offset: 2px;
            animation: pulse 1s ease-in-out;
        }

        @keyframes pulse {
            0%, 100% { outline-color: #58a6ff; }
            50% { outline-color: #f0883e; }
        }

        /* Status indicator */
        .status-bar {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 10px 16px;
            background: #238636;
            color: white;
            border-radius: 6px;
            font-size: 0.9rem;
            z-index: 10001;
            display: none;
        }

        .status-bar.active {
            display: block;
            animation: fadeIn 0.3s;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎯 Selector Collector</h1>
        <p class="subtitle">클릭한 요소의 모든 가능한 CSS 셀렉터를 수집합니다</p>

        <div class="tabs">
            <div class="tab active" data-tab="bookmarklet">북마클릿</div>
            <div class="tab" data-tab="console">콘솔 스크립트</div>
            <div class="tab" data-tab="demo">데모</div>
        </div>

        <!-- Bookmarklet Panel -->
        <div class="panel active" id="bookmarklet">
            <div class="bookmarklet-section">
                <p style="margin-bottom: 16px;">아래 버튼을 북마크바로 드래그하세요:</p>
                <a class="bookmarklet-btn" href="javascript:(function(){if(window.selectorCollector){window.selectorCollector.toggle();return;}const style=document.createElement('style');style.textContent=`.sc-highlight{outline:3px solid %2358a6ff!important;outline-offset:2px}.sc-panel{position:fixed;bottom:20px;right:20px;width:420px;max-height:70vh;background:%23161b22;border:1px solid %2330363d;border-radius:12px;box-shadow:0 8px 32px rgba(0,0,0,.4);z-index:2147483647;display:flex;flex-direction:column;font-family:-apple-system,BlinkMacSystemFont,sans-serif;font-size:14px;color:%23c9d1d9}.sc-header{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;background:%2321262d;border-bottom:1px solid %2330363d;border-radius:12px 12px 0 0}.sc-title{color:%2358a6ff;font-weight:600;font-size:14px}.sc-close{background:none;border:none;color:%238b949e;cursor:pointer;font-size:18px;padding:0}.sc-body{flex:1;overflow-y:auto;padding:12px}.sc-group{margin-bottom:10px}.sc-label{font-size:11px;color:%238b949e;margin-bottom:4px;text-transform:uppercase}.sc-value{display:flex;align-items:center;gap:8px;background:%230d1117;border:1px solid %2330363d;border-radius:4px;padding:8px;font-family:monospace;font-size:12px;word-break:break-all}.sc-value code{flex:1;color:%237ee787}.sc-copy{background:none;border:none;color:%238b949e;cursor:pointer;padding:2px}.sc-status{position:fixed;top:20px;right:20px;padding:10px 16px;background:%23238636;color:white;border-radius:6px;font-size:13px;z-index:2147483648;font-family:-apple-system,sans-serif}`;document.head.appendChild(style);const panel=document.createElement('div');panel.className='sc-panel';panel.innerHTML=`<div class='sc-header'><span class='sc-title'>🎯 Selector Collector</span><button class='sc-close'>✕</button></div><div class='sc-body'><p style='color:%238b949e;text-align:center;padding:20px'>요소를 클릭하세요</p></div>`;document.body.appendChild(panel);const status=document.createElement('div');status.className='sc-status';status.textContent='✓ Selector Collector 활성화';document.body.appendChild(status);setTimeout(()=>status.remove(),2000);function getSelectors(el){const s={};if(el.id)s.id='%23'+CSS.escape(el.id);if(el.className&&typeof el.className==='string'){const c=el.className.trim().split(/\\s+/).filter(x=>x);if(c.length)s.classes='.'+c.map(x=>CSS.escape(x)).join('.')}s.tag=el.tagName.toLowerCase();const attrs=['name','type','placeholder','data-testid','data-id','aria-label','role','href','src','alt','title','value'];attrs.forEach(a=>{const v=el.getAttribute(a);if(v)s['['+a+']']=el.tagName.toLowerCase()+'['+a+'=\"'+CSS.escape(v)+'\"]'});const parent=el.parentElement;if(parent){const siblings=[...parent.children].filter(c=>c.tagName===el.tagName);if(siblings.length>1){const idx=siblings.indexOf(el)+1;s.nthChild=el.tagName.toLowerCase()+':nth-child('+idx+')'}}let path=[];let current=el;while(current&&current!==document.body){let selector=current.tagName.toLowerCase();if(current.id){selector='%23'+CSS.escape(current.id);path.unshift(selector);break}else{const p=current.parentElement;if(p){const sibs=[...p.children].filter(c=>c.tagName===current.tagName);if(sibs.length>1)selector+=':nth-child('+(sibs.indexOf(current)+1)+')'}}path.unshift(selector);current=current.parentElement}s.fullPath=path.join(' > ');let xp='';current=el;while(current&&current.nodeType===1){let seg=current.tagName.toLowerCase();if(current.id){seg='//'+seg+'[@id=\"'+current.id+'\"]';xp=seg+xp;break}else{const p=current.parentElement;if(p){const sibs=[...p.children].filter(c=>c.tagName===current.tagName);if(sibs.length>1)seg+='['+(sibs.indexOf(current)+1)+']'}xp='/'+seg+xp;current=current.parentElement}}if(!xp.startsWith('//'))xp='//'+xp.slice(1);s.xpath=xp;const text=el.textContent?.trim().slice(0,30);if(text&&el.children.length===0)s.textContent=`//${el.tagName.toLowerCase()}[contains(text(),'${text}')]`;return s}function showSelectors(el){const selectors=getSelectors(el);let html='';for(const[k,v]of Object.entries(selectors)){html+=`<div class='sc-group'><div class='sc-label'>${k}</div><div class='sc-value'><code>${v}</code><button class='sc-copy' data-value='${v.replace(/'/g,'&apos;')}'>📋</button></div></div>`}panel.querySelector('.sc-body').innerHTML=html;panel.querySelectorAll('.sc-copy').forEach(b=>b.onclick=e=>{e.stopPropagation();navigator.clipboard.writeText(b.dataset.value);b.textContent='✓';setTimeout(()=>b.textContent='📋',1000)})}let active=true;let lastEl=null;function onClick(e){if(!active||panel.contains(e.target))return;e.preventDefault();e.stopPropagation();if(lastEl)lastEl.classList.remove('sc-highlight');e.target.classList.add('sc-highlight');lastEl=e.target;showSelectors(e.target)}document.addEventListener('click',onClick,true);panel.querySelector('.sc-close').onclick=()=>{active=false;panel.remove();if(lastEl)lastEl.classList.remove('sc-highlight');document.removeEventListener('click',onClick,true)};window.selectorCollector={toggle:()=>{active=!active;panel.style.display=active?'flex':'none';if(!active&&lastEl)lastEl.classList.remove('sc-highlight')}}})();">🎯 Selector Collector</a>
            </div>

            <div class="instructions">
                <h3>📖 사용 방법</h3>
                <ol>
                    <li>위의 <strong>🎯 Selector Collector</strong> 버튼을 북마크바로 드래그</li>
                    <li>원하는 웹페이지에서 북마클릿 클릭</li>
                    <li>페이지의 아무 요소나 클릭하면 해당 요소의 모든 셀렉터가 표시됨</li>
                    <li>📋 버튼을 클릭하여 원하는 셀렉터를 복사</li>
                </ol>
            </div>

            <div class="instructions" style="margin-top: 16px;">
                <h3>🔍 수집하는 셀렉터 종류</h3>
                <ul style="padding-left: 20px; line-height: 1.8;">
                    <li><code>#id</code> - ID 셀렉터</li>
                    <li><code>.class1.class2</code> - 클래스 셀렉터</li>
                    <li><code>tag</code> - 태그 셀렉터</li>
                    <li><code>[attribute]</code> - 속성 셀렉터 (name, type, data-*, aria-* 등)</li>
                    <li><code>:nth-child(n)</code> - 순서 기반 셀렉터</li>
                    <li><code>full path</code> - 전체 CSS 경로</li>
                    <li><code>xpath</code> - XPath 표현식</li>
                    <li><code>text content</code> - 텍스트 기반 XPath</li>
                </ul>
            </div>
        </div>

        <!-- Console Script Panel -->
        <div class="panel" id="console">
            <p style="margin-bottom: 16px;">F12 → Console 탭에서 아래 코드를 붙여넣고 실행하세요:</p>
            
            <div class="code-block">
                <div class="code-header">
                    <span class="code-lang">JavaScript</span>
                    <button class="copy-btn" onclick="copyCode()">📋 복사</button>
                </div>
                <div class="code-content">
                    <pre id="console-code">// 🎯 Selector Collector - Console Version
(function() {
    // 이미 실행 중이면 토글
    if (window.selectorCollector) {
        window.selectorCollector.toggle();
        return;
    }

    // 스타일 추가
    const style = document.createElement('style');
    style.id = 'sc-styles';
    style.textContent = `
        .sc-highlight {
            outline: 3px solid #58a6ff !important;
            outline-offset: 2px;
            animation: sc-pulse 1s ease-in-out;
        }
        @keyframes sc-pulse {
            0%, 100% { outline-color: #58a6ff; }
            50% { outline-color: #f0883e; }
        }
        .sc-panel {
            position: fixed;
            bottom: 20px;
            right: 20px;
            width: 450px;
            max-height: 70vh;
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 12px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
            z-index: 2147483647;
            display: flex;
            flex-direction: column;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            font-size: 14px;
            color: #c9d1d9;
        }
        .sc-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 16px;
            background: #21262d;
            border-bottom: 1px solid #30363d;
            border-radius: 12px 12px 0 0;
        }
        .sc-title { color: #58a6ff; font-weight: 600; }
        .sc-close {
            background: none;
            border: none;
            color: #8b949e;
            cursor: pointer;
            font-size: 18px;
            padding: 0;
        }
        .sc-close:hover { color: #f85149; }
        .sc-body {
            flex: 1;
            overflow-y: auto;
            padding: 12px;
        }
        .sc-group { margin-bottom: 10px; }
        .sc-label {
            font-size: 11px;
            color: #8b949e;
            margin-bottom: 4px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .sc-value {
            display: flex;
            align-items: center;
            gap: 8px;
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 4px;
            padding: 8px 10px;
            font-family: 'Fira Code', Consolas, monospace;
            font-size: 12px;
            word-break: break-all;
        }
        .sc-value code { flex: 1; color: #7ee787; }
        .sc-copy {
            background: none;
            border: none;
            color: #8b949e;
            cursor: pointer;
            padding: 2px;
            flex-shrink: 0;
        }
        .sc-copy:hover { color: #58a6ff; }
        .sc-history {
            border-top: 1px solid #30363d;
            padding: 12px;
            max-height: 150px;
            overflow-y: auto;
        }
        .sc-history-title {
            font-size: 11px;
            color: #8b949e;
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .sc-history-clear {
            background: none;
            border: none;
            color: #f85149;
            cursor: pointer;
            font-size: 11px;
        }
        .sc-history-item {
            padding: 6px 8px;
            background: #21262d;
            border-radius: 4px;
            margin-bottom: 6px;
            font-size: 12px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .sc-history-item:hover { background: #30363d; }
        .sc-tag { color: #f0883e; }
        .sc-status {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 10px 16px;
            background: #238636;
            color: white;
            border-radius: 6px;
            font-size: 13px;
            z-index: 2147483648;
            animation: sc-fadeIn 0.3s;
        }
        @keyframes sc-fadeIn {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .sc-export {
            padding: 8px 12px;
            background: #238636;
            border: none;
            border-radius: 4px;
            color: white;
            cursor: pointer;
            font-size: 12px;
            margin-top: 8px;
            width: 100%;
        }
        .sc-export:hover { background: #2ea043; }
    `;
    document.head.appendChild(style);

    // 패널 생성
    const panel = document.createElement('div');
    panel.className = 'sc-panel';
    panel.innerHTML = `
        <div class="sc-header">
            <span class="sc-title">🎯 Selector Collector</span>
            <button class="sc-close">✕</button>
        </div>
        <div class="sc-body">
            <p style="color: #8b949e; text-align: center; padding: 20px;">
                페이지의 요소를 클릭하세요
            </p>
        </div>
        <div class="sc-history">
            <div class="sc-history-title">
                <span>📜 히스토리</span>
                <button class="sc-history-clear">지우기</button>
            </div>
            <div class="sc-history-list"></div>
            <button class="sc-export">📥 JSON으로 내보내기</button>
        </div>
    `;
    document.body.appendChild(panel);

    // 상태 표시
    const status = document.createElement('div');
    status.className = 'sc-status';
    status.textContent = '✓ Selector Collector 활성화됨 - 요소를 클릭하세요';
    document.body.appendChild(status);
    setTimeout(() => status.remove(), 2500);

    // 히스토리 저장
    const history = [];

    // 셀렉터 생성 함수
    function getAllSelectors(element) {
        const selectors = {};

        // 1. ID
        if (element.id) {
            selectors.id = '#' + CSS.escape(element.id);
        }

        // 2. Classes
        if (element.className && typeof element.className === 'string') {
            const classes = element.className.trim().split(/\s+/).filter(c => c && !c.startsWith('sc-'));
            if (classes.length > 0) {
                selectors.classes = '.' + classes.map(c => CSS.escape(c)).join('.');
            }
        }

        // 3. Tag
        selectors.tag = element.tagName.toLowerCase();

        // 4. Attributes
        const importantAttrs = [
            'name', 'type', 'placeholder', 'value',
            'data-testid', 'data-id', 'data-cy', 'data-test',
            'aria-label', 'aria-labelledby', 'role',
            'href', 'src', 'alt', 'title', 'for'
        ];

        importantAttrs.forEach(attr => {
            const value = element.getAttribute(attr);
            if (value) {
                const key = `[${attr}]`;
                selectors[key] = `${element.tagName.toLowerCase()}[${attr}="${CSS.escape(value)}"]`;
            }
        });

        // 5. nth-child
        const parent = element.parentElement;
        if (parent) {
            const siblings = [...parent.children].filter(child => 
                child.tagName === element.tagName
            );
            if (siblings.length > 1) {
                const index = siblings.indexOf(element) + 1;
                selectors.nthChild = `${element.tagName.toLowerCase()}:nth-child(${index})`;
            }
        }

        // 6. Full CSS Path
        const path = [];
        let current = element;
        while (current && current !== document.body && current !== document.documentElement) {
            let selector = current.tagName.toLowerCase();
            if (current.id) {
                selector = '#' + CSS.escape(current.id);
                path.unshift(selector);
                break;
            } else {
                const parent = current.parentElement;
                if (parent) {
                    const siblings = [...parent.children].filter(c => c.tagName === current.tagName);
                    if (siblings.length > 1) {
                        const idx = siblings.indexOf(current) + 1;
                        selector += `:nth-child(${idx})`;
                    }
                }
            }
            path.unshift(selector);
            current = current.parentElement;
        }
        selectors.fullPath = path.join(' > ');

        // 7. XPath
        let xpath = '';
        current = element;
        while (current && current.nodeType === Node.ELEMENT_NODE) {
            let segment = current.tagName.toLowerCase();
            if (current.id) {
                segment = `//${segment}[@id="${current.id}"]`;
                xpath = segment + xpath;
                break;
            } else {
                const parent = current.parentElement;
                if (parent) {
                    const siblings = [...parent.children].filter(c => c.tagName === current.tagName);
                    if (siblings.length > 1) {
                        const idx = siblings.indexOf(current) + 1;
                        segment += `[${idx}]`;
                    }
                }
                xpath = '/' + segment + xpath;
                current = current.parentElement;
            }
        }
        if (!xpath.startsWith('//')) {
            xpath = '/' + xpath;
        }
        selectors.xpath = xpath;

        // 8. Text content (for leaf nodes)
        const textContent = element.textContent?.trim();
        if (textContent && element.children.length === 0 && textContent.length < 50) {
            selectors.textContent = `//${element.tagName.toLowerCase()}[contains(text(),'${textContent.slice(0, 30)}')]`;
        }

        return selectors;
    }

    // 셀렉터 표시 함수
    function displaySelectors(element, selectors) {
        const body = panel.querySelector('.sc-body');
        let html = '';

        for (const [key, value] of Object.entries(selectors)) {
            const escapedValue = value.replace(/'/g, '&#39;').replace(/"/g, '&quot;');
            html += `
                <div class="sc-group">
                    <div class="sc-label">${key}</div>
                    <div class="sc-value">
                        <code>${value}</code>
                        <button class="sc-copy" data-value="${escapedValue}">📋</button>
                    </div>
                </div>
            `;
        }
        body.innerHTML = html;

        // 복사 버튼 이벤트
        body.querySelectorAll('.sc-copy').forEach(btn => {
            btn.onclick = (e) => {
                e.stopPropagation();
                navigator.clipboard.writeText(btn.dataset.value);
                btn.textContent = '✓';
                setTimeout(() => btn.textContent = '📋', 1000);
            };
        });

        // 히스토리 추가
        const historyItem = {
            tag: element.tagName.toLowerCase(),
            id: element.id || null,
            classes: element.className || null,
            selectors: selectors,
            timestamp: new Date().toLocaleTimeString()
        };
        history.unshift(historyItem);
        if (history.length > 20) history.pop();
        updateHistory();
    }

    // 히스토리 업데이트
    function updateHistory() {
        const list = panel.querySelector('.sc-history-list');
        list.innerHTML = history.map((item, idx) => `
            <div class="sc-history-item" data-idx="${idx}">
                <span><span class="sc-tag">&lt;${item.tag}&gt;</span> ${item.id ? '#' + item.id : item.classes ? '.' + item.classes.split(' ')[0] : ''}</span>
                <span style="color: #8b949e; font-size: 10px;">${item.timestamp}</span>
            </div>
        `).join('');

        // 히스토리 아이템 클릭
        list.querySelectorAll('.sc-history-item').forEach(item => {
            item.onclick = () => {
                const idx = parseInt(item.dataset.idx);
                const body = panel.querySelector('.sc-body');
                let html = '';
                for (const [key, value] of Object.entries(history[idx].selectors)) {
                    const escapedValue = value.replace(/'/g, '&#39;').replace(/"/g, '&quot;');
                    html += `
                        <div class="sc-group">
                            <div class="sc-label">${key}</div>
                            <div class="sc-value">
                                <code>${value}</code>
                                <button class="sc-copy" data-value="${escapedValue}">📋</button>
                            </div>
                        </div>
                    `;
                }
                body.innerHTML = html;
                body.querySelectorAll('.sc-copy').forEach(btn => {
                    btn.onclick = (e) => {
                        e.stopPropagation();
                        navigator.clipboard.writeText(btn.dataset.value);
                        btn.textContent = '✓';
                        setTimeout(() => btn.textContent = '📋', 1000);
                    };
                });
            };
        });
    }

    // 히스토리 지우기
    panel.querySelector('.sc-history-clear').onclick = () => {
        history.length = 0;
        updateHistory();
    };

    // JSON 내보내기
    panel.querySelector('.sc-export').onclick = () => {
        const data = JSON.stringify(history, null, 2);
        const blob = new Blob([data], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'selectors-' + Date.now() + '.json';
        a.click();
        URL.revokeObjectURL(url);
    };

    // 클릭 이벤트 처리
    let isActive = true;
    let lastHighlighted = null;

    function handleClick(e) {
        if (!isActive) return;
        if (panel.contains(e.target)) return;

        e.preventDefault();
        e.stopPropagation();

        // 이전 하이라이트 제거
        if (lastHighlighted) {
            lastHighlighted.classList.remove('sc-highlight');
        }

        // 새 하이라이트
        e.target.classList.add('sc-highlight');
        lastHighlighted = e.target;

        // 셀렉터 수집 및 표시
        const selectors = getAllSelectors(e.target);
        displaySelectors(e.target, selectors);

        console.log('🎯 Collected Selectors:', selectors);
    }

    document.addEventListener('click', handleClick, true);

    // 닫기 버튼
    panel.querySelector('.sc-close').onclick = () => {
        isActive = false;
        panel.remove();
        style.remove();
        if (lastHighlighted) {
            lastHighlighted.classList.remove('sc-highlight');
        }
        document.removeEventListener('click', handleClick, true);
        delete window.selectorCollector;
        console.log('🎯 Selector Collector 종료됨');
    };

    // 전역 객체로 등록
    window.selectorCollector = {
        toggle: () => {
            isActive = !isActive;
            panel.style.display = isActive ? 'flex' : 'none';
            if (!isActive && lastHighlighted) {
                lastHighlighted.classList.remove('sc-highlight');
            }
            console.log('🎯 Selector Collector:', isActive ? '활성화' : '비활성화');
        },
        getHistory: () => history,
        destroy: () => panel.querySelector('.sc-close').click()
    };

    console.log('🎯 Selector Collector 시작됨');
    console.log('   - 페이지의 요소를 클릭하면 셀렉터가 수집됩니다');
    console.log('   - window.selectorCollector.toggle() - 토글');
    console.log('   - window.selectorCollector.getHistory() - 히스토리 조회');
    console.log('   - window.selectorCollector.destroy() - 종료');
})();</pre>
                </div>
            </div>

            <div class="instructions" style="margin-top: 16px;">
                <h3>💡 콘솔 명령어</h3>
                <ul style="padding-left: 20px; line-height: 1.8;">
                    <li><code>window.selectorCollector.toggle()</code> - 켜기/끄기</li>
                    <li><code>window.selectorCollector.getHistory()</code> - 수집 히스토리 조회</li>
                    <li><code>window.selectorCollector.destroy()</code> - 완전 종료</li>
                </ul>
            </div>
        </div>

        <!-- Demo Panel -->
        <div class="panel" id="demo">
            <p style="margin-bottom: 16px;">이 페이지에서 직접 테스트해보세요. 아래 버튼을 클릭하면 Selector Collector가 활성화됩니다:</p>
            
            <button class="demo-btn demo-btn-1" onclick="activateDemo()" id="activate-btn">
                🎯 데모 활성화
            </button>

            <div class="demo-area">
                <h3>테스트용 요소들</h3>
                <div class="demo-elements">
                    <button class="demo-btn demo-btn-1" id="btn-primary" data-testid="primary-button">
                        Primary Button
                    </button>
                    
                    <button class="demo-btn demo-btn-2" id="btn-secondary" aria-label="Secondary action">
                        Secondary Button
                    </button>
                    
                    <a href="#" class="demo-link" id="demo-link" data-cy="demo-link">
                        Sample Link
                    </a>
                    
                    <input type="text" class="demo-input" placeholder="Enter text..." name="demo-input" id="input-demo">
                    
                    <div class="demo-card" id="card-1" data-id="card-001">
                        <h4 style="color: #58a6ff; margin-bottom: 8px;">Card Title</h4>
                        <p style="color: #8b949e; font-size: 0.9rem;">Card content here</p>
                    </div>
                    
                    <div class="demo-card" id="card-2" role="article">
                        <h4 style="color: #58a6ff; margin-bottom: 8px;">Another Card</h4>
                        <p style="color: #8b949e; font-size: 0.9rem;">More content</p>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Selectors Panel (for demo) -->
    <div class="selectors-panel" id="selectors-panel">
        <div class="selectors-header">
            <h4>🎯 수집된 셀렉터</h4>
            <button class="close-panel" onclick="closePanel()">✕</button>
        </div>
        <div class="selectors-body" id="selectors-body">
            <p style="color: #8b949e; text-align: center; padding: 20px;">요소를 클릭하세요</p>
        </div>
    </div>

    <div class="status-bar" id="status-bar">✓ Selector Collector 활성화됨</div>

    <script>
        // Tab switching
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
                tab.classList.add('active');
                document.getElementById(tab.dataset.tab).classList.add('active');
            });
        });

        // Copy code
        function copyCode() {
            const code = document.getElementById('console-code').textContent;
            navigator.clipboard.writeText(code);
            const btn = document.querySelector('.copy-btn');
            btn.textContent = '✓ 복사됨!';
            btn.classList.add('copied');
            setTimeout(() => {
                btn.textContent = '📋 복사';
                btn.classList.remove('copied');
            }, 2000);
        }

        // Demo functionality
        let demoActive = false;
        let lastHighlighted = null;

        function activateDemo() {
            demoActive = !demoActive;
            const btn = document.getElementById('activate-btn');
            const status = document.getElementById('status-bar');
            const panel = document.getElementById('selectors-panel');

            if (demoActive) {
                btn.textContent = '⏹ 데모 비활성화';
                btn.style.background = '#f85149';
                status.classList.add('active');
                panel.classList.add('show');
                setTimeout(() => status.classList.remove('active'), 2000);
            } else {
                btn.textContent = '🎯 데모 활성화';
                btn.style.background = '';
                panel.classList.remove('show');
                if (lastHighlighted) {
                    lastHighlighted.classList.remove('selector-highlight');
                    lastHighlighted = null;
                }
            }
        }

        function closePanel() {
            demoActive = false;
            document.getElementById('selectors-panel').classList.remove('show');
            document.getElementById('activate-btn').textContent = '🎯 데모 활성화';
            document.getElementById('activate-btn').style.background = '';
            if (lastHighlighted) {
                lastHighlighted.classList.remove('selector-highlight');
            }
        }

        function getAllSelectors(element) {
            const selectors = {};

            if (element.id) {
                selectors.id = '#' + CSS.escape(element.id);
            }

            if (element.className && typeof element.className === 'string') {
                const classes = element.className.trim().split(/\s+/).filter(c => c && !c.includes('selector-'));
                if (classes.length > 0) {
                    selectors.classes = '.' + classes.map(c => CSS.escape(c)).join('.');
                }
            }

            selectors.tag = element.tagName.toLowerCase();

            const importantAttrs = ['name', 'type', 'placeholder', 'data-testid', 'data-id', 'data-cy', 'aria-label', 'role', 'href'];
            importantAttrs.forEach(attr => {
                const value = element.getAttribute(attr);
                if (value) {
                    selectors[`[${attr}]`] = `${element.tagName.toLowerCase()}[${attr}="${CSS.escape(value)}"]`;
                }
            });

            const parent = element.parentElement;
            if (parent) {
                const siblings = [...parent.children].filter(c => c.tagName === element.tagName);
                if (siblings.length > 1) {
                    const idx = siblings.indexOf(element) + 1;
                    selectors.nthChild = `${element.tagName.toLowerCase()}:nth-child(${idx})`;
                }
            }

            // Full path
            const path = [];
            let current = element;
            while (current && current !== document.body) {
                let selector = current.tagName.toLowerCase();
                if (current.id) {
                    selector = '#' + CSS.escape(current.id);
                    path.unshift(selector);
                    break;
                } else {
                    const p = current.parentElement;
                    if (p) {
                        const sibs = [...p.children].filter(c => c.tagName === current.tagName);
                        if (sibs.length > 1) {
                            selector += `:nth-child(${sibs.indexOf(current) + 1})`;
                        }
                    }
                }
                path.unshift(selector);
                current = current.parentElement;
            }
            selectors.fullPath = path.join(' > ');

            // XPath
            let xpath = '';
            current = element;
            while (current && current.nodeType === 1) {
                let seg = current.tagName.toLowerCase();
                if (current.id) {
                    seg = `//${seg}[@id="${current.id}"]`;
                    xpath = seg + xpath;
                    break;
                } else {
                    const p = current.parentElement;
                    if (p) {
                        const sibs = [...p.children].filter(c => c.tagName === current.tagName);
                        if (sibs.length > 1) seg += `[${sibs.indexOf(current) + 1}]`;
                    }
                    xpath = '/' + seg + xpath;
                    current = current.parentElement;
                }
            }
            if (!xpath.startsWith('//')) xpath = '/' + xpath;
            selectors.xpath = xpath;

            const text = element.textContent?.trim();
            if (text && element.children.length === 0 && text.length < 50) {
                selectors.textContent = `//${element.tagName.toLowerCase()}[contains(text(),'${text.slice(0, 30)}')]`;
            }

            return selectors;
        }

        function displaySelectors(selectors) {
            const body = document.getElementById('selectors-body');
            let html = '';
            for (const [key, value] of Object.entries(selectors)) {
                html += `
                    <div class="selector-group">
                        <div class="selector-label">${key}</div>
                        <div class="selector-value">
                            <code>${value}</code>
                            <button class="selector-copy" onclick="copySelector(this, '${value.replace(/'/g, "\\'")}')">📋</button>
                        </div>
                    </div>
                `;
            }
            body.innerHTML = html;
        }

        function copySelector(btn, value) {
            navigator.clipboard.writeText(value);
            btn.textContent = '✓';
            setTimeout(() => btn.textContent = '📋', 1000);
        }

        document.addEventListener('click', (e) => {
            if (!demoActive) return;
            
            const panel = document.getElementById('selectors-panel');
            if (panel.contains(e.target)) return;
            if (e.target.id === 'activate-btn') return;
            if (e.target.closest('.tabs')) return;

            e.preventDefault();
            e.stopPropagation();

            if (lastHighlighted) {
                lastHighlighted.classList.remove('selector-highlight');
            }

            e.target.classList.add('selector-highlight');
            lastHighlighted = e.target;

            const selectors = getAllSelectors(e.target);
            displaySelectors(selectors);
        }, true);
    </script>
</body>
</html>
