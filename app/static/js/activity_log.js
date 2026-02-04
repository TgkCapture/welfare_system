// app/static/js/activity_log.js
document.addEventListener('DOMContentLoaded', function() {
    initializeActivityLog();
    
    function initializeActivityLog() {
        setupFilters();
        setupModals();
        setupTimelineInteractions();
        calculateInsights();
        setupKeyboardShortcuts();
    }
    
    // Filter functionality
    function setupFilters() {
        const activityTypeFilter = document.getElementById('activityType');
        const dateRangeFilter = document.getElementById('dateRange');
        const searchFilter = document.getElementById('searchActivity');
        const clearFiltersBtn = document.getElementById('clearFiltersBtn');
        const activityItems = document.querySelectorAll('.timeline-item');
        
        function filterActivities() {
            const typeValue = activityTypeFilter.value;
            const dateValue = dateRangeFilter.value;
            const searchValue = searchFilter.value.toLowerCase();
            
            let visibleCount = 0;
            
            activityItems.forEach(item => {
                const itemType = item.dataset.type || '';
                const itemDate = new Date(item.dataset.date);
                const itemText = item.textContent.toLowerCase();
                
                let typeMatch = !typeValue || itemType === typeValue;
                let dateMatch = checkDateRange(itemDate, dateValue);
                let searchMatch = !searchValue || itemText.includes(searchValue);
                
                const isVisible = typeMatch && dateMatch && searchMatch;
                item.style.display = isVisible ? 'flex' : 'none';
                
                if (isVisible) {
                    visibleCount++;
                    item.style.opacity = '1';
                } else {
                    item.style.opacity = '0.3';
                }
            });
            
            // Update visible count
            document.getElementById('visibleActivitiesCount').textContent = visibleCount;
            
            // Show/hide empty state
            const emptyState = document.querySelector('.empty-state');
            const timeline = document.getElementById('activityTimeline');
            
            if (emptyState && timeline) {
                if (visibleCount === 0 && activityItems.length > 0) {
                    timeline.style.display = 'none';
                    emptyState.style.display = 'block';
                } else if (visibleCount > 0) {
                    timeline.style.display = 'block';
                    emptyState.style.display = 'none';
                }
            }
        }
        
        function checkDateRange(date, range) {
            if (!range) return true;
            
            const now = new Date();
            const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate());
            
            switch(range) {
                case 'today':
                    return date >= startOfDay;
                case 'week':
                    const weekAgo = new Date(startOfDay);
                    weekAgo.setDate(weekAgo.getDate() - 7);
                    return date >= weekAgo;
                case 'month':
                    const monthAgo = new Date(startOfDay);
                    monthAgo.setMonth(monthAgo.getMonth() - 1);
                    return date >= monthAgo;
                case 'quarter':
                    const quarterAgo = new Date(startOfDay);
                    quarterAgo.setMonth(quarterAgo.getMonth() - 3);
                    return date >= quarterAgo;
                case 'year':
                    const yearAgo = new Date(startOfDay);
                    yearAgo.setFullYear(yearAgo.getFullYear() - 1);
                    return date >= yearAgo;
                default:
                    return true;
            }
        }
        
        // Add event listeners
        [activityTypeFilter, dateRangeFilter].forEach(filter => {
            filter.addEventListener('change', filterActivities);
        });
        
        searchFilter.addEventListener('input', debounce(filterActivities, 300));
        
        clearFiltersBtn.addEventListener('click', function() {
            activityTypeFilter.value = '';
            dateRangeFilter.value = '';
            searchFilter.value = '';
            filterActivities();
        });
        
        // Initial filter
        filterActivities();
    }
    
    // Modal functionality
    function setupModals() {
        // Clear Activity Modal
        const clearActivityBtn = document.getElementById('clearActivityBtn');
        const clearActivityModal = document.getElementById('clearActivityModal');
        
        if (clearActivityBtn && clearActivityModal) {
            clearActivityBtn.addEventListener('click', () => openModal(clearActivityModal));
            
            const closeModal = clearActivityModal.querySelector('.close-modal');
            const cancelClear = clearActivityModal.querySelector('.cancel-clear');
            const confirmClearBtn = clearActivityModal.querySelector('#confirmClearBtn');
            
            closeModal.addEventListener('click', () => closeModalFunc(clearActivityModal));
            cancelClear.addEventListener('click', () => closeModalFunc(clearActivityModal));
            
            confirmClearBtn.addEventListener('click', function() {
                const exportBeforeClear = document.getElementById('exportBeforeClear').checked;
                const keepRecent = document.getElementById('keepRecentActivities').checked;
                
                // This would typically make an API call
                if (exportBeforeClear) {
                    exportActivityLog('all', 'json');
                }
                
                showNotification(
                    `Activity log cleared ${keepRecent ? '(keeping last 7 days)' : '(all activities)'}`,
                    'success'
                );
                closeModalFunc(clearActivityModal);
                
                // Simulate clearing
                setTimeout(() => {
                    const activityItems = document.querySelectorAll('.timeline-item');
                    if (keepRecent) {
                        // Keep only recent items (last 7 days)
                        const weekAgo = new Date();
                        weekAgo.setDate(weekAgo.getDate() - 7);
                        
                        activityItems.forEach(item => {
                            const itemDate = new Date(item.dataset.date);
                            if (itemDate < weekAgo) {
                                item.remove();
                            }
                        });
                    } else {
                        // Remove all
                        activityItems.forEach(item => item.remove());
                    }
                    
                    // Update counts
                    updateActivityCounts();
                }, 1000);
            });
        }
        
        // Export Options Modal
        const exportActivityBtn = document.getElementById('exportActivityBtn');
        const exportOptionsModal = document.getElementById('exportOptionsModal');
        const exportDateRange = document.getElementById('exportDateRange');
        const customDateRange = document.getElementById('customDateRange');
        
        if (exportActivityBtn && exportOptionsModal) {
            exportActivityBtn.addEventListener('click', () => openModal(exportOptionsModal));
            
            const closeModal = exportOptionsModal.querySelector('.close-modal');
            const cancelExport = exportOptionsModal.querySelector('.cancel-export');
            const startExportBtn = exportOptionsModal.querySelector('#startExportBtn');
            
            closeModal.addEventListener('click', () => closeModalFunc(exportOptionsModal));
            cancelExport.addEventListener('click', () => closeModalFunc(exportOptionsModal));
            
            // Toggle custom date range
            exportDateRange.addEventListener('change', function() {
                customDateRange.style.display = this.value === 'custom' ? 'block' : 'none';
            });
            
            startExportBtn.addEventListener('click', function() {
                const format = document.getElementById('exportFormat').value;
                const range = exportDateRange.value;
                const selectedTypes = Array.from(document.querySelectorAll('input[name="exportType"]:checked'))
                    .map(cb => cb.value);
                
                // Get custom dates if selected
                let customDates = null;
                if (range === 'custom') {
                    const startDate = document.getElementById('startDate').value;
                    const endDate = document.getElementById('endDate').value;
                    customDates = { start: startDate, end: endDate };
                }
                
                exportActivityLog(range, format, selectedTypes, customDates);
                closeModalFunc(exportOptionsModal);
            });
        }
    }
    
    function exportActivityLog(range, format, types = [], customDates = null) {
        // This would typically make an API call
        showNotification(`Exporting activity log in ${format.toUpperCase()} format...`, 'info');
        
        // Simulate export
        setTimeout(() => {
            showNotification('Activity log exported successfully!', 'success');
            
            // Simulate download
            const filename = `activity_log_${new Date().toISOString().split('T')[0]}.${format}`;
            simulateDownload(filename, format);
        }, 2000);
    }
    
    function simulateDownload(filename, format) {
        const data = {
            csv: 'id,type,description,timestamp\n1,login,User logged in,2025-01-23 10:30:00',
            json: '{"activities": [{"id": 1, "type": "login", "description": "User logged in", "timestamp": "2025-01-23T10:30:00"}]}',
            pdf: 'PDF content would be generated here',
            excel: 'Excel content would be generated here'
        };
        
        const content = data[format] || data.csv;
        const blob = new Blob([content], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
    
    // Timeline interactions
    function setupTimelineInteractions() {
        // Toggle details
        document.querySelectorAll('.toggle-details').forEach(button => {
            button.addEventListener('click', function() {
                const details = this.nextElementSibling;
                const isVisible = details.style.display === 'block';
                
                details.style.display = isVisible ? 'none' : 'block';
                this.innerHTML = `<i class="fas fa-chevron-${isVisible ? 'down' : 'up'}"></i> ${isVisible ? 'View' : 'Hide'} Details`;
            });
        });
        
        // Load more button
        const loadMoreBtn = document.getElementById('loadMoreBtn');
        if (loadMoreBtn) {
            loadMoreBtn.addEventListener('click', function() {
                // This would typically load more activities from the server
                showNotification('Loading more activities...', 'info');
                
                // Simulate loading
                setTimeout(() => {
                    const newActivity = document.createElement('div');
                    newActivity.className = 'timeline-item';
                    newActivity.innerHTML = `
                        <div class="timeline-marker">
                            <div class="marker-icon">
                                <i class="fas fa-plus"></i>
                            </div>
                        </div>
                        <div class="timeline-content">
                            <div class="timeline-header">
                                <div class="activity-description">
                                    <h4>Loaded additional activity</h4>
                                    <div class="activity-meta">
                                        <span class="activity-type system">
                                            <i class="fas fa-tag"></i>
                                            System
                                        </span>
                                    </div>
                                </div>
                                <div class="activity-time">
                                    <i class="fas fa-clock"></i>
                                    <span class="time-display">Just now</span>
                                </div>
                            </div>
                        </div>
                    `;
                    
                    document.getElementById('activityTimeline').appendChild(newActivity);
                    showNotification('More activities loaded', 'success');
                    updateActivityCounts();
                }, 1500);
            });
        }
        
        // Scroll to top button
        const scrollToTopBtn = document.getElementById('scrollToTopBtn');
        if (scrollToTopBtn) {
            scrollToTopBtn.addEventListener('click', () => {
                window.scrollTo({ top: 0, behavior: 'smooth' });
            });
        }
    }
    
    // Calculate insights
    function calculateInsights() {
        const activityItems = document.querySelectorAll('.timeline-item');
        const activities = Array.from(activityItems).map(item => ({
            date: new Date(item.dataset.date),
            type: item.dataset.type
        }));
        
        if (activities.length === 0) return;
        
        // Calculate most active day
        const dayCounts = {};
        activities.forEach(activity => {
            const day = activity.date.toLocaleDateString('en-US', { weekday: 'long' });
            dayCounts[day] = (dayCounts[day] || 0) + 1;
        });
        
        const mostActiveDay = Object.entries(dayCounts).reduce((a, b) => 
            a[1] > b[1] ? a : b
        )[0];
        
        // Calculate peak activity time
        const hourCounts = {};
        activities.forEach(activity => {
            const hour = activity.date.getHours();
            hourCounts[hour] = (hourCounts[hour] || 0) + 1;
        });
        
        const peakHour = Object.entries(hourCounts).reduce((a, b) => 
            a[1] > b[1] ? a : b
        )[0];
        
        const peakTime = `${peakHour}:00 - ${parseInt(peakHour) + 1}:00`;
        
        // Calculate activity trend
        const recentCount = activities.filter(a => {
            const weekAgo = new Date();
            weekAgo.setDate(weekAgo.getDate() - 7);
            return a.date >= weekAgo;
        }).length;
        
        const previousCount = activities.filter(a => {
            const twoWeeksAgo = new Date();
            twoWeeksAgo.setDate(twoWeeksAgo.getDate() - 14);
            const weekAgo = new Date();
            weekAgo.setDate(weekAgo.getDate() - 7);
            return a.date >= twoWeeksAgo && a.date < weekAgo;
        }).length;
        
        let trend = 'Stable';
        if (recentCount > previousCount * 1.2) trend = 'Increasing';
        else if (recentCount < previousCount * 0.8) trend = 'Decreasing';
        
        // Update DOM
        document.getElementById('mostActiveDay').textContent = mostActiveDay;
        document.getElementById('peakActivityTime').textContent = peakTime;
        document.getElementById('activityTrend').textContent = trend;
    }
    
    function updateActivityCounts() {
        const activityItems = document.querySelectorAll('.timeline-item');
        const types = ['login', 'profile', 'password', 'report'];
        
        types.forEach(type => {
            const count = Array.from(activityItems).filter(item => 
                item.dataset.type === type
            ).length;
            document.getElementById(`${type}Count`).textContent = count;
        });
        
        document.getElementById('visibleActivitiesCount').textContent = activityItems.length;
        calculateInsights();
    }
    
    // Utility functions
    function openModal(modal) {
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
    
    function closeModalFunc(modal) {
        modal.classList.remove('active');
        document.body.style.overflow = '';
    }
    
    function showNotification(message, type = 'info') {
        // Remove existing notifications
        const existing = document.querySelectorAll('.activity-notification');
        existing.forEach(n => n.remove());
        
        const notification = document.createElement('div');
        notification.className = `activity-notification notification-${type}`;
        notification.innerHTML = `
            <div class="notification-content">
                <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
                <span>${message}</span>
            </div>
        `;
        
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: ${type === 'success' ? '#48bb78' : type === 'error' ? '#fc8181' : '#4299e1'};
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 9999;
            animation: slideIn 0.3s ease-out;
            max-width: 400px;
        `;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            if (notification.parentNode) {
                notification.style.animation = 'slideOut 0.3s ease-in forwards';
                setTimeout(() => notification.remove(), 300);
            }
        }, 5000);
    }
    
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
    
    // Keyboard shortcuts
    function setupKeyboardShortcuts() {
        document.addEventListener('keydown', function(e) {
            // Ctrl/Cmd + F: Focus search
            if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
                e.preventDefault();
                const searchInput = document.getElementById('searchActivity');
                if (searchInput) searchInput.focus();
            }
            
            // Ctrl/Cmd + E: Export
            if ((e.ctrlKey || e.metaKey) && e.key === 'e') {
                e.preventDefault();
                const exportBtn = document.getElementById('exportActivityBtn');
                if (exportBtn) exportBtn.click();
            }
            
            // Escape: Close modals
            if (e.key === 'Escape') {
                const modals = document.querySelectorAll('.modal.active');
                modals.forEach(modal => closeModalFunc(modal));
            }
        });
    }
});