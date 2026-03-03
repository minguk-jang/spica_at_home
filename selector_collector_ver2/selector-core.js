(() => {
    // ------------------------------------------------------------------------
    // Constants & Helpers
    // ------------------------------------------------------------------------

    const IMPORTANT_ATTRS = [
        'name', 'type', 'placeholder', 'value',
        'data-testid', 'data-id', 'data-cy', 'data-test',
        'aria-label', 'aria-labelledby', 'role',
        'href', 'src', 'alt', 'title', 'for'
    ];

    /**
     * Bug 3 Fix: Escape attribute values correctly for CSS selectors.
     * CSS.escape() is for identifiers, not attribute string values.
     * We need to escape double quotes and backslashes.
     */
    function escapeAttrValue(str) {
        return str.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
    }

    /**
     * Bug 4 Fix: Escape text for XPath properly.
     * XPath 1.0 doesn't have a direct escape for both single and double quotes easily.
     * We use concat() if both are present.
     */
    function escapeXPathText(text) {
        if (!text.includes("'")) {
            return `'${text}'`;
        }
        if (!text.includes('"')) {
            return `"${text}"`;
        }
        // If both quotes are present, use concat: "It's" -> concat("It", "'", "s")
        const parts = text.split("'");
        // join with "',"'",'" -> effectively closing the string, adding a single quote, starting new string
        // but easier logic:
        return `concat('${parts.join("',\"'\",'")}')`;
    }

    /**
     * Bug 1 Fix: Use nth-of-type correctly.
     * Original bug used nth-child with filtered list index which is wrong.
     */
    function getNthOfType(element) {
        const parent = element.parentElement;
        if (!parent) return '';

        const siblings = [...parent.children].filter(c => c.tagName === element.tagName);
        if (siblings.length > 1) {
            const idx = siblings.indexOf(element) + 1;
            return `${element.tagName.toLowerCase()}:nth-of-type(${idx})`;
        }
        return '';
    }

    function buildFullCssPath(element) {
        if (!element || element.nodeType !== Node.ELEMENT_NODE) return '';
        
        const path = [];
        let current = element;

        while (current && current.nodeType === Node.ELEMENT_NODE) {
            let selector = current.tagName.toLowerCase();
            
            if (current.id) {
                selector += `#${CSS.escape(current.id)}`;
                path.unshift(selector);
                break; // Stop at ID as it's usually unique enough (and cleaner)
            } else {
                const parent = current.parentElement;
                if (parent) {
                    const siblings = [...parent.children].filter(c => c.tagName === current.tagName);
                    if (siblings.length > 1) {
                        selector += `:nth-of-type(${siblings.indexOf(current) + 1})`;
                    }
                }
                path.unshift(selector);
                current = parent;
            }
        }
        return path.join(' > ');
    }

    /**
     * Bug 2 Fix: XPath prefix logic.
     * Should only use // if we found an ID anchor. Otherwise use absolute path from /html/body
     */
    function buildXPath(element) {
        if (!element || element.nodeType !== Node.ELEMENT_NODE) return '';

        const paths = [];
        let current = element;
        let foundId = false;

        while (current && current.nodeType === Node.ELEMENT_NODE) {
            let tagName = current.tagName.toLowerCase();
            
            // Check for ID
            if (current.id) {
                const safeId = escapeAttrValue(current.id);
                paths.unshift(`${tagName}[@id="${safeId}"]`);
                foundId = true;
                break; // Stop at ID
            } else {
                // Calculate position among same-tag siblings
                let pos = 0;
                const siblings = current.parentNode ? [...current.parentNode.children] : [];
                const sameTagSiblings = siblings.filter(s => s.tagName === current.tagName);
                
                if (sameTagSiblings.length > 1) {
                    pos = sameTagSiblings.indexOf(current) + 1;
                    paths.unshift(`${tagName}[${pos}]`);
                } else {
                    paths.unshift(tagName);
                }
            }
            current = current.parentNode;
        }

        return foundId ? `//${paths.join('/')}` : `/${paths.join('/')}`;
    }

    // ------------------------------------------------------------------------
    // Core Functions
    // ------------------------------------------------------------------------

    function getAllSelectors(element) {
        if (!element || element.nodeType !== Node.ELEMENT_NODE) return {};

        const selectors = {};
        const tagName = element.tagName.toLowerCase();
        
        // 1. Tag
        selectors.tag = tagName;

        // 2. ID
        if (element.id) {
            selectors.id = `#${CSS.escape(element.id)}`;
        }

        // 3. Classes
        if (typeof element.className === 'string' && element.className.trim()) {
            const validClasses = element.className.split(/\s+/)
                .filter(c => c && c !== '__sc-highlight') // Exclude our highlight class
                .map(c => `.${CSS.escape(c)}`)
                .join('');
            if (validClasses) {
                selectors.classes = validClasses;
            }
        }

        // 4. Attributes
        IMPORTANT_ATTRS.forEach(attr => {
            if (element.hasAttribute(attr)) {
                const val = element.getAttribute(attr);
                if (val) { // only if has value
                    selectors[`[${attr}]`] = `${tagName}[${attr}="${escapeAttrValue(val)}"]`;
                }
            }
        });

        // 5. nth-of-type
        const nth = getNthOfType(element);
        if (nth) {
            selectors.nthOfType = nth;
        }

        // 6. Full CSS Path
        selectors.fullCssPath = buildFullCssPath(element);

        // 7. XPath
        selectors.xpath = buildXPath(element);

        // 8. Text XPath (if applicable)
        // Check if it's a leaf node or close to it, and has reasonable text
        const text = (element.textContent || '').trim();
        if (text && text.length < 50 && element.children.length === 0) {
            selectors.textXpath = `//${tagName}[contains(text(),${escapeXPathText(text)})]`;
        }

        return selectors;
    }

    function validateAllSelectors(selectors, targetElement) {
        const results = {};

        for (const [key, selector] of Object.entries(selectors)) {
            if (!selector) {
                results[key] = false;
                continue;
            }

            try {
                if (key === 'xpath' || key === 'textXpath') {
                    const result = document.evaluate(
                        selector, 
                        document, 
                        null, 
                        XPathResult.FIRST_ORDERED_NODE_TYPE, 
                        null
                    );
                    results[key] = (result.singleNodeValue === targetElement);
                } else {
                    // CSS Selectors
                    const el = document.querySelector(selector);
                    results[key] = (el === targetElement);
                }
            } catch (e) {
                console.warn(`Selector validation error for ${key}:`, e);
                results[key] = false;
            }
        }

        return results;
    }

    // ------------------------------------------------------------------------
    // Export
    // ------------------------------------------------------------------------

    window.SelectorCore = {
        getAllSelectors,
        validateAllSelectors
    };

})();
