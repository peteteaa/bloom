from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
import json
import asyncio
import threading
import traceback
import os
import subprocess
from flask import Flask, request, jsonify, render_template, send_from_directory
from playwright.async_api import async_playwright
from browser_launcher import launch_browser
from flask_cors import CORS

app = Flask(__name__, static_url_path='/static')
# Enable CORS for all routes
CORS(app)

# Store tasks, classes, assignments, and preferences in memory
tasks = []
classes = []
preferences = {
    "schedule_preference": "balanced",  # Options: "earlier", "later", "balanced"
    "blocked_websites": []  # List of websites to block
}

# Global variable to store blocked websites
blocked_websites = ["facebook.com", "twitter.com", "instagram.com"]

class Task:
    def __init__(self, title, due_date, time_needed, priority, description=None, blocked_websites=None):
        self.title = title
        self.due_date = due_date
        self.time_needed = float(time_needed)  # hours needed
        self.priority = int(priority)  # 1-5, 5 being highest
        self.description = description
        self.scheduled_times = []  # List of scheduled study sessions
        self.blocked_websites = blocked_websites or []  # Websites to block during study sessions for this task
        self.browser_sessions = []  # List of browser sessions associated with this task
        
    def update(self, title=None, due_date=None, time_needed=None, priority=None, description=None, blocked_websites=None):
        """Update task properties"""
        if title is not None:
            self.title = title
        if due_date is not None:
            self.due_date = due_date
        if time_needed is not None:
            self.time_needed = float(time_needed)
        if priority is not None:
            self.priority = int(priority)
        if description is not None:
            self.description = description
        if blocked_websites is not None:
            self.blocked_websites = blocked_websites
        return self

class Class:
    def __init__(self, name, days, start_time, end_time, location=None):
        self.name = name
        self.days = days  # List of weekday indices (0=Monday, 6=Sunday)
        self.start_time = start_time  # Format: 'HH:MM'
        self.end_time = end_time  # Format: 'HH:MM'
        self.location = location

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    events = []
    
    # Add tasks and study sessions
    for i, task in enumerate(tasks):
        # Add due date (red)
        events.append({
            'title': f'Due: {task.title}',
            'start': task.due_date + 'T23:59:00',
            'backgroundColor': '#dc3545',
            'borderColor': '#dc3545',
            'allDay': True,
            'taskId': i  # Add task ID to the event
        })
        
        # Add study sessions (blue)
        for session in task.scheduled_times:
            events.append({
                'title': f'Study: {task.title}',
                'start': session['start'],
                'end': session['end'],
                'backgroundColor': '#007bff',
                'borderColor': '#007bff',
                'taskId': i  # Add task ID to the event
            })
    
    # Add class schedules (green)
    # We'll add recurring events for each class for the next 4 weeks
    weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    today = datetime.now().date()
    
    # Get the date range from query parameters if provided
    start_date_str = request.args.get('start')
    end_date_str = request.args.get('end')
    
    if start_date_str and end_date_str:
        try:
            # Parse the date range
            if 'T' in start_date_str:
                start_date = datetime.fromisoformat(start_date_str.replace('Z', '')).date()
            else:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                
            if 'T' in end_date_str:
                end_date = datetime.fromisoformat(end_date_str.replace('Z', '')).date()
            else:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            # Default to 4 weeks if parsing fails
            start_date = today
            end_date = today + timedelta(days=28)
    else:
        # Default to 4 weeks if not provided
        start_date = today
        end_date = today + timedelta(days=28)
    
    # Generate class events for the date range
    for cls in classes:
        for day_idx in cls.days:
            # Find the next occurrence of this weekday
            days_ahead = (day_idx - today.weekday()) % 7
            next_day = today + timedelta(days=days_ahead)
            
            # Generate recurring events for this class
            current_date = next_day
            while current_date <= end_date:
                if current_date >= start_date:
                    class_start = f"{current_date.isoformat()}T{cls.start_time}:00"
                    class_end = f"{current_date.isoformat()}T{cls.end_time}:00"
                    
                    location_text = f" ({cls.location})" if cls.location else ""
                    events.append({
                        'title': f"Class: {cls.name}{location_text}",
                        'start': class_start,
                        'end': class_end,
                        'backgroundColor': '#28a745',  # Green
                        'borderColor': '#28a745',
                        'classId': classes.index(cls)  # Store index for potential deletion
                    })
                
                # Move to next week
                current_date += timedelta(days=7)
    
    return jsonify(events)

@app.route('/api/tasks', methods=['POST'])
def add_task():
    data = request.json
    task = Task(
        title=data['title'],
        due_date=data['dueDate'],
        time_needed=data['timeNeeded'],
        priority=data['priority'],
        description=data.get('description', ''),
        blocked_websites=data.get('blockedWebsites', [])
    )
    tasks.append(task)
    schedule_study_sessions()  # Recalculate all study sessions
    return jsonify({'status': 'success', 'taskId': len(tasks) - 1})

def is_time_slot_available(start_time, end_time, existing_sessions):
    """Check if a time slot is available and doesn't conflict with classes."""
    start = datetime.strptime(start_time, '%Y-%m-%dT%H:%M:%S')
    end = datetime.strptime(end_time, '%Y-%m-%dT%H:%M:%S')
    
    # Check against existing study sessions
    for session in existing_sessions:
        session_start = datetime.strptime(session['start'], '%Y-%m-%dT%H:%M:%S')
        session_end = datetime.strptime(session['end'], '%Y-%m-%dT%H:%M:%S')
        
        # Check for overlap with other study sessions
        if (start < session_end and end > session_start):
            return False
    
    # Check against class schedules
    for cls in classes:
        # Check if the day of the week matches any class days
        if start.weekday() in cls.days:
            # Parse class times
            class_start_hour, class_start_minute = map(int, cls.start_time.split(':'))
            class_end_hour, class_end_minute = map(int, cls.end_time.split(':'))
            
            # Create datetime objects for class times on the same day as start
            class_start = start.replace(
                hour=class_start_hour, 
                minute=class_start_minute, 
                second=0, 
                microsecond=0
            )
            class_end = start.replace(
                hour=class_end_hour, 
                minute=class_end_minute, 
                second=0, 
                microsecond=0
            )
            
            # Check for overlap with class
            if (start < class_end and end > class_start):
                return False
    
    return True

def find_available_slot(date, hours_needed, existing_sessions):

    for hour in range(9, 21 - int(hours_needed)):
        start_time = f"{date.strftime('%Y-%m-%d')}T{hour:02d}:00:00"
        end_time = f"{date.strftime('%Y-%m-%d')}T{hour + int(hours_needed):02d}:00:00"
        
        if is_time_slot_available(start_time, end_time, existing_sessions):
            return {'start': start_time, 'end': end_time}
    return None

def schedule_study_sessions():

    all_sessions = []
    for task in tasks:
        all_sessions.extend(task.scheduled_times)
        task.scheduled_times = []  # Clear existing schedule
    
    # Sort tasks by priority (highest first) and due date (earliest first)
    sorted_tasks = sorted(tasks, key=lambda x: (-x.priority, x.due_date))
    
    for task in sorted_tasks:
        total_hours = task.time_needed
        due_date = datetime.strptime(task.due_date, '%Y-%m-%d')
        current_date = datetime.now()
        
        # Skip if already past due date
        if due_date < current_date:
            continue
        
        days_until_due = (due_date - current_date).days
        if days_until_due <= 0:
            continue
        
        # Calculate study session length based on priority
        base_hours = min(3, total_hours)  # Max 3 hours per session
        session_hours = base_hours * (task.priority / 3)  # Adjust session length by priority
        
        # Calculate number of sessions needed
        total_sessions = int(total_hours / session_hours)
        if total_hours % session_hours > 0:
            total_sessions += 1  # Add an extra session for remaining time
        
        # Try to distribute sessions evenly
        days_between_sessions = max(1, days_until_due // total_sessions)
        
        # Schedule the sessions
        sessions_scheduled = 0
        current_try_date = current_date
        max_attempts = days_until_due * 2  # Allow for some retry flexibility
        attempt = 0
        
        while sessions_scheduled < total_sessions and attempt < max_attempts:
            # Skip weekends
            while current_try_date.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
                current_try_date += timedelta(days=1)
            

            slot = find_available_slot(current_try_date, session_hours, all_sessions)
            
            if slot:
                task.scheduled_times.append(slot)
                sessions_scheduled += 1
                current_try_date += timedelta(days=days_between_sessions)
            else:
                # If no slot available, try the next day
                current_try_date += timedelta(days=1)
            
            attempt += 1
        

        if sessions_scheduled < total_sessions:
            remaining_hours = total_hours - (sessions_scheduled * session_hours)
            while remaining_hours > 0 and attempt < max_attempts:
                # Try to fit in 1-hour sessions
                while current_try_date.weekday() >= 5:
                    current_try_date += timedelta(days=1)
                
                slot = find_available_slot(current_try_date, 1, all_sessions)
                if slot:
                    task.scheduled_times.append(slot)
                    all_sessions.append(slot)
                    remaining_hours -= 1
                
                current_try_date += timedelta(days=1)
                attempt += 1

@app.route('/api/classes', methods=['GET'])
def get_classes():
    """Get all classes."""
    class_list = []
    for cls in classes:
        # Convert weekday indices to readable format
        weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        days_readable = [weekday_names[day] for day in cls.days]
        
        class_list.append({
            'name': cls.name,
            'days': cls.days,  # Numeric for processing
            'daysReadable': days_readable,  # Human-readable
            'startTime': cls.start_time,
            'endTime': cls.end_time,
            'location': cls.location
        })
    return jsonify(class_list)

@app.route('/api/classes', methods=['POST'])
def add_class():
    """Add a new class."""
    data = request.json
    
    # Convert day strings to weekday indices if needed
    if isinstance(data['days'][0], str):
        weekday_map = {'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6}
        days = [weekday_map[day.lower()] for day in data['days']]
    else:
        days = data['days']
    
    new_class = Class(
        name=data['name'],
        days=days,
        start_time=data['startTime'],
        end_time=data['endTime'],
        location=data.get('location', '')
    )
    classes.append(new_class)
    
    # Recalculate study sessions to account for new class schedule
    schedule_study_sessions()
    
    return jsonify({'status': 'success'})

@app.route('/api/classes/<int:index>', methods=['DELETE'])
def delete_class(index):
    """Delete a class by index."""
    if 0 <= index < len(classes):
        del classes[index]
        # Recalculate study sessions
        schedule_study_sessions()
        return jsonify({'status': 'success'})
    else:
        return jsonify({'status': 'error', 'message': 'Class not found'}), 404

@app.route('/api/preferences', methods=['GET'])
def get_preferences():
    """Get the current preferences."""
    return jsonify(preferences)

@app.route('/api/preferences', methods=['POST'])
def update_preferences():
    """Update the preferences."""
    global preferences
    data = request.json
    
    if 'schedule_preference' in data:
        if data['schedule_preference'] in ['earlier', 'later', 'balanced']:
            preferences['schedule_preference'] = data['schedule_preference']
        else:
            return jsonify({'error': 'Invalid schedule preference value'}), 400
    
    # Reschedule all tasks with the new preference
    schedule_study_sessions()
    
    return jsonify(preferences)

@app.route('/api/start-browser', methods=['POST'])
def start_browser():
    try:
        global blocked_websites
        
        # Get the path to the debug_browser.py script
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'debug_browser.py')
        
        # Start the browser process with the blocked websites as arguments
        cmd = ['python', script_path]
        
        # Always enable auto-reopen with high limits
        cmd.append('--max-reopens=50')  # Allow many reopens to keep browser running
        
        # Add blocked websites as arguments
        cmd.extend(blocked_websites)  # Add each blocked website as a separate argument
        
        print(f"Starting browser with command: {cmd}")
        # Create a log file for browser output
        log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'browser_debug.log')
        print(f"Browser output will be logged to: {log_file_path}")
        
        with open(log_file_path, 'w') as log_file:
            # Write header to log file
            log_file.write(f"Browser launch at {datetime.now().isoformat()}\n")
            log_file.write(f"Command: {' '.join(cmd)}\n\n")
            
            # Start process with output redirected to the log file
            process = subprocess.Popen(
                cmd, 
                stdout=log_file, 
                stderr=log_file,
                start_new_session=True  # This is important to detach the process
            )
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error starting browser: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500
    


@app.route('/api/tasks/<int:task_id>/browser/start', methods=['POST'])
def start_task_browser(task_id):
    """Start a browser session for a specific task with task-specific website blocking"""
    print("\n" + "=" * 50)
    print(f"[DEBUG] /api/tasks/{task_id}/browser/start endpoint called")
    
    # Check if task exists
    if task_id < 0 or task_id >= len(tasks):
        error_message = f"Task with ID {task_id} not found"
        print(f"[DEBUG] {error_message}")
        return jsonify({'status': 'error', 'message': error_message}), 404
    
    # Get the task
    task = tasks[task_id]
    print(f"[DEBUG] Found task: {task.title}")
    
    # Get blocked websites from task, request, or preferences (in that order of priority)
    blocked_websites = []
    try:
        data = request.json or {}
        
        # Priority 1: Request data
        if 'websites' in data and data['websites']:
            blocked_websites = data['websites']
            print(f"[DEBUG] Using blocked websites from request: {blocked_websites}")
        # Priority 2: Task-specific blocked websites
        elif task.blocked_websites:
            blocked_websites = task.blocked_websites
            print(f"[DEBUG] Using blocked websites from task: {blocked_websites}")
        # Priority 3: Global preferences
        else:
            blocked_websites = preferences.get('blocked_websites', [])
            print(f"[DEBUG] Using blocked websites from preferences: {blocked_websites}")
            
        # If still empty, use default websites
        if not blocked_websites:
            blocked_websites = ['facebook.com', 'twitter.com', 'youtube.com']
            print(f"[DEBUG] Using default blocked websites: {blocked_websites}")
    except Exception as e:
        print(f"[DEBUG] Error determining blocked websites: {e}")
        blocked_websites = ['facebook.com', 'twitter.com', 'youtube.com']
        print(f"[DEBUG] Using default blocked websites due to error: {blocked_websites}")
    
    try:
        # Create a thread to run the browser asynchronously
        print("[DEBUG] Creating browser thread for task")
        browser_thread = threading.Thread(target=run_browser_async, args=(blocked_websites,))
        browser_thread.daemon = True
        
        # Start the thread
        print("[DEBUG] Starting browser thread")
        browser_thread.start()
        print(f"[DEBUG] Browser thread started successfully: {browser_thread.name}")
        
        # Record this browser session in the task
        session_info = {
            'start_time': datetime.now().isoformat(),
            'blocked_websites': blocked_websites,
            'thread_name': browser_thread.name
        }
        task.browser_sessions.append(session_info)
        print(f"[DEBUG] Added browser session to task: {session_info}")
        
        # Return success response
        response_data = {
            'status': 'success', 
            'message': f'Browser started for task: {task.title}',
            'task_id': task_id,
            'task_title': task.title,
            'blocked_websites': blocked_websites,
            'thread_name': browser_thread.name,
            'session_id': len(task.browser_sessions) - 1
        }
        print(f"[DEBUG] Returning success response: {response_data}")
        return jsonify(response_data)
    except Exception as e:
        print(f"[DEBUG] Failed to start browser for task: {e}")
        print(f"[DEBUG] Exception traceback: {traceback.format_exc()}")
        error_response = {'status': 'error', 'message': f"Failed to start browser for task: {e}"}
        return jsonify(error_response), 500

@app.route('/api/blocked-websites', methods=['GET'])
def get_blocked_websites():
    global blocked_websites
    return jsonify(blocked_websites)

@app.route('/api/tasks/<int:task_id>', methods=['GET', 'PUT'])
def task_endpoint(task_id):
    # Check if task exists
    if task_id < 0 or task_id >= len(tasks):
        return jsonify({'status': 'error', 'message': f"Task with ID {task_id} not found"}), 404
    
    # Get the task
    task = tasks[task_id]
    
    if request.method == 'GET':
        return get_task(task_id, task)
    elif request.method == 'PUT':
        return update_task(task_id, task)

def get_task(task_id, task):
    """Get a specific task"""
    return jsonify({
        'status': 'success',
        'taskId': task_id,
        'task': {
            'title': task.title,
            'dueDate': task.due_date,
            'timeNeeded': task.time_needed,
            'priority': task.priority,
            'description': task.description,
            'blockedWebsites': task.blocked_websites
        }
    })

def update_task(task_id, task):
    """Update a task's properties"""
    
    # Get data from request
    data = request.json
    if not data:
        return jsonify({'status': 'error', 'message': 'No data provided'}), 400
    
    # Update task properties
    task.update(
        title=data.get('title'),
        due_date=data.get('dueDate'),
        time_needed=data.get('timeNeeded'),
        priority=data.get('priority'),
        description=data.get('description'),
        blocked_websites=data.get('blockedWebsites')
    )
    
    # Reschedule study sessions if needed
    if 'timeNeeded' in data or 'priority' in data or 'dueDate' in data:
        schedule_study_sessions()
    
    # Return updated task
    return jsonify({
        'status': 'success',
        'message': f'Task "{task.title}" updated successfully',
        'taskId': task_id,
        'task': {
            'title': task.title,
            'dueDate': task.due_date,
            'timeNeeded': task.time_needed,
            'priority': task.priority,
            'description': task.description,
            'blockedWebsites': task.blocked_websites
        }
    })

@app.route('/api/tasks/<int:task_id>/browser/sessions', methods=['GET'])
def get_task_browser_sessions(task_id):
    """Get browser session history for a specific task"""
    # Check if task exists
    if task_id < 0 or task_id >= len(tasks):
        return jsonify({'status': 'error', 'message': f"Task with ID {task_id} not found"}), 404
    
    # Get the task
    task = tasks[task_id]
    
    # Return the browser sessions
    return jsonify({
        'status': 'success',
        'task_id': task_id,
        'task_title': task.title,
        'browser_sessions': task.browser_sessions
    })

@app.route('/api/blocked-websites', methods=['POST'])
def update_blocked_websites():
    global blocked_websites
    data = request.json
    if 'website' in data:
        # Add a single website
        website = data['website']
        if website not in blocked_websites:
            blocked_websites.append(website)
        return jsonify({'status': 'success', 'websites': blocked_websites})
    elif 'websites' in data:
        # Replace the entire list
        blocked_websites = data['websites']
        return jsonify({'status': 'success', 'websites': blocked_websites})
    return jsonify({'status': 'error', 'message': 'No website provided'}), 400

@app.route('/api/blocked-websites/<int:index>', methods=['DELETE'])
def delete_blocked_website(index):
    global blocked_websites
    if 0 <= index < len(blocked_websites):
        removed = blocked_websites.pop(index)
        return jsonify({'status': 'success', 'removed': removed, 'websites': blocked_websites})
    return jsonify({'status': 'error', 'message': 'Invalid index'}), 400

def run_browser_async(blocked_websites):
    """Run the browser with website blocking in an async context"""
    import threading
    import os
    
    print("\n" + "*" * 50)
    print(f"[DEBUG] run_browser_async called with blocked_websites: {blocked_websites}")
    print(f"[DEBUG] Current thread: {threading.current_thread().name}")
    print(f"[DEBUG] Current working directory: {os.getcwd()}")
    
    try:
        # Make sure blocked_websites is a list of strings
        if not isinstance(blocked_websites, list):
            print(f"[DEBUG] blocked_websites is not a list, converting from {type(blocked_websites)}")
            blocked_websites = []
        
        # Convert any non-string items to strings
        print(f"[DEBUG] Converting blocked_websites items to strings: {blocked_websites}")
        blocked_websites = [str(site) for site in blocked_websites]
        print(f"[DEBUG] Converted blocked_websites: {blocked_websites}")
        
        # Try to use the standalone script first
        print("[DEBUG] Attempting to use standalone script method")
        try:
            import subprocess
            import sys
            import os
            
            # Get the absolute path to the script
            script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'debug_browser.py')
            print(f"[DEBUG] Script path: {script_path}")
            print(f"[DEBUG] Script exists: {os.path.exists(script_path)}")
            print(f"[DEBUG] Python executable: {sys.executable}")
            
            # Construct the command to run the standalone script
            cmd = [sys.executable, script_path] + blocked_websites
            print(f"[DEBUG] Running command: {' '.join(cmd)}")
            
            # Run the script as a subprocess, detached from the parent process
            print("[DEBUG] Creating subprocess")
            if os.name == 'nt':  # Windows
                print("[DEBUG] Using Windows-specific subprocess creation")
                process = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
            else:  # Unix/Linux/Mac
                print("[DEBUG] Using Unix-specific subprocess creation")
                process = subprocess.Popen(
                    cmd, 
                    start_new_session=True,
                    stdout=None,
                    stderr=None
                )
                
            print(f"[DEBUG] Started browser process with PID: {process.pid}")
            
            # Check if process is running
            if process.poll() is None:
                print("[DEBUG] Process is still running (good)")
            else:
                print(f"[DEBUG] Process exited immediately with code: {process.returncode}")
                stdout, stderr = process.communicate()
                print(f"[DEBUG] Process stdout: {stdout}")
                print(f"[DEBUG] Process stderr: {stderr}")
                raise Exception(f"Process exited immediately with code {process.returncode}")
                
            print("[DEBUG] Standalone script method successful")
            return
        except Exception as script_error:
            print(f"[DEBUG] Error running standalone script: {script_error}")
            print(f"[DEBUG] Script error traceback: {traceback.format_exc()}")
        
        # Fallback to using the async method directly
        print("[DEBUG] Falling back to direct async method")
        import threading
        
        def run_async():
            print("[DEBUG] Inside run_async thread function")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                print("[DEBUG] Running start_browser_async in the event loop")
                loop.run_until_complete(start_browser_async(blocked_websites))
                print("[DEBUG] start_browser_async completed")
            except Exception as async_error:
                print(f"[DEBUG] Error in async browser: {async_error}")
                print(f"[DEBUG] Async error traceback: {traceback.format_exc()}")
            finally:
                print("[DEBUG] Closing event loop")
                loop.close()
        
        # Run in a separate thread
        print("[DEBUG] Creating thread for async method")
        thread = threading.Thread(target=run_async, name="BrowserThread")
        thread.daemon = True
        print("[DEBUG] Starting thread")
        thread.start()
        print(f"[DEBUG] Started browser thread: {thread.name}, is_alive: {thread.is_alive()}")
    except Exception as e:
        print(f"[DEBUG] Error in browser session: {e}")
        print(f"[DEBUG] Error traceback: {traceback.format_exc()}")

async def start_browser_async(blocked_websites):
    """Start a browser with website blocking using Playwright"""
    print("\n" + "#" * 50)
    print(f"[DEBUG] start_browser_async called with blocked_websites: {blocked_websites}")
    
    try:
        print("[DEBUG] Initializing Playwright...")
        async with async_playwright() as p:
            print("[DEBUG] Launching Chromium browser...")
            browser = await p.chromium.launch(headless=False)
            print(f"[DEBUG] Browser launched successfully, connected: {browser.is_connected()}")
            
            print("[DEBUG] Creating browser context")
            context = await browser.new_context()
            
            print("[DEBUG] Creating new page")
            page = await context.new_page()
            
            # Set up route handler to block specified websites
            async def route_handler(route):
                url = route.request.url
                blocked = False
                
                for blocked_site in blocked_websites:
                    if blocked_site in url:
                        print(f"[DEBUG] Blocking access to: {url} (matched {blocked_site})")
                        blocked = True
                        break
                
                if blocked:
                    # Redirect to a blocked page or just abort
                    print(f"[DEBUG] Aborting request to blocked site: {url}")
                    await route.abort()
                else:
                    # Allow the request to continue
                    await route.continue_()
            
            # Set up website blocking if there are sites to block
            if blocked_websites:
                print(f"[DEBUG] Setting up route handler for blocking {len(blocked_websites)} websites...")
                await context.route('**/*', route_handler)
                print("[DEBUG] Website blocking routes established")
            else:
                print("[DEBUG] No websites to block, skipping route handler setup")
            
            # Navigate to a start page
            print("[DEBUG] Navigating to Google...")
            try:
                await page.goto('https://www.google.com')
                print("[DEBUG] Successfully navigated to Google")
            except Exception as nav_error:
                print(f"[DEBUG] Navigation error: {nav_error}")
                print(f"[DEBUG] Navigation error traceback: {traceback.format_exc()}")
            
            print("[DEBUG] Browser is now open and ready for use")
            
            # Keep the browser open until closed
            try:
                print("[DEBUG] Waiting for browser disconnection event")
                await browser.wait_for_event('disconnected')
                print("[DEBUG] Browser was closed by user")
            except Exception as wait_error:
                print(f"[DEBUG] Error while waiting for browser to close: {wait_error}")
                print(f"[DEBUG] Wait error traceback: {traceback.format_exc()}")
    except Exception as e:
        print(f"[DEBUG] Error in browser session: {e}")
        print(f"[DEBUG] Error traceback: {traceback.format_exc()}")

if __name__ == '__main__':
    app.run(debug=True)