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
