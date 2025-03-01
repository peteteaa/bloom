#!/usr/bin/env python3
"""Browser launcher with website blocking and auto-reopen functionality."""
import asyncio
import sys
import traceback
import os
import time
import json

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
            with open(GLOBAL_TABS_FILE, 'r') as f:
                saved_data = json.load(f)
                open_tabs = saved_data.get('tabs', [DEFAULT_URL])
                print(f"Loaded {len(open_tabs)} saved tabs")
        else:
            open_tabs = [DEFAULT_URL]
            print("No saved tabs found, using default")
    except Exception as e:
        print(f"Error loading saved tabs: {e}")
        open_tabs = [DEFAULT_URL]
    
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
                                    <p>Access to <strong>{url}</strong> has been blocked to help you stay focused.</p>
                                    <p>This site is on your blocked list: <strong>{blocked_site}</strong></p>
                                    </body></html>"""
                                )
                                return
                        await route.continue_()
                    
                    # Apply the blocking
                    await context.route("**/*", route_handler)
                
                # Function to save open tabs
                async def save_tabs():
                    tabs_to_save = []
                    for tab in current_tabs:
                        try:
                            url = await tab.evaluate("window.location.href")
                            if url and not url.startswith("about:"):
                                tabs_to_save.append(url)
                        except Exception as e:
                            print(f"Error saving tab: {e}")
                    
                    # Save tabs to file
                    try:
                        with open(GLOBAL_TABS_FILE, 'w') as f:
                            json.dump({"tabs": tabs_to_save}, f)
                        print(f"Saved {len(tabs_to_save)} tabs for future sessions")
                    except Exception as e:
                        print(f"Error saving tabs: {e}")
                    
                    return tabs_to_save
                
                # Open tabs from previous session
                if open_tabs:
                    first_page = await context.new_page()
                    current_tabs.append(first_page)
                    
                    try:
                        await first_page.goto(open_tabs[0], timeout=30000)
                        print(f"Opened first tab: {open_tabs[0]}")
                    except Exception as e:
                        print(f"Error opening first tab: {e}")
                        await first_page.goto(DEFAULT_URL)
                    
                    # Add browser UI elements
                    await first_page.evaluate("""
                        // Add a header banner
                        const banner = document.createElement('div');
                        banner.style.position = 'fixed';
                        banner.style.top = '0';
                        banner.style.left = '0';
                        banner.style.right = '0';
                        banner.style.backgroundColor = '#4CAF50';
                        banner.style.color = 'white';
                        banner.style.padding = '10px';
                        banner.style.zIndex = '9999';
                        banner.style.textAlign = 'center';
                        banner.style.fontSize = '14px';
                        banner.innerHTML = 'Focus Browser - Navigation allowed, website blocking active';
                        document.body.appendChild(banner);
                        
                        // Add visibility change detection
                        document.addEventListener('visibilitychange', function() {
                            if (document.visibilityState === 'hidden') {
                                console.log('Tab hidden, may open new tab if needed');
                                // Create a signal element to indicate this tab was hidden
                                const hiddenSignal = document.createElement('div');
                                hiddenSignal.id = 'tab-hidden-signal';
                                hiddenSignal.setAttribute('data-hidden-time', Date.now());
                                hiddenSignal.style.display = 'none';
                                document.body.appendChild(hiddenSignal);
                            } else if (document.visibilityState === 'visible') {
                                // Remove the hidden signal if tab becomes visible again
                                const hiddenSignal = document.getElementById('tab-hidden-signal');
                                if (hiddenSignal) {
                                    hiddenSignal.remove();
                                }
                            }
                        });
                        
                        // Add a close button
                        const closeBtn = document.createElement('button');
                        closeBtn.textContent = 'Close Browser';
                        closeBtn.style.position = 'fixed';
                        closeBtn.style.bottom = '10px';
                        closeBtn.style.right = '10px';
                        closeBtn.style.zIndex = '9999';
                        closeBtn.style.padding = '8px 16px';
                        closeBtn.style.backgroundColor = '#f44336';
                        closeBtn.style.color = 'white';
                        closeBtn.style.border = 'none';
                        closeBtn.style.borderRadius = '4px';
                        closeBtn.style.cursor = 'pointer';
                        closeBtn.onclick = () => {
                            // Display closing message
                            const overlay = document.createElement('div');
                            overlay.style.position = 'fixed';
                            overlay.style.top = '0';
                            overlay.style.left = '0';
                            overlay.style.width = '100%';
                            overlay.style.height = '100%';
                            overlay.style.backgroundColor = 'rgba(0,0,0,0.7)';
                            overlay.style.display = 'flex';
                            overlay.style.justifyContent = 'center';
                            overlay.style.alignItems = 'center';
                            overlay.style.zIndex = '10000';
                            overlay.innerHTML = '<div style="background-color: white; padding: 20px; border-radius: 5px; text-align: center;"><h2>Closing Browser</h2><p>Browser will automatically relaunch...</p></div>';
                            document.body.appendChild(overlay);
                            
                            // Create the close signal
                            const signal = document.createElement('div');
                            signal.id = 'browser-close-signal';
                            signal.setAttribute('data-reopen', 'true'); // Signal to reopen
                            signal.style.display = 'none';
                            document.body.appendChild(signal);
                            
                            // Give time for the message to be seen
                            setTimeout(() => {
                                window.close();
                            }, 1000);
                        };
                        document.body.appendChild(closeBtn);
                        
                        // Add keyboard shortcuts info
                        const shortcutInfo = document.createElement('div');
                        shortcutInfo.style.position = 'fixed';
                        shortcutInfo.style.bottom = '10px';
                        shortcutInfo.style.left = '10px';
                        shortcutInfo.style.zIndex = '9999';
                        shortcutInfo.style.padding = '8px';
                        shortcutInfo.style.backgroundColor = '#3498db';
                        shortcutInfo.style.color = 'white';
                        shortcutInfo.style.borderRadius = '4px';
                        shortcutInfo.style.fontSize = '12px';
                        shortcutInfo.innerHTML = 'Press <strong>Ctrl+Q</strong> to close browser';
                        document.body.appendChild(shortcutInfo);
                    """)
                    
                    # Open additional tabs
                    for i, tab_url in enumerate(open_tabs[1:], 1):
                        try:
                            print(f"Opening tab {i+1}: {tab_url}")
                            new_tab = await context.new_page()
                            current_tabs.append(new_tab)
                            await new_tab.goto(tab_url, timeout=30000)
                        except Exception as e:
                            print(f"Error opening tab {i+1}: {e}")
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
                
                # Main browser monitoring loop
                print("Browser open and running - monitoring for close events")
                while not browser_closed:
                    try:
                        # Check if browser was closed
                        if not browser.is_connected():
                            print("Browser disconnected - will relaunch automatically")
                            browser_closed = True
                            # Make sure we always reopen when browser is closed externally
                            if auto_reopen and reopen_count < max_reopens:
                                print("Scheduling browser relaunch...")
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
                            # Save tabs before closing
                            open_tabs = await save_tabs()
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
                                
                                # Add UI elements to new tab
                                await new_tab.evaluate("""
                                    // Add a header banner
                                    const banner = document.createElement('div');
                                    banner.style.position = 'fixed';
                                    banner.style.top = '0';
                                    banner.style.left = '0';
                                    banner.style.right = '0';
                                    banner.style.backgroundColor = '#4CAF50';
                                    banner.style.color = 'white';
                                    banner.style.padding = '10px';
                                    banner.style.zIndex = '9999';
                                    banner.style.textAlign = 'center';
                                    banner.style.fontSize = '14px';
                                    banner.innerHTML = 'Focus Browser - New Tab Opened Automatically';
                                    document.body.appendChild(banner);
                                    
                                    // Add close button
                                    const closeBtn = document.createElement('button');
                                    closeBtn.textContent = 'Close Browser';
                                    closeBtn.style.position = 'fixed';
                                    closeBtn.style.bottom = '10px';
                                    closeBtn.style.right = '10px';
                                    closeBtn.style.zIndex = '9999';
                                    closeBtn.style.padding = '8px 16px';
                                    closeBtn.style.backgroundColor = '#f44336';
                                    closeBtn.style.color = 'white';
                                    closeBtn.style.border = 'none';
                                    closeBtn.style.borderRadius = '4px';
                                    closeBtn.style.cursor = 'pointer';
                                    closeBtn.onclick = () => {
                                        // Display closing message
                                        const overlay = document.createElement('div');
                                        overlay.style.position = 'fixed';
                                        overlay.style.top = '0';
                                        overlay.style.left = '0';
                                        overlay.style.width = '100%';
                                        overlay.style.height = '100%';
                                        overlay.style.backgroundColor = 'rgba(0,0,0,0.7)';
                                        overlay.style.display = 'flex';
                                        overlay.style.justifyContent = 'center';
                                        overlay.style.alignItems = 'center';
                                        overlay.style.zIndex = '10000';
                                        overlay.innerHTML = '<div style="background-color: white; padding: 20px; border-radius: 5px; text-align: center;"><h2>Closing Browser</h2><p>Browser will automatically relaunch...</p></div>';
                                        document.body.appendChild(overlay);
                                        
                                        // Create the close signal
                                        const signal = document.createElement('div');
                                        signal.id = 'browser-close-signal';
                                        signal.setAttribute('data-reopen', 'true');
                                        signal.style.display = 'none';
                                        document.body.appendChild(signal);
                                        
                                        // Give time for the message to be seen
                                        setTimeout(() => {
                                            window.close();
                                        }, 1000);
                                    };
                                    document.body.appendChild(closeBtn);
                                """)
                                
                                # Update current tabs list
                                all_pages = context.pages
                            
                            # Update the current tabs list
                            current_tabs = all_pages
                            print(f"Tab count changed: now {len(current_tabs)} tabs")
                        
                        # Check for hidden tabs
                        all_hidden = True
                        if len(current_tabs) > 0:
                            for tab in current_tabs:
                                try:
                                    # Check if this tab has a hidden signal
                                    has_hidden_signal = await tab.evaluate("!!document.getElementById('tab-hidden-signal')")
                                    
                                    # If at least one tab is not hidden, we don't need to open a new one
                                    if not has_hidden_signal:
                                        all_hidden = False
                                        break
                                except Exception:
                                    # If we can't check, assume it's not hidden
                                    all_hidden = False
                            
                            # If all tabs are hidden, open a new tab
                            if all_hidden:
                                print("All tabs are hidden - opening a new visible tab")
                                try:
                                    new_tab = await context.new_page()
                                    await new_tab.goto(DEFAULT_URL)
                                    current_tabs.append(new_tab)
                                    
                                    # Add UI elements to the new tab
                                    await new_tab.evaluate("""
                                        // Add a header banner
                                        const banner = document.createElement('div');
                                        banner.style.position = 'fixed';
                                        banner.style.top = '0';
                                        banner.style.left = '0';
                                        banner.style.right = '0';
                                        banner.style.backgroundColor = '#3498db';
                                        banner.style.color = 'white';
                                        banner.style.padding = '10px';
                                        banner.style.zIndex = '9999';
                                        banner.style.textAlign = 'center';
                                        banner.style.fontSize = '14px';
                                        banner.innerHTML = 'Focus Browser - Auto-opened tab (other tabs were hidden)';
                                        document.body.appendChild(banner);
                                        
                                        // Add close button
                                        const closeBtn = document.createElement('button');
                                        closeBtn.textContent = 'Close Browser';
                                        closeBtn.style.position = 'fixed';
                                        closeBtn.style.bottom = '10px';
                                        closeBtn.style.right = '10px';
                                        closeBtn.style.zIndex = '9999';
                                        closeBtn.style.padding = '8px 16px';
                                        closeBtn.style.backgroundColor = '#f44336';
                                        closeBtn.style.color = 'white';
                                        closeBtn.style.border = 'none';
                                        closeBtn.style.borderRadius = '4px';
                                        closeBtn.style.cursor = 'pointer';
                                        closeBtn.onclick = () => {
                                            const signal = document.createElement('div');
                                            signal.id = 'browser-close-signal';
                                            signal.setAttribute('data-reopen', 'true');
                                            signal.style.display = 'none';
                                            document.body.appendChild(signal);
                                            
                                            // Overlay message
                                            const overlay = document.createElement('div');
                                            overlay.style.position = 'fixed';
                                            overlay.style.top = '0';
                                            overlay.style.left = '0';
                                            overlay.style.width = '100%';
                                            overlay.style.height = '100%';
                                            overlay.style.backgroundColor = 'rgba(0,0,0,0.7)';
                                            overlay.style.display = 'flex';
                                            overlay.style.justifyContent = 'center';
                                            overlay.style.alignItems = 'center';
                                            overlay.style.zIndex = '10000';
                                            overlay.innerHTML = '<div style="background-color: white; padding: 20px; border-radius: 5px; text-align: center;"><h2>Closing Browser</h2><p>Browser will automatically relaunch...</p></div>';
                                            document.body.appendChild(overlay);
                                            
                                            setTimeout(() => window.close(), 1000);
                                        };
                                        document.body.appendChild(closeBtn);
                                        
                                        // Add visibility change listener
                                        document.addEventListener('visibilitychange', function() {
                                            if (document.visibilityState === 'hidden') {
                                                const hiddenSignal = document.createElement('div');
                                                hiddenSignal.id = 'tab-hidden-signal';
                                                hiddenSignal.setAttribute('data-hidden-time', Date.now());
                                                hiddenSignal.style.display = 'none';
                                                document.body.appendChild(hiddenSignal);
                                            } else if (document.visibilityState === 'visible') {
                                                const hiddenSignal = document.getElementById('tab-hidden-signal');
                                                if (hiddenSignal) hiddenSignal.remove();
                                            }
                                        });
                                    """)
                                except Exception as e:
                                    print(f"Error opening new tab for hidden tabs: {e}")
                        
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
                    open_tabs = await save_tabs()
                    await browser.close()
                
                print("Browser session ended")
                
                # Handle auto-reopen
                if auto_reopen and reopen_count < max_reopens:
                    reopen_count += 1
                    print(f"Auto-reopening browser (attempt {reopen_count}/{max_reopens})")
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
                print(f"Reopening after error (attempt {reopen_count}/{max_reopens})")
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
