#!/usr/bin/env python3
"""
Playwright test script to browse the Gmail CrewAI app and look for errors.
"""
import asyncio
import time
from playwright.async_api import async_playwright
import json
import traceback

class AppTester:
    def __init__(self, base_url=None):
        import os
        port = os.getenv('PORT', '8505')
        self.base_url = base_url or f"http://localhost:{port}"
        self.errors = []
        self.warnings = []
        self.info = []

    def log_error(self, message, error_type="ERROR", details=None):
        error_entry = {
            "type": error_type,
            "message": message,
            "timestamp": time.time(),
            "details": details
        }
        if error_type == "ERROR":
            self.errors.append(error_entry)
        elif error_type == "WARNING":
            self.warnings.append(error_entry)
        else:
            self.info.append(error_entry)
        print(f"[{error_type}] {message}")
        if details:
            print(f"  Details: {details}")

    async def wait_for_app_to_load(self, page, timeout=30000):
        """Wait for the Streamlit app to fully load"""
        try:
            # Wait for Streamlit to initialize
            await page.wait_for_selector('[data-testid="stApp"]', timeout=timeout)
            self.log_error("App container loaded successfully", "INFO")
            
            # Wait a bit more for dynamic content
            await page.wait_for_timeout(3000)
            
            # Check if there are any immediate errors
            error_elements = await page.query_selector_all('.stException, .stError, [data-testid="stException"]')
            if error_elements:
                for i, error_el in enumerate(error_elements):
                    error_text = await error_el.text_content()
                    self.log_error(f"Streamlit exception found: {error_text}", "ERROR")
            
            return True
            
        except Exception as e:
            self.log_error(f"App failed to load within {timeout}ms", "ERROR", str(e))
            return False

    async def test_login_page(self, page):
        """Test the login page functionality"""
        self.log_error("Testing login page...", "INFO")
        
        try:
            # Check for login elements
            login_elements = [
                "button",  # Look for login buttons
                "h1",      # Look for page title
                ".login-container", # Login container
            ]
            
            found_elements = []
            for selector in login_elements:
                elements = await page.query_selector_all(selector)
                found_elements.extend([(selector, len(elements))])
            
            self.log_error(f"Found UI elements: {found_elements}", "INFO")
            
            # Check for specific login text/buttons
            content = await page.content()
            login_indicators = [
                "Login with Gmail",
                "Sign up with Gmail", 
                "Gmail CrewAI",
                "Setup as Primary Owner",
                "authentication"
            ]
            
            found_text = []
            for indicator in login_indicators:
                if indicator.lower() in content.lower():
                    found_text.append(indicator)
            
            if found_text:
                self.log_error(f"Found login indicators: {found_text}", "INFO")
            else:
                self.log_error("No login indicators found - app may not be on login page", "WARNING")
            
            # Look for any error messages on the page
            error_selectors = [
                '.stError',
                '.stException', 
                '[data-testid="stAlert"]',
                '.error'
            ]
            
            for selector in error_selectors:
                error_elements = await page.query_selector_all(selector)
                for error_el in error_elements:
                    error_text = await error_el.text_content()
                    if error_text and error_text.strip():
                        self.log_error(f"UI Error found: {error_text.strip()}", "ERROR")
            
        except Exception as e:
            self.log_error(f"Error testing login page: {str(e)}", "ERROR", traceback.format_exc())

    async def test_navigation(self, page):
        """Test basic navigation and button functionality"""
        self.log_error("Testing navigation and buttons...", "INFO")
        
        try:
            # Find all buttons
            buttons = await page.query_selector_all('button')
            self.log_error(f"Found {len(buttons)} buttons on page", "INFO")
            
            # Test clicking accessible buttons (avoid OAuth buttons for now)
            for i, button in enumerate(buttons[:3]):  # Test first 3 buttons max
                try:
                    button_text = await button.text_content()
                    button_text = button_text.strip() if button_text else f"Button {i}"
                    
                    # Skip OAuth/external redirect buttons
                    skip_buttons = ["login with gmail", "sign up with gmail", "setup as primary owner"]
                    if any(skip_text in button_text.lower() for skip_text in skip_buttons):
                        self.log_error(f"Skipping OAuth button: {button_text}", "INFO")
                        continue
                    
                    # Check if button is enabled
                    is_disabled = await button.get_attribute('disabled')
                    if is_disabled:
                        self.log_error(f"Button '{button_text}' is disabled", "INFO")
                        continue
                    
                    self.log_error(f"Testing button: {button_text}", "INFO")
                    
                    # Click the button
                    await button.click()
                    await page.wait_for_timeout(1000)  # Wait for any response
                    
                    # Check for any new errors after clicking
                    new_errors = await page.query_selector_all('.stError, .stException')
                    for error_el in new_errors:
                        error_text = await error_el.text_content()
                        if error_text and error_text.strip():
                            self.log_error(f"Error after clicking '{button_text}': {error_text.strip()}", "ERROR")
                    
                except Exception as e:
                    self.log_error(f"Error testing button {i}: {str(e)}", "WARNING")
            
        except Exception as e:
            self.log_error(f"Error testing navigation: {str(e)}", "ERROR", traceback.format_exc())

    async def test_form_inputs(self, page):
        """Test form inputs and text areas"""
        self.log_error("Testing form inputs...", "INFO")
        
        try:
            # Find text inputs
            text_inputs = await page.query_selector_all('input[type="text"], textarea')
            self.log_error(f"Found {len(text_inputs)} text inputs", "INFO")
            
            # Test each input
            for i, input_el in enumerate(text_inputs[:2]):  # Test first 2 inputs
                try:
                    placeholder = await input_el.get_attribute('placeholder')
                    input_type = await input_el.get_attribute('type') or 'textarea'
                    
                    self.log_error(f"Testing input {i}: type={input_type}, placeholder='{placeholder}'", "INFO")
                    
                    # Try to type in the input
                    test_text = "test input" if input_type != 'email' else "test@example.com"
                    await input_el.fill(test_text)
                    
                    # Get the value back
                    value = await input_el.input_value()
                    if value == test_text:
                        self.log_error(f"Input {i} accepts text correctly", "INFO")
                    else:
                        self.log_error(f"Input {i} value mismatch: expected '{test_text}', got '{value}'", "WARNING")
                    
                    # Clear the input
                    await input_el.fill("")
                    
                except Exception as e:
                    self.log_error(f"Error testing input {i}: {str(e)}", "WARNING")
            
        except Exception as e:
            self.log_error(f"Error testing form inputs: {str(e)}", "ERROR", traceback.format_exc())

    async def check_console_errors(self, page):
        """Check for JavaScript console errors"""
        self.log_error("Checking console for JavaScript errors...", "INFO")
        
        console_errors = []
        
        def handle_console(msg):
            if msg.type in ['error', 'warning']:
                console_errors.append({
                    'type': msg.type,
                    'text': msg.text,
                    'location': msg.location if hasattr(msg, 'location') else None
                })
        
        page.on('console', handle_console)
        
        # Trigger some interactions to generate console activity
        await page.reload()
        await page.wait_for_timeout(3000)
        
        # Report console errors
        for error in console_errors:
            error_type = "ERROR" if error['type'] == 'error' else "WARNING"
            self.log_error(f"Console {error['type']}: {error['text']}", error_type, error.get('location'))

    async def test_app_responsiveness(self, page):
        """Test app responsiveness on different screen sizes"""
        self.log_error("Testing app responsiveness...", "INFO")
        
        try:
            # Test different viewport sizes
            viewports = [
                {"width": 1920, "height": 1080, "name": "Desktop"},
                {"width": 768, "height": 1024, "name": "Tablet"}, 
                {"width": 375, "height": 667, "name": "Mobile"},
            ]
            
            for viewport in viewports:
                self.log_error(f"Testing {viewport['name']} viewport ({viewport['width']}x{viewport['height']})", "INFO")
                
                await page.set_viewport_size({"width": viewport["width"], "height": viewport["height"]})
                await page.wait_for_timeout(1000)
                
                # Check if critical elements are still visible
                app_container = await page.query_selector('[data-testid="stApp"]')
                if app_container:
                    bounding_box = await app_container.bounding_box()
                    if bounding_box and bounding_box['width'] > 0:
                        self.log_error(f"{viewport['name']} viewport: App container visible", "INFO")
                    else:
                        self.log_error(f"{viewport['name']} viewport: App container not visible", "WARNING")
                else:
                    self.log_error(f"{viewport['name']} viewport: App container not found", "ERROR")
            
            # Reset to default size
            await page.set_viewport_size({"width": 1280, "height": 720})
            
        except Exception as e:
            self.log_error(f"Error testing responsiveness: {str(e)}", "ERROR", traceback.format_exc())

    async def take_screenshot(self, page, filename="app_screenshot.png"):
        """Take a screenshot of the current page"""
        try:
            await page.screenshot(path=filename, full_page=True)
            self.log_error(f"Screenshot saved: {filename}", "INFO")
        except Exception as e:
            self.log_error(f"Failed to take screenshot: {str(e)}", "WARNING")

    async def run_tests(self):
        """Run all tests"""
        async with async_playwright() as p:
            self.log_error("Starting Playwright browser tests...", "INFO")
            
            # Launch browser
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            try:
                # Navigate to app
                self.log_error(f"Navigating to {self.base_url}", "INFO")
                await page.goto(self.base_url)
                
                # Wait for app to load
                if not await self.wait_for_app_to_load(page):
                    self.log_error("App failed to load, aborting tests", "ERROR")
                    await self.take_screenshot(page, "failed_load_screenshot.png")
                    return
                
                # Take initial screenshot
                await self.take_screenshot(page, "initial_screenshot.png")
                
                # Check for console errors
                await self.check_console_errors(page)
                
                # Test login page
                await self.test_login_page(page)
                
                # Test navigation
                await self.test_navigation(page)
                
                # Test form inputs
                await self.test_form_inputs(page)
                
                # Test responsiveness
                await self.test_app_responsiveness(page)
                
                # Take final screenshot
                await self.take_screenshot(page, "final_screenshot.png")
                
            except Exception as e:
                self.log_error(f"Critical error during testing: {str(e)}", "ERROR", traceback.format_exc())
                await self.take_screenshot(page, "error_screenshot.png")
            
            finally:
                await browser.close()

    def print_summary(self):
        """Print a summary of all findings"""
        print("\n" + "="*60)
        print("PLAYWRIGHT TEST SUMMARY")
        print("="*60)
        
        print(f"\n🔴 ERRORS FOUND: {len(self.errors)}")
        for error in self.errors:
            print(f"  - {error['message']}")
            if error.get('details'):
                print(f"    Details: {error['details'][:200]}...")
        
        print(f"\n🟡 WARNINGS: {len(self.warnings)}")
        for warning in self.warnings:
            print(f"  - {warning['message']}")
        
        print(f"\n🟢 INFO MESSAGES: {len(self.info)}")
        for info in self.info:
            print(f"  - {info['message']}")
        
        print(f"\n📊 TOTAL ISSUES: {len(self.errors + self.warnings)}")
        
        # Save detailed results to file
        results = {
            "errors": self.errors,
            "warnings": self.warnings,
            "info": self.info,
            "summary": {
                "total_errors": len(self.errors),
                "total_warnings": len(self.warnings),
                "total_info": len(self.info)
            }
        }
        
        with open("playwright_test_results.json", "w") as f:
            json.dump(results, f, indent=2)
        print("\n📝 Detailed results saved to: playwright_test_results.json")

async def main():
    """Main function"""
    # Wait a moment for the Streamlit app to start
    print("Waiting for Streamlit app to start...")
    time.sleep(5)
    
    tester = AppTester()
    await tester.run_tests()
    tester.print_summary()

if __name__ == "__main__":
    asyncio.run(main()) 