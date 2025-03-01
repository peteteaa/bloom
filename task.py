from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
import json

app = Flask(__name__, static_url_path='/static')

# Store tasks, classes, and assignments in memory
tasks = []
classes = []

class Task:
    def __init__(self, title, due_date, time_needed, priority, description=None):
        self.title = title
        self.due_date = due_date
        self.time_needed = float(time_needed)  # hours needed
        self.priority = int(priority)  # 1-5, 5 being highest
        self.description = description
        self.scheduled_times = []  # List of scheduled study sessions

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
    for task in tasks:
        # Add due date (red)
        events.append({
            'title': f'Due: {task.title}',
            'start': task.due_date + 'T23:59:00',
            'backgroundColor': '#dc3545',
            'borderColor': '#dc3545',
            'allDay': True
        })
        
        # Add study sessions (blue)
        for session in task.scheduled_times:
            events.append({
                'title': f'Study: {task.title}',
                'start': session['start'],
                'end': session['end'],
                'backgroundColor': '#007bff',
                'borderColor': '#007bff'
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
        description=data.get('description', '')
    )
    tasks.append(task)
    schedule_study_sessions()  # Recalculate all study sessions
    return jsonify({'status': 'success'})

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

if __name__ == '__main__':
    app.run(debug=True)