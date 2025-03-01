from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
import json

app = Flask(__name__, static_url_path='/static')

# Store tasks and assignments in memory
tasks = []

class Task:
    def __init__(self, title, due_date, time_needed, priority, description=None):
        self.title = title
        self.due_date = due_date
        self.time_needed = float(time_needed)  # hours needed
        self.priority = int(priority)  # 1-5, 5 being highest
        self.description = description
        self.scheduled_times = []  # List of scheduled study sessions

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
    """Check if a time slot is available."""
    start = datetime.strptime(start_time, '%Y-%m-%dT%H:%M:%S')
    end = datetime.strptime(end_time, '%Y-%m-%dT%H:%M:%S')
    
    for session in existing_sessions:
        session_start = datetime.strptime(session['start'], '%Y-%m-%dT%H:%M:%S')
        session_end = datetime.strptime(session['end'], '%Y-%m-%dT%H:%M:%S')
        
        # Check for overlap
        if (start < session_end and end > session_start):
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

if __name__ == '__main__':
    app.run(debug=True)