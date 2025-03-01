import subprocess
import sys
import os
import platform
import subprocess

def launch_browser(url="https://www.google.com"):
    """
    Launch the default browser to the specified URL using the appropriate
    system command based on the operating system.
    """
    try:
        print(f"Attempting to launch browser to {url}")
        
        # Determine the operating system
        system = platform.system()
        
        if system == 'Darwin':  # macOS
            subprocess.run(['open', url])
            print("Browser launched using 'open' command")
        elif system == 'Windows':
            subprocess.run(['start', url], shell=True)
            print("Browser launched using 'start' command")
        elif system == 'Linux':
            subprocess.run(['xdg-open', url])
            print("Browser launched using 'xdg-open' command")
        else:
            print(f"Unsupported operating system: {system}")
            return False
            
        return True
    except Exception as e:
        print(f"Error launching browser: {e}")
        return False

if __name__ == "__main__":
    # If run directly, launch browser to Google
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.google.com"
    launch_browser(url)
