# Playwright Patterns

이 문서는 Webwright text-default plugin이 사용하는 Playwright 패턴을 정리합니다.
핵심은 한 번에 하나의 shell command를 실행하고, JSON wrapper 없이 Python
heredoc이나 `final_script.py`를 직접 다루는 것입니다.

## Browser launch skeleton

기본 engine은 Firefox를 선호합니다. 일부 사이트는 Playwright Chromium의 TLS/H2
fingerprint를 거부할 수 있으므로 Firefox가 더 안정적일 때가 있습니다. 첫 실행
전에는 필요한 browser를 설치합니다.

```bash
python - <<'PY'
import asyncio
import os
from pathlib import Path
from playwright.async_api import async_playwright

WORKSPACE = Path(os.environ.get("WORKSPACE_DIR", "."))
SCREENSHOTS = WORKSPACE / "screenshots"
SCREENSHOTS.mkdir(parents=True, exist_ok=True)

async def main():
    async with async_playwright() as playwright:
        headless = os.environ.get("WEBWRIGHT_HEADLESS", "1") not in {"0", "false", "False"}
        browser = await playwright.firefox.launch(headless=headless)
        context = await browser.new_context(viewport={"width": 1280, "height": 1800})
        page = await context.new_page()
        await page.goto("<START_URL>", wait_until="domcontentloaded")
        print("URL:", page.url)
        print("TITLE:", await page.title())
        print("ARIA:", await page.locator("body").aria_snapshot())
        await page.screenshot(path=str(SCREENSHOTS / "explore_1_start.png"))
        await browser.close()

asyncio.run(main())
PY
```

규칙:

- viewport는 항상 1280x1800을 사용합니다.
- `page.screenshot(full_page=True)`는 사용하지 않습니다.
- 매 run은 fresh browser context에서 시작합니다.

## Locator와 form 입력

가능하면 CSS class보다 role, name, aria-label을 사용합니다. 검색어, 날짜, 필터처럼
parameterized input이 있는 작업은 deep link URL 조립보다 화면의 form을 직접
조작하는 방식을 우선합니다. Deep link는 locale, A/B bucket, 로그인 상태에 따라
parameter가 조용히 무시될 수 있습니다.

```python
await page.get_by_role("button", name="Filters").click()
panel = page.get_by_role("button", name="Filters").first.locator("..")
print(await panel.aria_snapshot())
await page.get_by_role("checkbox", name="BMW").check()
```

form을 채운 뒤에는 visible state를 다시 읽고 각 critical point를 검증합니다.
자동 submit에 기대지 말고 명시적인 submit control을 클릭합니다.

## Final script instrumentation

`final_runs/run_<id>/final_script.py`는 다음을 지켜야 합니다.

- screenshot은 `final_runs/run_<id>/screenshots/final_execution_<step>_<action>.png`
  형식으로 저장합니다.
- action log는 `final_script_log.txt`에 기록합니다.
- CLI tool mode에서는 첫 줄에 `step 0 params: ...`를 기록합니다.
- 마지막에는 추출한 핵심 datum을 log와 stdout에서 확인할 수 있어야 합니다.

```python
RUN_DIR = Path(__file__).parent
SCREENSHOTS = RUN_DIR / "screenshots"
SCREENSHOTS.mkdir(parents=True, exist_ok=True)
LOG = RUN_DIR / "final_script_log.txt"
LOG.write_text("")
```

## Evidence priority

DOM/text/ARIA/URL/response/log evidence를 먼저 사용합니다. Screenshot은 반드시
저장하되, vision fallback은 구조화 evidence가 부족한 시각적 claim에만 사용합니다.
최종 보고에서는 어떤 critical point가 text evidence로 검증됐고 어떤 항목이
vision fallback을 사용했는지 분리해서 적습니다.
