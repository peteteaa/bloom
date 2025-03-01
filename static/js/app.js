// Task management class
class TaskManager {
    constructor() {
        this.form = document.getElementById('taskForm');
        this.calendar = this.initializeCalendar();
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
        this.form.addEventListener('submit', (e) => this.handleSubmit(e));
    }

    async handleSubmit(e) {
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
            this.form.reset();
            
            // Show success message
            this.showNotification('Task added successfully!', 'success');
        } catch (error) {
            console.error('Error adding task:', error);
            this.showNotification('Failed to add task. Please try again.', 'error');
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
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new TaskManager();
});
