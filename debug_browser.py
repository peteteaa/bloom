#!/usr/bin/env python3
"""Browser launcher with website blocking and auto-reopen functionality."""
import asyncio
import sys
import traceback
import os
import time
import json
from datetime import datetime

# Configuration
MAX_REOPENS = 10
REOPEN_DELAY = 1.0  # seconds
DEFAULT_URL = 'https://www.google.com'
GLOBAL_TABS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'global_tabs.json')

async def start_browser(blocked_websites=None, auto_reopen=True, max_reopens=MAX_REOPENS):
    """Launch a browser with website blocking and auto-reopen functionality."""
    print(f"=== BROWSER SESSION ===")
    print(f"Auto-reopen: {auto_reopen}")
    print(f"Max reopens: {max_reopens}")
    print(f"Blocked websites: {blocked_websites}")
    
    # Initialize variables
    if blocked_websites is None:
        blocked_websites = []
    reopen_count = 0
    open_tabs = []
    
    # Try to load saved tabs
    try:
        if os.path.exists(GLOBAL_TABS_FILE):
            print(f">>> Found saved tabs file: {GLOBAL_TABS_FILE}")
            with open(GLOBAL_TABS_FILE, 'r') as f:
                saved_data = json.load(f)
                open_tabs = saved_data.get('tabs', [DEFAULT_URL])
                tab_info = saved_data.get('tab_info', [])
                saved_time = saved_data.get('datetime', 'unknown time')
                
                # Print detailed debug info about loaded tabs
                print(f">>> LOADED {len(open_tabs)} saved tabs from {saved_time}")
                print(f">>> TAB URLs: {open_tabs}")
                print(f">>> GOT {len(tab_info)} tab_info items")
                # Print each tab's info
                for i, tab in enumerate(tab_info):
                    print(f">>>   TAB {i+1}: {tab.get('url')}")
                
                # Ensure we have at least some tabs to open
                if not open_tabs:
                    print(">>> No valid tabs found in saved file, using default")
                    open_tabs = [DEFAULT_URL]
        else:
            open_tabs = [DEFAULT_URL]
            tab_info = []
            print(">>> No saved tabs file found, using default URL")
    except Exception as e:
        print(f">>> ERROR loading saved tabs: {e}")
        print(f">>> Using default URL instead")
        open_tabs = [DEFAULT_URL]
        tab_info = []
    
    while True:  # Main browser session loop for reopening
        try:
            # Import playwright
            from playwright.async_api import async_playwright
            
            async with async_playwright() as p:
                print(f"\n--- Browser Session {reopen_count + 1} ---")
                
                # Launch browser
                browser_args = [
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-extensions',
                    '--disable-popup-blocking',
                    '--start-maximized',
                    '--disable-infobars',
                    '--disable-dev-shm-usage'
                ]
                
                browser = await p.chromium.launch(
                    headless=False,
                    args=browser_args
                )
                
                # Create a context and page
                context = await browser.new_context()
                current_tabs = []
                last_save_time = time.time()  # Track when we last saved tabs
                
                # Set up page event handlers
                async def handle_page_created(page):
                    print("New page created")
                    # Set up event listeners for this page
                    page.on("load", lambda: asyncio.create_task(handle_page_loaded(page)))
                    
                async def handle_page_loaded(page):
                    print("Page loaded/refreshed")
                    await track_page_url(page)
                    
                # Listen for new pages
                context.on("page", lambda page: asyncio.create_task(handle_page_created(page)))
                
                # Set up route handler for website blocking
                if blocked_websites:
                    async def route_handler(route):
                        url = route.request.url.lower()
                        for blocked_site in blocked_websites:
                            if blocked_site.lower() in url:
                                print(f"Blocking access to {url}")
                                # Serve a block page instead of just aborting
                                await route.fulfill(
                                    status=200,
                                    content_type="text/html",
                                    body=f"""<html><body style='font-family: Arial; text-align: center;'>
                                    <h1 style='color: #f44336; margin-top: 50px;'>Website Blocked</h1>
                                    <p>Access to <strong>{url}</strong> has been blocked to help you stay on track with your studies.</p>
                                    <p>This site is on your blocked list: <strong>{blocked_site}</strong></p>
                                    </body></html>"""
                                )
                                return
                        await route.continue_()
                    
                    # Apply the blocking
                    await context.route("**/*", route_handler)
                
                # Track page URLs and states
                tab_states = {}
                
                # Add debug print to show tab tracking is initialized
                print("Tab state tracking initialized")
                
                # Function to track page URL changes
                async def track_page_url(page):
                    try:
                        url = await page.evaluate("window.location.href")
                        if url and not url.startswith("about:"):
                            page_id = id(page)
                            tab_states[page_id] = {
                                'url': url,
                                'timestamp': time.time()
                            }
                            return url
                    except Exception as e:
                        print(f"Error tracking page URL: {e}")
                    return None
                
                # Function to save open tabs
                async def save_tabs(force_save=False):
                    print(">>> DEBUG: save_tabs called with force_save=", force_save)
                    print(f">>> DEBUG: Current tabs count: {len(current_tabs)}")
                    tabs_to_save = []
                    for tab in current_tabs:
                        try:
                            # Update tab state before saving
                            url = await track_page_url(tab)
                            print(f">>> DEBUG: Tab URL tracked: {url}")
                            if url:
                                tabs_to_save.append(url)
                        except Exception as e:
                            print(f"Error saving tab: {e}")
                    
                    # Don't save empty tab lists unless forced
                    if not tabs_to_save and not force_save:
                        print(">>> WARNING: No valid tabs to save")
                        return tabs_to_save
                        
                    # Ensure we're not saving 'about:blank' tabs
                    tabs_to_save = [url for url in tabs_to_save if url and url != 'about:blank']
                    
                    # If we filtered out all tabs, but force_save is true, use default
                    if not tabs_to_save and force_save:
                        print(">>> No valid tabs after filtering, using default URL")
                        tabs_to_save = [DEFAULT_URL]
                    
                    # Save tabs to file
                    try:
                        # If no tabs to save but force_save is True, use the default URL
                        if not tabs_to_save and force_save:
                            tabs_to_save = [DEFAULT_URL]
                        
                        # Get additional state information for each tab
                        tab_info = []
                        for i, url in enumerate(tabs_to_save):
                            # Try to get scroll position and form input values
                            tab_data = {'url': url}
                            try:
                                if i < len(current_tabs):
                                    # Get scroll position
                                    scroll_pos = await current_tabs[i].evaluate("""
                                        () => {
                                            return {
                                                x: window.scrollX || window.pageXOffset,
                                                y: window.scrollY || window.pageYOffset
                                            };
                                        }
                                    """)
                                    tab_data['scroll'] = scroll_pos
                            except Exception as e:
                                print(f"Error capturing tab state: {e}")
                            
                            tab_info.append(tab_data)
                        
                        # Save all tab data with state information
                        with open(GLOBAL_TABS_FILE, 'w') as f:
                            # Create a more descriptive saved state
                            saved_state = {
                                "tabs": tabs_to_save, 
                                "tab_info": tab_info,
                                "timestamp": time.time(),
                                "datetime": datetime.now().isoformat(),
                                "tab_count": len(tabs_to_save)
                            }
                            json.dump(saved_state, f, indent=2)  # Pretty print for debugging
                        print(f">>> SAVED {len(tabs_to_save)} tabs to {GLOBAL_TABS_FILE}")
                        print(f">>> TAB URLs: {tabs_to_save}")
                    except Exception as e:
                        print(f"Error saving tabs: {e}")
                    
                    return tabs_to_save
                
                # Open tabs from previous session
                # Function to handle when a page finishes loading
                async def handle_page_loaded(page):
                    try:
                        url = await track_page_url(page)
                        print(f"Page loaded: {url}")
                        # Save tabs on each page load
                        await save_tabs(force_save=True)
                    except Exception as e:
                        print(f"Error in page load handler: {e}")
                
                # Set up event handlers for page creation
                async def handle_new_page(new_page):
                    print(f"New page created: tracking it")
                    if new_page not in current_tabs:
                        current_tabs.append(new_page)
                    
                    # Always navigate to Google.com for any new page
                    try:
                        await new_page.goto(DEFAULT_URL, timeout=30000)
                        print(f"Navigated new page to Google: {DEFAULT_URL}")
                    except Exception as e:
                        print(f"Error navigating to Google: {e}")
                    
                    # Immediately start tracking this page
                    url = await track_page_url(new_page)
                    print(f"New page URL: {url}")
                    # Set up automatic state saving on page load
                    new_page.on("load", lambda: asyncio.create_task(handle_page_loaded(new_page)))
                
                # Set up context to detect new pages
                context.on("page", lambda new_page: asyncio.create_task(handle_new_page(new_page)))
                print("Page creation tracking is active")
                
                # Print detailed debug info about tab restoration
                print(f">>> RESTORING TABS: Found {len(open_tabs)} tabs to restore")
                print(f">>> TABS TO RESTORE: {', '.join(open_tabs)}")
                print(f">>> TAB INFO COUNT: {len(tab_info) if 'tab_info' in locals() else 'NOT_FOUND'}")
                
                if open_tabs:
                    print(f">>> OPENING FIRST TAB: Always using Google instead of {open_tabs[0]}")
                    first_page = await context.new_page()
                    current_tabs.append(first_page)
                    # Manually track the first page
                    asyncio.create_task(handle_new_page(first_page))
                    
                    try:
                        await first_page.goto(DEFAULT_URL, timeout=30000)
                        print(f"Opened first tab to Google: {DEFAULT_URL}")
                        
                        # Restore first tab's state if available
                        if tab_info and len(tab_info) > 0:
                            first_tab_data = tab_info[0]
                            
                            # Restore scroll position
                            if 'scroll' in first_tab_data:
                                try:
                                    scroll_pos = first_tab_data['scroll']
                                    await first_page.evaluate(
                                        f"window.scrollTo({scroll_pos['x']}, {scroll_pos['y']})"
                                    )
                                    print(f"Restored scroll position for first tab")
                                except Exception as e:
                                    print(f"Error restoring first tab scroll position: {e}")
                    except Exception as e:
                        print(f"Error opening first tab: {e}")
                        # Still try to go to Google even on error
                        try:
                            await first_page.goto(DEFAULT_URL, timeout=30000)
                            print(f"Opened first tab to Google after error")
                        except Exception as e2:
                            print(f"Failed to open Google after error: {e2}")
                    
                    # Open additional tabs
                    if len(open_tabs) > 1:
                        print(f">>> RESTORING {len(open_tabs)-1} ADDITIONAL TABS")
                    
                    for i, tab_url in enumerate(open_tabs[1:], 1):
                        try:
                            print(f">>> OPENING TAB {i+1}: Always using Google instead of {tab_url}")
                            new_tab = await context.new_page()
                            current_tabs.append(new_tab)
                            # Set up event handlers before navigation using a function to capture the correct tab reference
                            def create_load_handler(tab):
                                return lambda: asyncio.create_task(handle_page_loaded(tab))
                            
                            # Use the function to create a properly scoped handler
                            new_tab.on("load", create_load_handler(new_tab))
                            
                            # Always navigate to Google instead of the saved URL
                            await new_tab.goto(DEFAULT_URL, timeout=30000)
                            print(f">>> SUCCESSFULLY OPENED TAB {i+1} TO GOOGLE")
                            
                            # Force track this tab's URL
                            await track_page_url(new_tab)
                            
                            # Restore tab state if available
                            if len(tab_info) > i:
                                tab_data = tab_info[i]
                                
                                # Restore scroll position
                                if 'scroll' in tab_data:
                                    try:
                                        scroll_pos = tab_data['scroll']
                                        await new_tab.evaluate(
                                            f"window.scrollTo({scroll_pos['x']}, {scroll_pos['y']})"
                                        )
                                        print(f"Restored scroll position for tab {i+1}")
                                    except Exception as e:
                                        print(f"Error restoring scroll position: {e}")
                                        
                            # Set up event listener for this specific tab
                            await new_tab.evaluate("""
                                window.addEventListener('beforeunload', function(e) {
                                    // Signal that we're about to unload this page
                                    console.log('Tab is being unloaded - should save state');
                                });
                            """)
                        except Exception as e:
                            print(f">>> ERROR opening tab {i+1}: {e}")
                            print(f">>> Will try to create a new tab with default URL instead")
                            try:
                                # Try to create a new tab with the default URL instead
                                new_tab = await context.new_page()
                                current_tabs.append(new_tab)
                                await new_tab.goto(DEFAULT_URL, timeout=30000)
                                print(f">>> Created replacement tab with default URL")
                            except Exception as fallback_error:
                                print(f">>> CRITICAL ERROR: Could not create fallback tab: {fallback_error}")
                else:
                    # Just open a single tab with the default URL
                    first_page = await context.new_page()
                    current_tabs.append(first_page)
                    await first_page.goto(DEFAULT_URL)
                    print(f"Opened default page: {DEFAULT_URL}")
                
                # Add keyboard shortcut listener to all pages
                for page in current_tabs:
                    await page.keyboard.down('Control')
                    await page.keyboard.press('KeyQ')
                    await page.keyboard.up('Control')
                
                # Track browser state
                browser_closed = False
                
                # Set up a dedicated periodic tab saver
                async def periodic_tab_saver():
                    while not browser_closed:
                        try:
                            # Save tabs every 10 seconds
                            await asyncio.sleep(10)  # More frequent saves
                            if current_tabs:
                                print("Periodic tab save triggered")
                                await save_tabs(force_save=True)
                        except Exception as e:
                            print(f"Error in periodic tab saver: {e}")
                            await asyncio.sleep(1)  # Sleep on error
                
                # Start the periodic saver as a background task
                tab_save_task = asyncio.create_task(periodic_tab_saver())
                print(">>> PERIODIC TAB SAVER STARTED <<<")
                
                # Main browser monitoring loop
                print("Browser open and running - monitoring for close events")
                print(">>> DEBUG: Browser is now fully initialized and running")
                print(f">>> DEBUG: Current tabs: {len(current_tabs)}")
                while not browser_closed:
                    try:
                        # Check if browser was closed
                        if not browser.is_connected():
                            print("Browser disconnected - will relaunch automatically")
                            browser_closed = True
                            
                            # Try to save tabs before proceeding - CRITICAL SAVE POINT
                            try:
                                # Extra forceful save to make absolutely sure tabs are saved
                                print("CRITICAL: Performing emergency tab save before browser disconnection")
                                
                                # First make a direct attempt to save the global_tabs.json file
                                # even if save_tabs function has issues
                                emergency_tabs = []
                                for tab in current_tabs:
                                    try:
                                        page_id = id(tab)
                                        if page_id in tab_states:
                                            emergency_tabs.append(tab_states[page_id]['url'])
                                    except Exception:
                                        pass  # Ignore errors in emergency tab collection
                                
                                if emergency_tabs:
                                    try:
                                        with open(GLOBAL_TABS_FILE, 'w') as f:
                                            json.dump({
                                                "tabs": emergency_tabs,
                                                "tab_info": [{'url': url} for url in emergency_tabs],
                                                "timestamp": time.time(),
                                                "emergency": True
                                            }, f)
                                        print(f"EMERGENCY: Saved {len(emergency_tabs)} tabs directly to file")
                                    except Exception as direct_e:
                                        print(f"CRITICAL ERROR: Even emergency save failed: {direct_e}")
                                
                                # Now try the regular save
                                open_tabs = await save_tabs(force_save=True)
                                print(f"Saved {len(open_tabs)} tabs before browser disconnection")
                            except Exception as e:
                                print(f"Failed to save tabs on disconnection: {e}")
                            
                            # Make sure we always reopen when browser is closed externally
                            if auto_reopen and reopen_count < max_reopens:
                                print(">>> SCHEDULING BROWSER RELAUNCH...")
                                print(">>> TABS WILL BE RESTORED FROM: " + GLOBAL_TABS_FILE)
                                # Force reload of tabs from file
                                try:
                                    if os.path.exists(GLOBAL_TABS_FILE):
                                        with open(GLOBAL_TABS_FILE, 'r') as f:
                                            saved_data = json.load(f)
                                            open_tabs = saved_data.get('tabs', [DEFAULT_URL])
                                            tab_info = saved_data.get('tab_info', [])
                                            saved_time = saved_data.get('datetime', 'unknown time')
                                            print(f">>> RELAUNCH: Will restore {len(open_tabs)} tabs: {open_tabs}")
                                except Exception as e:
                                    print(f">>> ERROR reloading tabs for relaunch: {e}")
                            else:
                                print("Warning: Auto-reopen limit reached or disabled")
                            break
                        
                        # Check for explicit close signal
                        has_close_signal = False
                        should_reopen = True  # Default to reopen when closed
                        for page in current_tabs:
                            try:
                                close_signal_check = await page.evaluate("""
                                    () => {
                                        const signal = document.getElementById('browser-close-signal');
                                        if (signal) {
                                            return {
                                                exists: true,
                                                reopen: signal.getAttribute('data-reopen') === 'true'
                                            };
                                        }
                                        return { exists: false, reopen: true };
                                    }
                                """)
                                
                                if close_signal_check['exists']:
                                    has_close_signal = True
                                    should_reopen = close_signal_check['reopen']
                                    break
                            except Exception as e:
                                # Page might be closed
                                print(f"Error checking close signal: {e}")
                        
                        if has_close_signal:
                            print(f"Explicit close signal detected. Reopen: {should_reopen}")
                            browser_closed = True
                            # Save tabs before closing with force_save=True to ensure they're saved
                            open_tabs = await save_tabs(force_save=True)
                            print(f"Saved {len(open_tabs)} tabs before closing browser")
                            await browser.close()
                            
                            # If should_reopen is False, break out of the reopen loop
                            if not should_reopen:
                                print("Browser will not be reopened as requested")
                                return  # Exit the function completely
                            
                            print("Browser will be reopened after closing")
                            break
                        
                        # Check for new tabs and ensure we always have at least one tab open
                        all_pages = context.pages
                        if len(all_pages) != len(current_tabs):
                            # If tab count decreased (tab was closed)
                            if len(all_pages) < len(current_tabs) and len(all_pages) == 0:
                                print("All tabs were closed - opening a new tab")
                                new_tab = await context.new_page()
                                await new_tab.goto(DEFAULT_URL)
                                current_tabs.append(new_tab)
                            
                            # Update the current tabs list
                            current_tabs = all_pages
                            print(f"Tab count changed: now {len(current_tabs)} tabs")
                            
                            # Save tabs whenever the tab count changes
                            await save_tabs()
                            
                        # Periodically save tabs (every 30 seconds)
                        current_time = time.time()
                        if current_time - last_save_time > 30:  # 30 seconds
                            await save_tabs()
                            last_save_time = current_time
                        
                        # Short delay before next check
                        await asyncio.sleep(0.5)
                        
                    except Exception as e:
                        print(f"Error in browser monitoring: {e}")
                        # Only break if it's a fatal error
                        if 'Target closed' in str(e):
                            browser_closed = True
                            break
                
                # Browser closed, save tabs for reopening
                if not browser_closed:
                    # Force save tabs before closing
                    print(">>> FORCE SAVING TABS BEFORE BROWSER CLOSE")
                    open_tabs = await save_tabs(force_save=True)
                    await browser.close()
                
                print("Browser session ended")
                
                # Handle auto-reopen
                if auto_reopen and reopen_count < max_reopens:
                    reopen_count += 1
                    print(f">>> AUTO-REOPENING BROWSER (attempt {reopen_count}/{max_reopens})")
                    print(f">>> WILL RESTORE TABS FROM: {GLOBAL_TABS_FILE}")
                    
                    # Force reload tabs from file before continuing
                    try:
                        if os.path.exists(GLOBAL_TABS_FILE):
                            print(f">>> RELAUNCH: Reading tabs from {GLOBAL_TABS_FILE}")
                            with open(GLOBAL_TABS_FILE, 'r') as f:
                                saved_data = json.load(f)
                                open_tabs = saved_data.get('tabs', [DEFAULT_URL])
                                tab_info = saved_data.get('tab_info', [])
                                saved_time = saved_data.get('datetime', 'unknown time')
                                print(f">>> RELAUNCH: Found {len(open_tabs)} tabs saved at {saved_time}")
                                print(f">>> RELAUNCH: Will restore tabs: {open_tabs}")
                                
                                # Ensure we have valid tabs
                                if not open_tabs or all(not url or url == 'about:blank' for url in open_tabs):
                                    print(">>> RELAUNCH: No valid tabs found, using default URL")
                                    open_tabs = [DEFAULT_URL]
                                    tab_info = []
                    except Exception as e:
                        print(f">>> ERROR reloading tabs for relaunch: {e}")
                        
                    await asyncio.sleep(REOPEN_DELAY)
                    continue
                else:
                    print("Not reopening browser - session complete")
                    break
                    
        except Exception as e:
            print(f"Critical error in browser session: {e}")
            print(traceback.format_exc())
            
            if auto_reopen and reopen_count < max_reopens:
                reopen_count += 1
                print(f">>> REOPENING AFTER ERROR (attempt {reopen_count}/{max_reopens})")
                print(f">>> WILL RESTORE TABS FROM: {GLOBAL_TABS_FILE}")
                
                # Force reload tabs from file before continuing
                try:
                    if os.path.exists(GLOBAL_TABS_FILE):
                        with open(GLOBAL_TABS_FILE, 'r') as f:
                            saved_data = json.load(f)
                            open_tabs = saved_data.get('tabs', [DEFAULT_URL])
                            tab_info = saved_data.get('tab_info', [])
                            print(f">>> RELAUNCH AFTER ERROR: Will restore {len(open_tabs)} tabs: {open_tabs}")
                except Exception as e:
                    print(f">>> ERROR reloading tabs for error recovery: {e}")
                    
                await asyncio.sleep(REOPEN_DELAY)
            else:
                print("Too many errors or auto-reopen disabled")
                break

async def main():
    # Parse command-line arguments
    args = sys.argv[1:]
    
    # Check for control flags
    auto_reopen = '--no-reopen' not in args
    if '--no-reopen' in args:
        args.remove('--no-reopen')
    
    max_reopens = MAX_REOPENS
    for arg in args:
        if arg.startswith('--max-reopens='):
            try:
                max_reopens = int(arg.split('=')[1])
                args.remove(arg)
                break
            except (ValueError, IndexError):
                pass
    
    # Remaining args are blocked websites
    blocked_websites = [site for site in args if site and not site.startswith('--')]
    
    await start_browser(blocked_websites, auto_reopen, max_reopens)

if __name__ == "__main__":
    print("Starting browser with blocking and auto-reopen...")
    asyncio.run(main())
    print("Browser session completed.")
