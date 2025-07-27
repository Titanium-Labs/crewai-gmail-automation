#!/usr/bin/env python3
"""
Detailed inspection script to understand what's displayed on the Gmail CrewAI app page.
"""
import asyncio
import time
from playwright.async_api import async_playwright
import json

class DetailedInspector:
    def __init__(self, base_url="http://localhost:8501"):
        self.base_url = base_url

    async def inspect_page_content(self, page):
        """Get detailed information about page content"""
        print("🔍 DETAILED PAGE INSPECTION")
        print("="*60)
        
        # Get page title
        title = await page.title()
        print(f"📄 Page Title: {title}")
        
        # Get all text content
        text_content = await page.evaluate("() => document.body.innerText")
        lines = [line.strip() for line in text_content.split('\n') if line.strip()]
        print(f"\n📝 Page Text Content (first 30 lines):")
        for i, line in enumerate(lines[:30]):
            print(f"   {i+1:2d}: {line}")
        
        # Get all headings
        headings = await page.query_selector_all('h1, h2, h3, h4, h5, h6')
        print(f"\n📋 Headings Found ({len(headings)}):")
        for i, heading in enumerate(headings):
            tag_name = await heading.evaluate("el => el.tagName")
            text = await heading.text_content()
            print(f"   {tag_name}: {text}")
        
        # Get all buttons with their text
        buttons = await page.query_selector_all('button')
        print(f"\n🔘 Buttons Found ({len(buttons)}):")
        for i, button in enumerate(buttons):
            text = await button.text_content()
            is_disabled = await button.get_attribute('disabled')
            is_visible = await button.is_visible()
            print(f"   {i+1:2d}: '{text}' (disabled: {bool(is_disabled)}, visible: {is_visible})")
        
        # Get all inputs
        inputs = await page.query_selector_all('input, textarea, select')
        print(f"\n📝 Input Elements Found ({len(inputs)}):")
        for i, input_el in enumerate(inputs):
            tag_name = await input_el.evaluate("el => el.tagName")
            input_type = await input_el.get_attribute('type') or 'N/A'
            placeholder = await input_el.get_attribute('placeholder') or 'N/A'
            value = await input_el.input_value() if tag_name.lower() in ['input', 'textarea'] else 'N/A'
            is_visible = await input_el.is_visible()
            print(f"   {i+1:2d}: {tag_name} (type: {input_type}, placeholder: {placeholder}, visible: {is_visible})")
        
        # Check for Streamlit-specific elements
        streamlit_elements = {
            "stApp": '[data-testid="stApp"]',
            "stSidebar": '[data-testid="stSidebar"]',
            "stHeader": '[data-testid="stHeader"]',
            "stTabs": '[data-testid="stTabs"]',
            "stColumns": '[data-testid="column"]',
            "stError": '.stError',
            "stException": '.stException',
            "stAlert": '[data-testid="stAlert"]'
        }
        
        print(f"\n🎛️ Streamlit Elements:")
        for name, selector in streamlit_elements.items():
            elements = await page.query_selector_all(selector)
            print(f"   {name}: {len(elements)} found")
            if name == "stError" or name == "stException" or name == "stAlert":
                for el in elements:
                    error_text = await el.text_content()
                    print(f"     ⚠️ {error_text}")
        
        # Check for any error indicators in the HTML
        html_content = await page.content()
        error_keywords = ["error", "exception", "failed", "timeout", "not found", "invalid"]
        print(f"\n🚨 Error Keywords Check:")
        for keyword in error_keywords:
            count = html_content.lower().count(keyword)
            if count > 0:
                print(f"   '{keyword}': found {count} times")
        
        # Check current URL
        current_url = page.url
        print(f"\n🌐 Current URL: {current_url}")
        
        # Check for any query parameters
        if '?' in current_url:
            params = current_url.split('?')[1]
            print(f"   Query params: {params}")

    async def check_network_requests(self, page):
        """Monitor network requests for errors"""
        print(f"\n🌐 NETWORK MONITORING")
        print("="*60)
        
        failed_requests = []
        console_messages = []
        
        def handle_request_failed(request):
            failed_requests.append({
                'url': request.url,
                'method': request.method,
                'failure': request.failure
            })
        
        def handle_console(msg):
            console_messages.append({
                'type': msg.type,
                'text': msg.text,
                'location': str(msg.location) if hasattr(msg, 'location') else 'N/A'
            })
        
        page.on('requestfailed', handle_request_failed)
        page.on('console', handle_console)
        
        # Reload page to capture all requests
        await page.reload(wait_until='networkidle')
        await page.wait_for_timeout(3000)
        
        print(f"❌ Failed Requests ({len(failed_requests)}):")
        for req in failed_requests:
            print(f"   {req['method']} {req['url']} - {req['failure']}")
        
        print(f"\n💬 Console Messages ({len(console_messages)}):")
        for msg in console_messages:
            print(f"   [{msg['type']}] {msg['text']}")

    async def test_functionality(self, page):
        """Test basic functionality"""
        print(f"\n⚙️ FUNCTIONALITY TESTING")
        print("="*60)
        
        # Try to interact with visible elements
        try:
            # Look for a chat input (from placeholder "Ask your CrewAI agents anything...")
            chat_input = await page.query_selector('textarea[placeholder*="Ask your CrewAI agents"]')
            if chat_input and await chat_input.is_visible():
                print("✅ Found chat input - testing...")
                await chat_input.fill("Hello, this is a test message")
                value = await chat_input.input_value()
                print(f"   Input test: {'✅ Success' if value == 'Hello, this is a test message' else '❌ Failed'}")
                await chat_input.fill("")  # Clear
            else:
                print("❌ Chat input not found or not visible")
            
            # Test tabs if they exist
            tabs = await page.query_selector_all('[role="tab"]')
            if tabs:
                print(f"✅ Found {len(tabs)} tabs - testing first tab...")
                first_tab = tabs[0]
                tab_text = await first_tab.text_content()
                print(f"   Clicking tab: {tab_text}")
                await first_tab.click()
                await page.wait_for_timeout(1000)
                print("   ✅ Tab click successful")
            else:
                print("ℹ️ No tabs found")
                
            # Check if we can scroll
            print("✅ Testing page scroll...")
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(500)
            await page.evaluate("window.scrollTo(0, 0)")
            print("   ✅ Scroll test successful")
            
        except Exception as e:
            print(f"❌ Functionality test error: {str(e)}")

    async def save_page_info(self, page):
        """Save comprehensive page information"""
        print(f"\n💾 SAVING PAGE INFORMATION")
        print("="*60)
        
        # Save full HTML
        html_content = await page.content()
        with open("page_source.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        print("✅ Full HTML saved to: page_source.html")
        
        # Save page text
        text_content = await page.evaluate("() => document.body.innerText")
        with open("page_text.txt", "w", encoding="utf-8") as f:
            f.write(text_content)
        print("✅ Page text saved to: page_text.txt")
        
        # Take screenshot
        await page.screenshot(path="detailed_screenshot.png", full_page=True)
        print("✅ Screenshot saved to: detailed_screenshot.png")

    async def run_inspection(self):
        """Run complete inspection"""
        async with async_playwright() as p:
            print("🚀 Starting detailed app inspection...")
            
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            try:
                # Navigate to app
                print(f"🌐 Navigating to {self.base_url}")
                await page.goto(self.base_url, wait_until='networkidle')
                
                # Wait for app to load
                await page.wait_for_selector('[data-testid="stApp"]', timeout=10000)
                print("✅ App loaded successfully")
                
                # Run inspections
                await self.inspect_page_content(page)
                await self.check_network_requests(page)
                await self.test_functionality(page)
                await self.save_page_info(page)
                
            except Exception as e:
                print(f"❌ Critical error during inspection: {str(e)}")
                await page.screenshot(path="error_inspection_screenshot.png")
            
            finally:
                await browser.close()

async def main():
    """Main function"""
    print("Waiting for Streamlit app to be ready...")
    time.sleep(3)
    
    inspector = DetailedInspector()
    await inspector.run_inspection()
    
    print("\n" + "="*60)
    print("🎉 INSPECTION COMPLETE")
    print("="*60)
    print("Check the generated files:")
    print("  - page_source.html (full HTML source)")
    print("  - page_text.txt (visible text content)")
    print("  - detailed_screenshot.png (visual screenshot)")

if __name__ == "__main__":
    asyncio.run(main()) 