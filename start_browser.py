#!/usr/bin/env python3
"""Direct script to start a browser with website blocking.
This bypasses the Flask application and directly uses the browser launching code.
"""

import asyncio
import os
import sys
from playwright.async_api import async_playwright

async def start_browser_async(blocked_websites, auto_reopen=True, max_reopens=20):
    """Start a browser with website blocking using Playwright
    
    Args:
        blocked_websites: List of websites to block
        auto_reopen: Whether to automatically reopen the browser if closed
        max_reopens: Maximum number of times to reopen the browser
    """
    reopen_count = 0
    last_url = 'https://www.google.com'  # Default starting URL - normal Google homepage
    
    # Global variable to store tabs across browser sessions
    global_tabs_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'global_tabs.txt')
    
    # Initialize or load saved tabs
    if reopen_count == 0 and os.path.exists(global_tabs_file):
        try:
            with open(global_tabs_file, 'r') as f:
                saved_tabs = f.read().splitlines()
                open_tabs = [url for url in saved_tabs if url and not url.startswith('about:')]
                if open_tabs:
                    print(f"Loaded {len(open_tabs)} saved tabs from previous session")
                else:
                    open_tabs = [last_url]  # Default if no valid tabs found
        except Exception as e:
            print(f"Error loading saved tabs: {e}")
            open_tabs = [last_url]  # Default if error loading tabs
    else:
        open_tabs = [last_url]  # Default for first launch
        
    print(f"\n==== BROWSER SESSION START ====\nAuto-reopen: {auto_reopen}, Max reopens: {max_reopens}\n")
    
    while True:  # Loop to allow reopening
        try:
            print("Initializing Playwright...")
            async with async_playwright() as p:
                print("Launching Chromium browser...")
                # Launch browser with stable configuration for reliable performance
                browser = await p.chromium.launch(
                    headless=False,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--no-first-run',
                        '--disable-extensions',  # Disable extensions for faster startup
                        '--disable-popup-blocking',  # Allow popups which YouTube might use
                        '--window-size=1280,720',  # Set window size
                        '--disable-infobars',  # Disable infobars
                        '--start-maximized'  # Start maximized
                    ]
                )
                print("Browser launched successfully")
                
                # Create a simple context with basic settings for stability
                context = await browser.new_context(
                    viewport={'width': 1280, 'height': 800}
                )
                page = await context.new_page()
                
                # Set up route handler to block specified websites
                async def route_handler(route):
                    url = route.request.url.lower()  # Convert URL to lowercase for case-insensitive matching
                    blocked = False
                    
                    # Check for special force close URL
                    if 'force-browser-close' in url:
                        print("Force close URL detected!")
                        nonlocal browser_closed
                        browser_closed = True
                        await route.fulfill(status=200, body="Closing browser...")
                        await browser.close()
                        return
                    
                    # Check if this is a resource that should never be blocked to prevent crashes
                    # Allow all JavaScript, CSS, and media resources to load to prevent crashes
                    resource_type = route.request.resource_type
                    safe_resources = ['script', 'stylesheet', 'media', 'font', 'websocket']
                    
                    if resource_type in safe_resources:
                        await route.continue_()
                        return
                    
                    # Special handling for navigation requests
                    if resource_type == 'document':
                        # Only block if it's a full navigation to a blocked site
                        # This allows typing in the URL bar without triggering blocks
                        for blocked_site in blocked_websites:
                            # Check if this is a complete URL to a blocked site
                            # Use more precise matching to avoid false positives
                            if blocked_site.lower() in url and (
                                f"://{blocked_site.lower()}" in url or 
                                f"www.{blocked_site.lower()}" in url
                            ):
                                print(f"Blocking navigation to: {route.request.url}")
                                blocked = True
                                break
                    else:
                        # For non-navigation resources, use standard blocking
                        for blocked_site in blocked_websites:
                            if blocked_site.lower() in url:
                                print(f"Blocking resource: {route.request.url}")
                                blocked = True
                                break
                    
                    if blocked:
                        await route.abort()
                    else:
                        await route.continue_()
                
                print("Setting up route handler for website blocking...")
                await context.route('**/*', route_handler)
                
                # Restore tabs from previous session or start with default URL
                if open_tabs:
                    print(f"Restoring {len(open_tabs)} tabs from previous session...")
                    
                    # Navigate to the first tab in the list
                    if open_tabs[0]:
                        print(f"Navigating to primary tab: {open_tabs[0]}")
                        try:
                            # Normal navigation for the first page
                            print(f"Navigating to first page: {open_tabs[0]}")
                            # Use a standard navigation approach with normal timeout
                            await page.goto(open_tabs[0], wait_until='domcontentloaded', timeout=30000)
                        except Exception as e:
                            print(f"Error navigating to {open_tabs[0]}: {e}")
                            # Fallback to default URL with normal navigation
                            print("Falling back to Google homepage")
                            await page.goto('https://www.google.com', wait_until='domcontentloaded', timeout=30000)
                    
                    # Open additional tabs if there were any
                    for i, tab_url in enumerate(open_tabs[1:], 1):
                        if tab_url:
                            print(f"Opening additional tab {i}: {tab_url}")
                            new_page = await context.new_page()
                            try:
                                # Normal navigation for additional tabs
                                print(f"Navigating to tab {i}: {tab_url}")
                                # Use a standard navigation approach with normal timeout
                                await new_page.goto(tab_url, wait_until='domcontentloaded', timeout=30000)
                            except Exception as e:
                                print(f"Error navigating to {tab_url}: {e}")
                                # Keep the tab open but show a blank page
                                print(f"Loading blank page for tab {i} due to error")
                                await new_page.goto('about:blank', wait_until='domcontentloaded', timeout=10000)
                else:
                    # Navigate to the last URL or default with normal navigation
                    print(f"No saved tabs found. Navigating to default URL: {last_url}...")
                    await page.goto(last_url, wait_until='domcontentloaded', timeout=30000)
                
                # Set up navigation listener to ONLY track the current URL and tabs
                # CRITICAL FIX: We're completely removing any browser close detection from navigation events
                async def on_frame_navigated(frame):
                    nonlocal last_url, open_tabs, global_tabs_file
                    if frame.is_main:
                        current_url = frame.url
                        if current_url and not current_url.startswith('about:'):
                            last_url = current_url
                            print(f"Navigation detected - Current URL: {last_url}")
                            print("NAVIGATION EVENT - BROWSER WILL REMAIN OPEN")
                            
                            # Add a simple message to the page
                            try:
                                await frame.evaluate("""
                                    console.log('Navigation detected to new page');
                                """)
                            except Exception as e:
                                print(f"Error injecting navigation protection: {e}")
                            
                            # Track open tabs for restoration
                            try:
                                # Get all pages (tabs) in the browser
                                all_pages = context.pages
                                # Get current tabs
                                current_tabs = []
                                
                                for tab in all_pages:
                                    tab_url = tab.url
                                    if tab_url and not tab_url.startswith('about:'):
                                        if tab_url not in current_tabs:
                                            current_tabs.append(tab_url)
                                
                                # Only update if tabs have changed
                                if set(current_tabs) != set(open_tabs):
                                    open_tabs = current_tabs.copy()
                                    
                                    # Save tabs to file for persistence between sessions
                                    if open_tabs:
                                        with open(global_tabs_file, 'w') as f:
                                            for url in open_tabs:
                                                f.write(f"{url}\n")
                                        print(f"Currently tracking {len(open_tabs)} tabs for restoration")
                            except Exception as e:
                                print(f"Error tracking tabs: {e}")
                            
                            # CRITICAL: NEVER check for force close during navigation
                            # We're completely removing any browser close detection from navigation events
                
                page.on("framenavigated", on_frame_navigated)
                
                # Add a visible message to the page without a close button
                blocked_sites_str = ', '.join(blocked_websites)
                await page.evaluate(
                    """
                    (blockedSites) => {
                        // Create the main notification div
                        const div = document.createElement('div');
                        div.style.position = 'fixed';
                        div.style.top = '0';
                        div.style.left = '0';
                        div.style.right = '0';
                        div.style.padding = '10px';
                        div.style.backgroundColor = '#4CAF50';
                        div.style.color = 'white';
                        div.style.fontSize = '16px';
                        div.style.zIndex = '9999';
                        div.style.textAlign = 'center';
                        div.style.boxShadow = '0 4px 8px rgba(0,0,0,0.3)';
                        
                        // Add the text message with stronger emphasis on navigation
                        div.innerHTML = 'Study Browser Active - Websites Blocked: ' + blockedSites + 
                                      ' <strong>(Browser will stay open when typing URLs or navigating between tabs)</strong>';
                        
                        document.body.appendChild(div);
                        
                        // Add a simple message about the browser being open
                        const messageDiv = document.createElement('div');
                        messageDiv.textContent = 'Browser is now open - you can navigate freely';
                        messageDiv.style.position = 'fixed';
                        messageDiv.style.bottom = '50px';
                        messageDiv.style.left = '0';
                        messageDiv.style.right = '0';
                        messageDiv.style.textAlign = 'center';
                        messageDiv.style.padding = '10px';
                        messageDiv.style.backgroundColor = '#4CAF50';
                        messageDiv.style.color = 'white';
                        messageDiv.style.zIndex = '9998';
                        document.body.appendChild(messageDiv);
                    }
                    """, 
                    blocked_sites_str
                )
                
                print("Browser is now open and ready for use")
                
                # Set up browser close detection
                browser_closed = False
                
                # CRITICAL FIX: The root issue is likely in the browser close detection
                # We need to completely disable the beforeunload event and only use
                # explicit browser disconnection events
                await page.evaluate("""
                    // DO NOT add any beforeunload handlers yet - they might be causing
                    // the immediate close issue
                    
                    // Add a simple close button
                    const closeButton = document.createElement('button');
                    closeButton.textContent = 'Close Browser';
                    closeButton.style.position = 'fixed';
                    closeButton.style.bottom = '10px';
                    closeButton.style.right = '10px';
                    closeButton.style.zIndex = '9999';
                    closeButton.style.padding = '8px 16px';
                    closeButton.style.backgroundColor = '#f44336';
                    closeButton.style.color = 'white';
                    closeButton.style.border = 'none';
                    closeButton.style.borderRadius = '4px';
                    closeButton.style.cursor = 'pointer';
                    closeButton.onclick = function() {
                        // Create a special element to signal browser to close
                        const forceCloseSignal = document.createElement('div');
                        forceCloseSignal.id = 'force-browser-close-signal';
                        forceCloseSignal.style.display = 'none';
                        document.body.appendChild(forceCloseSignal);
                    };
                    document.body.appendChild(closeButton);
                    
                    // Add keyboard shortcut handler (Ctrl+Q to quit)
                    document.addEventListener('keydown', function(event) {
                        if (event.ctrlKey && event.key === 'q') {
                            console.log('Ctrl+Q detected - closing browser');
                            const forceCloseSignal = document.createElement('div');
                            forceCloseSignal.id = 'force-browser-close-signal';
                            forceCloseSignal.style.display = 'none';
                            document.body.appendChild(forceCloseSignal);
                        }
                    });
                    
                    // Add a visible close button to make it clear how to close
                    const closeButton = document.createElement('button');
                    closeButton.id = 'browser-close-button';
                    closeButton.textContent = 'Close Browser';
                    closeButton.style.position = 'fixed';
                    closeButton.style.bottom = '10px';
                    closeButton.style.right = '10px';
                    closeButton.style.zIndex = '9999';
                    closeButton.style.padding = '8px 16px';
                    closeButton.style.backgroundColor = '#f44336';
                    closeButton.style.color = 'white';
                    closeButton.style.border = 'none';
                    closeButton.style.borderRadius = '4px';
                    closeButton.style.cursor = 'pointer';
                    closeButton.onclick = window.explicitlyCloseBrowser;
                    document.body.appendChild(closeButton);
                    
                    console.log('FIXED BROWSER CLOSE HANDLERS - Navigation will NEVER close the browser');
                """)
                
                async def on_browser_close():
                    nonlocal browser_closed, open_tabs, global_tabs_file
                    
                    # Mark the browser as closed and ensure we exit properly
                    browser_closed = True
                    print("\n**** Browser was closed by user ****")
                    
                    # Save all open tabs before closing
                    try:
                        # Get all pages (tabs) in the browser
                        all_pages = context.pages
                        # Clear the open_tabs list and refill with current tabs
                        open_tabs = []
                        
                        for tab in all_pages:
                            tab_url = tab.url
                            if tab_url and not tab_url.startswith('about:'):
                                if tab_url not in open_tabs:
                                    open_tabs.append(tab_url)
                        
                        # Save tabs to file for persistence between sessions
                        if open_tabs:
                            # Write tabs to global file
                            with open(global_tabs_file, 'w') as f:
                                for url in open_tabs:
                                    f.write(f"{url}\n")
                            
                            print(f"Saved {len(open_tabs)} tabs for restoration on next launch")
                            for i, url in enumerate(open_tabs):
                                print(f"  Tab {i+1}: {url}")
                    except Exception as e:
                        print(f"Error saving tabs: {e}")
                    
                    print("Starting reopen loop...")
                    
                    # Force cleanup to ensure the reopen loop starts promptly
                    try:
                        # Ensure the browser is fully closed
                        if browser.is_connected():
                            print("Browser still connected, forcing close...")
                            await browser.close()
                        
                        # Close the context as well
                        await context.close()
                    except Exception as e:
                        print(f"Error during cleanup: {e}")
                        
                    # Ensure the process exits cleanly to trigger reopen
                    print("Browser cleanup complete, reopen loop will start")
                

                # Listen for browser disconnection
                browser.on("disconnected", on_browser_close)
                
                # Wait for browser to be closed
                print("\nBrowser is open. Close the window to exit (or use Ctrl+Q or the Close button).")
                
                # Set up a periodic check for browser state
                check_interval = 0.3  # seconds - reduced for faster detection
                consecutive_failures = 0
                max_failures = 2  # Consider browser closed after this many consecutive failures
                
                while not browser_closed:
                    try:
                        # Check if browser is still connected
                        if not browser.is_connected():
                            browser_closed = True
                            print("Browser disconnection detected - explicit close by user")
                            break
                        
                        # CRITICAL FIX: We're completely changing how browser close is detected
                        # We'll ONLY check for our explicit close signal and ignore all other events
                        try:
                            # ONLY check for our explicit close button click
                            has_explicit_close = await page.evaluate("""
                                // Only return true if our explicit close button was clicked
                                return !!document.getElementById('force-browser-close-signal');
                            """)
                            
                            if has_explicit_close:
                                print("Explicit force close signal detected - user clicked close button!")
                                browser_closed = True
                                await browser.close()
                                break
                            
                            # If we get here, the browser is still open and responsive
                            # Reset failure counter
                            consecutive_failures = 0
                            
                            # Simple browser check
                            await page.evaluate("""
                                console.log('Browser is still responsive');
                            """)
                        except Exception as e:
                            # Completely ignore navigation errors
                            if 'Target closed' not in str(e) and 'Navigation failed' not in str(e):
                                consecutive_failures += 1
                                print(f"Browser check failure {consecutive_failures}/{max_failures}: {e}")
                                if consecutive_failures >= max_failures:
                                    print("Browser appears to be unresponsive - but NOT closing it")
                                    # Reset counter instead of closing
                                    consecutive_failures = 0
                                browser_closed = True
                                break
                                
                        await asyncio.sleep(check_interval)
                    except Exception as e:
                        print(f"Error checking browser state: {e}")
                        browser_closed = True
                        break
                
                print("Browser close detected, cleaning up...")
                
            # This code runs after the browser context is closed
            print("Browser context closed")
            
            # Handle auto-reopen
            if auto_reopen and reopen_count < max_reopens:
                reopen_count += 1
                print(f"\n==== REOPENING BROWSER TO {last_url} (Attempt {reopen_count}/{max_reopens}) ====\n")
                # Short delay before reopening
                await asyncio.sleep(0.5)
                continue  # Restart the loop to reopen
            else:
                if reopen_count >= max_reopens:
                    print(f"\n==== Maximum reopen attempts ({max_reopens}) reached. ====\n")
                else:
                    print("\n==== Auto-reopen is disabled. ====\n")
                break  # Exit the loop
                
        except Exception as e:
            print(f"\n==== ERROR in browser session: {e} ====\n")
            
            # If the error is related to a crash, we might need to reset the last_url
            # to avoid going back to a problematic page
            if "youtube" in last_url.lower() and "crashed" in str(e).lower():
                print("Detected crash on YouTube - resetting to Google homepage")
                last_url = 'https://www.google.com'
            
            # Handle auto-reopen after error
            if auto_reopen and reopen_count < max_reopens:
                reopen_count += 1
                print(f"\n==== REOPENING BROWSER AFTER ERROR TO {last_url} (Attempt {reopen_count}/{max_reopens}) ====\n")
                # Longer delay before reopening after a crash
                await asyncio.sleep(1.5)
                continue
            else:
                if reopen_count >= max_reopens:
                    print(f"\n==== Maximum reopen attempts ({max_reopens}) reached. ====\n")
                else:
                    print("\n==== Auto-reopen is disabled. ====\n")
                break

def main():
    # Default blocked websites
    blocked_websites = ["facebook.com", "twitter.com", "instagram.com"]
    
    # Parse command line arguments
    auto_reopen = True
    max_reopens = 5  # Reduced from 10 to prevent excessive crashes
    
    # Process command line arguments
    if len(sys.argv) > 1:
        # Check for special flags
        args = sys.argv[1:]
        filtered_args = []
        
        for arg in args:
            if arg == "--no-reopen":
                auto_reopen = False
            elif arg.startswith("--max-reopens="):
                try:
                    max_reopens = int(arg.split("=")[1])
                except (IndexError, ValueError):
                    print(f"Invalid max-reopens value: {arg}. Using default: {max_reopens}")
            else:
                filtered_args.append(arg)
        
        # Any remaining args are blocked websites
        if filtered_args:
            blocked_websites = filtered_args
    
    print(f"Starting browser with blocked websites: {blocked_websites}")
    print(f"Auto-reopen: {auto_reopen}, Max reopens: {max_reopens}")
    
    # Run the browser
    asyncio.run(start_browser_async(blocked_websites, auto_reopen, max_reopens))

if __name__ == "__main__":
    main()
