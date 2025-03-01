// Task and Class management class
class TaskManager {
    constructor() {
        this.taskForm = document.getElementById('taskForm');
        this.classForm = document.getElementById('classForm');
        this.classList = document.getElementById('classList');
        this.calendar = this.initializeCalendar();
        this.loadClasses();
        this.bindEvents();
    }

    initializeCalendar() {
        return $('#calendar').fullCalendar({
            header: {
                left: 'prev,next today',
                center: 'title',
                right: 'month,agendaWeek,agendaDay'
            },
            defaultView: 'agendaWeek',
            navLinks: true,
            editable: false,
            eventLimit: true,
            events: '/api/tasks',
            minTime: '08:00:00',
            maxTime: '20:00:00',
            eventRender: (event, element) => {
                // Add tooltips to events
                if (event.title.startsWith('Study:')) {
                    element.attr('title', 'Study session for ' + event.title.substring(7));
                } else if (event.title.startsWith('Due:')) {
                    element.attr('title', 'Assignment due: ' + event.title.substring(5));
                }
            }
        });
    }

    bindEvents() {
        this.taskForm.addEventListener('submit', (e) => this.handleTaskSubmit(e));
        this.classForm.addEventListener('submit', (e) => this.handleClassSubmit(e));
    }

    async handleTaskSubmit(e) {
        e.preventDefault();

        const formData = {
            title: document.getElementById('title').value,
            dueDate: document.getElementById('dueDate').value,
            timeNeeded: document.getElementById('timeNeeded').value,
            priority: document.getElementById('priority').value,
            description: document.getElementById('description').value
        };

        try {
            const response = await fetch('/api/tasks', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(formData)
            });

            if (!response.ok) {
                throw new Error('Failed to add task');
            }

            // Refresh calendar and reset form
            $('#calendar').fullCalendar('refetchEvents');
            this.taskForm.reset();
            
            // Show success message
            this.showNotification('Task added successfully!', 'success');
        } catch (error) {
            console.error('Error adding task:', error);
            this.showNotification('Failed to add task. Please try again.', 'error');
        }
    }
    
    async handleClassSubmit(e) {
        e.preventDefault();
        
        // Get selected days
        const selectedDays = [];
        document.querySelectorAll('input[name="classDays"]:checked').forEach(checkbox => {
            selectedDays.push(parseInt(checkbox.value));
        });
        
        if (selectedDays.length === 0) {
            this.showNotification('Please select at least one day for the class.', 'error');
            return;
        }
        
        const formData = {
            name: document.getElementById('className').value,
            days: selectedDays,
            startTime: document.getElementById('classStartTime').value,
            endTime: document.getElementById('classEndTime').value,
            location: document.getElementById('classLocation').value
        };
        
        try {
            const response = await fetch('/api/classes', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(formData)
            });

            if (!response.ok) {
                throw new Error('Failed to add class');
            }

            // Refresh calendar and class list
            $('#calendar').fullCalendar('refetchEvents');
            this.loadClasses();
            this.classForm.reset();
            
            // Show success message
            this.showNotification('Class added successfully!', 'success');
        } catch (error) {
            console.error('Error adding class:', error);
            this.showNotification('Failed to add class. Please try again.', 'error');
        }
    }

    showNotification(message, type) {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        // Remove notification after 3 seconds
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }
    
    async loadClasses() {
        try {
            const response = await fetch('/api/classes');
            if (!response.ok) {
                throw new Error('Failed to load classes');
            }
            
            const classes = await response.json();
            this.renderClassList(classes);
        } catch (error) {
            console.error('Error loading classes:', error);
            this.showNotification('Failed to load classes.', 'error');
        }
    }
    
    renderClassList(classes) {
        // Clear current list
        this.classList.innerHTML = '';
        
        if (classes.length === 0) {
            const emptyMessage = document.createElement('p');
            emptyMessage.className = 'empty-message';
            emptyMessage.textContent = 'No classes added yet.';
            this.classList.appendChild(emptyMessage);
            return;
        }
        
        // Add each class to the list
        classes.forEach((cls, index) => {
            const classItem = document.createElement('div');
            classItem.className = 'class-item';
            
            const title = document.createElement('h3');
            title.textContent = cls.name;
            
            const days = document.createElement('p');
            days.textContent = `Days: ${cls.daysReadable.join(', ')}`;
            
            const time = document.createElement('p');
            time.textContent = `Time: ${cls.startTime} - ${cls.endTime}`;
            
            const location = document.createElement('p');
            location.textContent = cls.location ? `Location: ${cls.location}` : '';
            
            const deleteButton = document.createElement('button');
            deleteButton.className = 'delete-class';
            deleteButton.textContent = '×';
            deleteButton.setAttribute('data-index', index);
            deleteButton.addEventListener('click', () => this.deleteClass(index));
            
            classItem.appendChild(title);
            classItem.appendChild(days);
            classItem.appendChild(time);
            if (cls.location) classItem.appendChild(location);
            classItem.appendChild(deleteButton);
            
            this.classList.appendChild(classItem);
        });
    }
    
    async deleteClass(index) {
        try {
            const response = await fetch(`/api/classes/${index}`, {
                method: 'DELETE'
            });
            
            if (!response.ok) {
                throw new Error('Failed to delete class');
            }
            
            // Refresh calendar and class list
            $('#calendar').fullCalendar('refetchEvents');
            this.loadClasses();
            
            // Show success message
            this.showNotification('Class deleted successfully!', 'success');
        } catch (error) {
            console.error('Error deleting class:', error);
            this.showNotification('Failed to delete class. Please try again.', 'error');
        }
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new TaskManager();
});
