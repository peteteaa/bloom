# Focus Browser

A productivity-focused browser with website blocking and auto-reopen features to help maintain focus and prevent distractions.

## Features

- **Website Blocking**: Block distracting websites with a friendly block page
- **Auto-Reopen**: Browser automatically reopens if closed accidentally
- **Tab Management**: 
  - Automatically opens a new tab when all tabs are closed
  - Opens a new tab when all existing tabs are hidden
  - **Enhanced Tab Restoration**: Automatically saves and restores all open tabs when the browser is closed and reopened, ensuring no work is lost
- **User Interface**:
  - Status banner indicating when website blocking is active
  - Close button for explicitly closing the browser
  - Keyboard shortcuts (Ctrl+Q) for closing the browser

## File Descriptions

1. **task.py**: This is the main Flask application file that handles server-side logic, including API endpoints for managing tasks and blocked websites.

2. **debug_browser.py**: This file contains the logic for launching the browser with specified website blocking and auto-reopen functionality.

3. **start_browser.py**: This file is responsible for starting the browser process and managing command-line arguments for blocked websites and auto-reopen functionality.

4. **browser_launcher.py**: This file contains functions related to the browser's behavior, including opening and closing tabs, managing sessions, and handling events.

5. **app.js**: This is the main JavaScript file that manages the user interface, handles user interactions, and communicates with the Flask backend.

6. **styles.css**: This CSS file contains styles for the application, including the layout and appearance of the user interface elements.

7. **index.html**: This is the main HTML file that serves as the entry point for the application, containing the structure and layout for the user interface.

## Requirements

- Python 3.8+
- Playwright
- Flask

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/focus-browser.git
cd focus-browser
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install Playwright browsers:
```bash
playwright install
```

## Usage

### Starting the Server

```bash
python task.py
```

This will start a Flask server on http://127.0.0.1:5000/

### Starting the Browser

You can start the browser by:

1. Visiting http://127.0.0.1:5000/ and clicking the "Start Browser" button
2. Making a POST request to the API endpoint:
```bash
curl -X POST http://127.0.0.1:5000/api/start-browser
```

### Blocking Websites

You can configure blocked websites through the web interface or by passing them as command-line arguments when starting the browser directly:

```bash
python debug_browser.py facebook.com twitter.com instagram.com
```

## How It Works

- The browser is built using Playwright, a browser automation library
- Website blocking is implemented by intercepting requests to blocked domains
- Auto-reopen functionality monitors browser state and relaunches when needed
- Tab management ensures you always have at least one tab available

## License

MIT
