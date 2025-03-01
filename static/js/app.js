// Task management class
class TaskManager {
    constructor() {
        this.form = document.getElementById('taskForm');
        this.classForm = document.getElementById('classForm');
        this.classList = document.getElementById('classList');
        this.earlierBtn = document.getElementById('earlierBtn');
        this.balancedBtn = document.getElementById('balancedBtn');
        this.laterBtn = document.getElementById('laterBtn');
        this.calendar = this.initializeCalendar();
        this.loadClasses();
        this.loadPreferences();
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
        this.classForm.addEventListener('submit', (e) => this.handleClassSubmit(e));
        
        // Preference buttons
        this.earlierBtn.addEventListener('click', () => this.updatePreference('earlier'));
        this.balancedBtn.addEventListener('click', () => this.updatePreference('balanced'));
        this.laterBtn.addEventListener('click', () => this.updatePreference('later'));
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

// Website Blocker class
class WebsiteBlocker {
    constructor() {
        this.form = document.getElementById('websiteBlockerForm');
        this.websiteInput = document.getElementById('websiteUrl');
        this.websitesList = document.getElementById('blockedWebsitesList');
        this.openBrowserBtn = document.getElementById('openBrowserBtn');
        
        // Rename the button to be clearer
        this.openBrowserBtn.textContent = 'Open & Auto-Close Browser';
        
        // Add a flag to track if auto-reopen is active
        this.autoReopenActive = false;
        
        this.bindEvents();
        this.loadBlockedWebsites();
    }
    
    bindEvents() {
        this.form.addEventListener('submit', (e) => this.handleSubmit(e));
        this.openBrowserBtn.addEventListener('click', () => this.toggleContinuousReopening());
    }
    
    async loadBlockedWebsites() {
        try {
            const response = await fetch('/api/blocked-websites');
            if (!response.ok) {
                throw new Error('Failed to load blocked websites');
            }
            
            const websites = await response.json();
            this.renderWebsitesList(websites);
        } catch (error) {
            console.error('Error loading blocked websites:', error);
            this.showNotification('Failed to load blocked websites', 'error');
        }
    }
    
    async handleSubmit(e) {
        e.preventDefault();
        
        const website = this.websiteInput.value.trim();
        if (!website) return;
        
        try {
            const response = await fetch('/api/blocked-websites', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ website })
            });
            
            if (!response.ok) {
                throw new Error('Failed to block website');
            }
            
            const result = await response.json();
            this.websiteInput.value = '';
            this.loadBlockedWebsites();
            this.showNotification(`${website} has been blocked`, 'success');
        } catch (error) {
            console.error('Error blocking website:', error);
            this.showNotification('Failed to block website', 'error');
        }
    }
    
    async removeWebsite(index) {
        try {
            const response = await fetch(`/api/blocked-websites/${index}`, {
                method: 'DELETE'
            });
            
            if (!response.ok) {
                throw new Error('Failed to remove website');
            }
            
            const result = await response.json();
            this.loadBlockedWebsites();
            this.showNotification(`Website has been unblocked`, 'success');
        } catch (error) {
            console.error('Error removing website:', error);
            this.showNotification('Failed to remove website', 'error');
        }
    }
    
    toggleContinuousReopening() {
        if (this.autoReopenActive) {
            // Stop auto-reopen
            this.stopAutoReopen();
        } else {
            // Start browser with auto-reopen on close
            this.startBrowserWithAutoReopen();
        }
    }
    
    startBrowserWithAutoReopen() {
        if (this.autoReopenActive) return;
        
        this.autoReopenActive = true;
        this.openBrowserBtn.textContent = 'Stop Auto-Reopening';
        this.openBrowserBtn.classList.add('active');
        
        // Open browser immediately with auto-reopen enabled
        this.openAndCloseBrowser();
        
        this.showNotification('Auto-reopening activated - Browser will reopen when closed', 'success');
    }
    
    stopAutoReopen() {
        if (!this.autoReopenActive) return;
        
        this.autoReopenActive = false;
        this.openBrowserBtn.textContent = 'Open & Auto-Close Browser';
        this.openBrowserBtn.classList.remove('active');
        
        this.showNotification('Auto-reopening deactivated', 'success');
    }
    
    async openAndCloseBrowser() {
        try {
            this.showNotification('Starting study browser...', 'success');
            
            // Prepare the API request
            let url = '/api/start-browser';
            let method = 'POST';
            let body = {};
            
            // If auto-reopen is active, pass that to the server
            if (this.autoReopenActive) {
                // We'll keep the existing auto-reopen functionality in the Python script
                // No need to modify the request
            }
            
            // Call the API to start the browser with blocked websites
            const response = await fetch(url, {
                method: method,
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(body)
            });
            
            if (!response.ok) {
                throw new Error('Failed to start browser');
            }
            
            const result = await response.json();
            if (result.success) {
                this.showNotification('Browser started successfully', 'success');
            } else {
                throw new Error(result.message || 'Failed to start browser');
            }
            
        } catch (error) {
            console.error('Error opening browser:', error);
            this.showNotification('Failed to start browser: ' + error.message, 'error');
            
            // If we encounter an error during auto-reopening, stop it
            if (this.autoReopenActive) {
                this.stopAutoReopen();
            }
        }
    }
    
    renderWebsitesList(websites) {
        this.websitesList.innerHTML = '';
        
        if (websites.length === 0) {
            const emptyMessage = document.createElement('li');
            emptyMessage.textContent = 'No websites blocked yet';
            emptyMessage.style.fontStyle = 'italic';
            emptyMessage.style.color = '#666';
            this.websitesList.appendChild(emptyMessage);
            return;
        }
        
        websites.forEach((website, index) => {
            const item = document.createElement('li');
            item.className = 'blocked-website-item';
            
            const urlSpan = document.createElement('span');
            urlSpan.className = 'blocked-website-url';
            urlSpan.textContent = website;
            
            const removeBtn = document.createElement('button');
            removeBtn.className = 'remove-website-btn';
            removeBtn.textContent = 'Remove';
            removeBtn.addEventListener('click', () => this.removeWebsite(index));
            
            item.appendChild(urlSpan);
            item.appendChild(removeBtn);
            
            this.websitesList.appendChild(item);
        });
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

// Class management class
class ClassManager {
    constructor() {
        this.form = document.getElementById('classForm');
        this.classList = document.getElementById('classList');
        this.bindEvents();
        this.loadClasses();
    }
    
    bindEvents() {
        this.form.addEventListener('submit', (e) => this.handleSubmit(e));
    }
    
    async loadClasses() {
        try {
            const response = await fetch('/api/classes');
            if (!response.ok) {
                throw new Error('Failed to load classes');
            }
            
            const classes = await response.json();
            this.renderClassesList(classes);
        } catch (error) {
            console.error('Error loading classes:', error);
            this.showNotification('Failed to load classes', 'error');
        }
    }
    
    async handleSubmit(e) {
        e.preventDefault();
        
        // Get selected days
        const selectedDays = [];
        document.querySelectorAll('input[name="days"]:checked').forEach(checkbox => {
            selectedDays.push(parseInt(checkbox.value));
        });
        
        if (selectedDays.length === 0) {
            this.showNotification('Please select at least one day', 'error');
            return;
        }
        
        const formData = {
            name: document.getElementById('className').value,
            days: selectedDays,
            startTime: document.getElementById('startTime').value,
            endTime: document.getElementById('endTime').value,
            location: document.getElementById('location').value
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
            
            // Refresh calendar and classes list
            $('#calendar').fullCalendar('refetchEvents');
            this.form.reset();
            this.loadClasses();
            
            this.showNotification('Class added successfully!', 'success');
        } catch (error) {
            console.error('Error adding class:', error);
            this.showNotification('Failed to add class. Please try again.', 'error');
        }
    }
    
    async removeClass(index) {
        try {
            const response = await fetch(`/api/classes/${index}`, {
                method: 'DELETE'
            });
            
            if (!response.ok) {
                throw new Error('Failed to remove class');
            }
            
            // Refresh calendar and classes list
            $('#calendar').fullCalendar('refetchEvents');
            this.loadClasses();
            
            this.showNotification('Class removed successfully', 'success');
        } catch (error) {
            console.error('Error removing class:', error);
            this.showNotification('Failed to remove class', 'error');
        }
    }
    
    renderClassesList(classes) {
        this.classList.innerHTML = '';
        
        if (classes.length === 0) {
            const emptyMessage = document.createElement('li');
            emptyMessage.textContent = 'No classes added yet';
            emptyMessage.style.fontStyle = 'italic';
            emptyMessage.style.color = '#666';
            this.classList.appendChild(emptyMessage);
            return;
        }
        
        const weekdayNames = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
        
        classes.forEach((cls, index) => {
            const item = document.createElement('li');
            item.className = 'class-item';
            
            const detailsDiv = document.createElement('div');
            detailsDiv.className = 'class-details';
            
            const nameDiv = document.createElement('div');
            nameDiv.className = 'class-name';
            nameDiv.textContent = cls.name;
            
            const scheduleDiv = document.createElement('div');
            scheduleDiv.className = 'class-schedule';
            
            // Format days
            const dayNames = cls.days.map(day => weekdayNames[day]).join(', ');
            scheduleDiv.textContent = `${dayNames} from ${cls.start_time} to ${cls.end_time}`;
            
            const locationDiv = document.createElement('div');
            locationDiv.className = 'class-location';
            if (cls.location) {
                locationDiv.textContent = `Location: ${cls.location}`;
            }
            
            detailsDiv.appendChild(nameDiv);
            detailsDiv.appendChild(scheduleDiv);
            if (cls.location) {
                detailsDiv.appendChild(locationDiv);
            }
            
            const removeBtn = document.createElement('button');
            removeBtn.className = 'remove-class-btn';
            removeBtn.textContent = '×';
            removeBtn.addEventListener('click', () => this.removeClass(index));
            
            item.appendChild(detailsDiv);
            item.appendChild(removeBtn);
            
            this.classList.appendChild(item);
        });
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

// Add these methods to the TaskManager class
Object.assign(TaskManager.prototype, {
    async loadClasses() {
        try {
            const response = await fetch('/api/classes');
            if (response.ok) {
                const classes = await response.json();
                // Update the UI if needed
            }
        } catch (error) {
            console.error('Error loading classes:', error);
        }
    },
    
    async handleClassSubmit(e) {
        e.preventDefault();
        
        // Get selected days
        const selectedDays = [];
        document.querySelectorAll('input[name="days"]:checked').forEach(checkbox => {
            selectedDays.push(parseInt(checkbox.value));
        });
        
        if (selectedDays.length === 0) {
            this.showNotification('Please select at least one day', 'error');
            return;
        }
        
        const formData = {
            name: document.getElementById('className').value,
            days: selectedDays,
            startTime: document.getElementById('startTime').value,
            endTime: document.getElementById('endTime').value,
            location: document.getElementById('location').value
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
            
            // Refresh calendar and reset form
            $('#calendar').fullCalendar('refetchEvents');
            this.classForm.reset();
            this.loadClasses();
            
            this.showNotification('Class added successfully!', 'success');
        } catch (error) {
            console.error('Error adding class:', error);
            this.showNotification('Failed to add class. Please try again.', 'error');
        }
    },
    
    async loadPreferences() {
        try {
            const response = await fetch('/api/preferences');
            if (response.ok) {
                const prefs = await response.json();
                
                // Update UI based on preferences
                this.earlierBtn.classList.remove('active');
                this.balancedBtn.classList.remove('active');
                this.laterBtn.classList.remove('active');
                
                if (prefs.schedule_preference === 'earlier') {
                    this.earlierBtn.classList.add('active');
                } else if (prefs.schedule_preference === 'later') {
                    this.laterBtn.classList.add('active');
                } else {
                    this.balancedBtn.classList.add('active');
                }
            }
        } catch (error) {
            console.error('Error loading preferences:', error);
        }
    },
    
    async updatePreference(preference) {
        try {
            const response = await fetch('/api/preferences', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ schedule_preference: preference })
            });
            
            if (!response.ok) {
                throw new Error('Failed to update preferences');
            }
            
            // Update UI
            this.earlierBtn.classList.remove('active');
            this.balancedBtn.classList.remove('active');
            this.laterBtn.classList.remove('active');
            
            if (preference === 'earlier') {
                this.earlierBtn.classList.add('active');
            } else if (preference === 'later') {
                this.laterBtn.classList.add('active');
            } else {
                this.balancedBtn.classList.add('active');
            }
            
            // Refresh calendar to show updated schedule
            $('#calendar').fullCalendar('refetchEvents');
            
            this.showNotification('Preferences updated successfully!', 'success');
        } catch (error) {
            console.error('Error updating preferences:', error);
            this.showNotification('Failed to update preferences. Please try again.', 'error');
        }
    }
});

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new TaskManager();
    new WebsiteBlocker();
});
