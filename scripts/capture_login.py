"""
Скрипт для исследования API авторизации midasbuy.com
Перехватывает сетевые запросы при логине и сохраняет результаты
"""
import asyncio
import json
from datetime import datetime
from playwright.async_api import async_playwright

EMAIL = "alihanveliev2@gmail.com"
PASSWORD = "alihan30"
TARGET_URL = "https://www.midasbuy.com/shop/pagedoo/ct1744785094_QMGQJMGD/mobile/index.html?from=self.midasbuy_saas&adtag=couponManage#/pages/p-wgbu/"

captured_requests = []
captured_responses = []


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=300)
        context = await browser.new_context(
            viewport={"width": 390, "height": 844},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        )
        page = await context.new_page()

        # Intercept all network requests
        async def on_request(request):
            if any(x in request.url for x in ['cgi-bin', 'api', 'login', 'auth', 'coupon', 'user']):
                info = {
                    "url": request.url,
                    "method": request.method,
                    "headers": dict(request.headers),
                    "post_data": request.post_data,
                    "time": datetime.now().isoformat()
                }
                captured_requests.append(info)
                print(f"[REQ] {request.method} {request.url}")
                if request.post_data:
                    print(f"      BODY: {request.post_data[:200]}")

        async def on_response(response):
            if any(x in response.url for x in ['cgi-bin', 'api', 'login', 'auth', 'coupon', 'user']):
                try:
                    body = await response.body()
                    body_text = body.decode('utf-8', errors='replace')[:500]
                except:
                    body_text = "(failed to read)"
                info = {
                    "url": response.url,
                    "status": response.status,
                    "headers": dict(response.headers),
                    "body": body_text,
                    "time": datetime.now().isoformat()
                }
                captured_responses.append(info)
                print(f"[RES] {response.status} {response.url}")
                print(f"      BODY: {body_text[:200]}")

        page.on("request", on_request)
        page.on("response", on_response)

        print(f"\n[*] Navigating to {TARGET_URL}")
        await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(2000)

        print("\n[*] Looking for Sign In button...")
        # Try to find and click the sign in button
        sign_in_selectors = [
            'text="Sign In"',
            'text="Sign In Midasbuy"',
            '[class*="sign-in"]',
            '[class*="login"]',
            'button:has-text("Sign")',
        ]
        
        clicked = False
        for sel in sign_in_selectors:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=3000):
                    await btn.click()
                    clicked = True
                    print(f"[*] Clicked: {sel}")
                    break
            except:
                continue
        
        if not clicked:
            print("[!] Could not find Sign In button automatically")
            print("[*] Please click Sign In manually in the browser...")
            await page.wait_for_timeout(10000)

        await page.wait_for_timeout(2000)

        print("\n[*] Looking for email input...")
        email_selectors = [
            'input[type="email"]',
            'input[placeholder*="email" i]',
            'input[placeholder*="Email" i]',
            'input[name="email"]',
        ]
        
        for sel in email_selectors:
            try:
                inp = page.locator(sel).first
                if await inp.is_visible(timeout=5000):
                    await inp.fill(EMAIL)
                    print(f"[*] Filled email: {sel}")
                    break
            except:
                continue

        await page.wait_for_timeout(1000)

        print("[*] Looking for password input...")
        for sel in ['input[type="password"]', 'input[placeholder*="password" i]', 'input[name="password"]']:
            try:
                inp = page.locator(sel).first
                if await inp.is_visible(timeout=3000):
                    await inp.fill(PASSWORD)
                    print(f"[*] Filled password: {sel}")
                    break
            except:
                continue

        await page.wait_for_timeout(1000)

        print("[*] Submitting login form...")
        submit_selectors = [
            'button[type="submit"]',
            'button:has-text("Log In")',
            'button:has-text("Sign In")',
            'button:has-text("Login")',
        ]
        
        for sel in submit_selectors:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=3000):
                    await btn.click()
                    print(f"[*] Clicked submit: {sel}")
                    break
            except:
                continue

        print("[*] Waiting for login to complete (15 seconds)...")
        await page.wait_for_timeout(15000)

        # Get cookies after login
        cookies = await context.cookies()
        print(f"\n[*] Cookies after login ({len(cookies)} total):")
        for c in cookies:
            print(f"  {c['name']} = {c['value'][:50]}...")

        # Save results
        results = {
            "requests": captured_requests,
            "responses": captured_responses,
            "cookies": [{"name": c["name"], "value": c["value"], "domain": c["domain"]} for c in cookies],
            "timestamp": datetime.now().isoformat()
        }
        
        with open("scripts/login_capture.json", "w") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"\n[✓] Saved {len(captured_requests)} requests and {len(captured_responses)} responses")
        print("[*] Results saved to scripts/login_capture.json")
        
        input("\nPress ENTER to close browser...")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
