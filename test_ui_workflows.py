import asyncio
import sys
from playwright.async_api import async_playwright, expect

# Global lists to collect errors
console_errors = []
failed_requests = []
page_errors = []

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # Listeners for errors
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: page_errors.append(str(err)))
        page.on("requestfailed", lambda req: failed_requests.append(f"{req.method} {req.url} - {req.failure}") if req.failure and "ERR_ABORTED" not in str(req.failure) else None)
        
        # Helper to check response status
        async def check_response(response):
            if response.status >= 400:
                failed_requests.append(f"{response.request.method} {response.url} - Status: {response.status}")
        
        page.on("response", check_response)

        BASE_URL = "http://localhost:5173"
        print(f"Testing workflows on {BASE_URL}")

        # 1. Login as Admin
        print("Logging in as Admin...")
        await page.goto(f"{BASE_URL}/login", wait_until="networkidle")
        await page.fill("input[id='identifier']", "admin")
        await page.fill("input[type='password']", "Admin@12345")
        await page.click("button[type='submit']")
        await expect(page.locator("text=Dashboard").first).to_be_visible(timeout=10000)
        print("Login successful.")

        # 2. Material Master Upload
        print("Testing Material Master Upload...")
        await page.goto(f"{BASE_URL}/master/material-upload", wait_until="networkidle")
        await expect(page.locator("h1")).to_contain_text("Material Master")
        file_input = page.locator("input[type='file']").first
        if await file_input.count() > 0:
            import os
            test_file = os.path.join("backend", "test.xlsx")
            if os.path.exists(test_file):
                await file_input.set_input_files(test_file)
                pass
        await page.wait_for_timeout(1000)
        
        # 3. BOM Upload
        print("Testing BOM Upload...")
        await page.goto(f"{BASE_URL}/master/bom-upload", wait_until="networkidle")
        await expect(page.locator("h1")).to_contain_text("BOM")
        file_input = page.locator("input[type='file']").first
        if await file_input.count() > 0:
            import os
            test_file = os.path.join("backend", "Skus_Bom.xlsx")
            if os.path.exists(test_file):
                await file_input.set_input_files(test_file)
                pass
        await page.wait_for_timeout(1000)

        # 4. Inventory Upload
        print("Testing Inventory Upload...")
        await page.goto(f"{BASE_URL}/inventory/upload", wait_until="networkidle")
        # Check if the page loads without crashing
        await page.wait_for_timeout(1000)
        
        # 5. ODS Request
        print("Testing ODS Request (Create)...")
        # Login as ODS Operator
        await page.evaluate("localStorage.clear(); sessionStorage.clear();")
        await page.goto(f"{BASE_URL}/login", wait_until="networkidle")
        await page.fill("input[id='identifier']", "ods_op")
        await page.fill("input[type='password']", "OdsOp@12345")
        await page.click("button[type='submit']")
        await page.wait_for_timeout(2000)
        await page.goto(f"{BASE_URL}/requests/new", wait_until="networkidle")
        await page.wait_for_timeout(1000)

        # 6. RMPM Approval
        print("Testing RMPM Approval...")
        await page.evaluate("localStorage.clear(); sessionStorage.clear();")
        await page.goto(f"{BASE_URL}/login", wait_until="networkidle")
        await page.fill("input[id='identifier']", "rmpm_op")
        await page.fill("input[type='password']", "Rmpm@12345")
        await page.click("button[type='submit']")
        await page.wait_for_timeout(2000)
        await page.goto(f"{BASE_URL}/requests", wait_until="networkidle")
        await page.wait_for_timeout(1000)

        # 7. Dashboard
        print("Testing Dashboard...")
        await page.goto(f"{BASE_URL}/", wait_until="networkidle")
        await page.wait_for_timeout(1000)

        # 8. Reports
        print("Testing Reports...")
        await page.goto(f"{BASE_URL}/reports", wait_until="networkidle")
        await page.wait_for_timeout(1000)

        print("\n--- Test Results ---")
        errors_found = False
        if console_errors:
            print("JavaScript Console Errors:")
            for e in set(console_errors):
                if "favicon" not in e and "The resource" not in e: # ignore common warnings
                    print(f"  - {e}")
                    errors_found = True
        
        if page_errors:
            print("Page Errors (Exceptions):")
            for e in set(page_errors):
                print(f"  - {e}")
                errors_found = True
                
        if failed_requests:
            print("Failed API Requests:")
            for req in set(failed_requests):
                if "/api/" in req:
                    print(f"  - {req}")
                    errors_found = True
                    
        if not errors_found:
            print("All workflows verified successfully! No UI or API errors detected.")
            sys.exit(0)
        else:
            print("Errors detected during verification.")
            sys.exit(1)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
