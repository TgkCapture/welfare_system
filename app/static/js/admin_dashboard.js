// app/static/js/admin_dashboard.js
document.addEventListener('DOMContentLoaded', function() {
    // Initialize admin dashboard
    initializeAdminDashboard();
    
    function initializeAdminDashboard() {
        setupChartAnimations();
        setupRealTimeUpdates();
        setupQuickLinks();
        setupActionButtons();
        setupNotifications();
    }
    
    // Setup chart animations for role distribution
    function setupChartAnimations() {
        const progressBars = document.querySelectorAll('.progress-bar');
        
        progressBars.forEach(bar => {
            const width = bar.style.width;
            bar.style.width = '0%';
            
            setTimeout(() => {
                bar.style.transition = 'width 1.5s ease-in-out';
                bar.style.width = width;
            }, 300);
        });
    }
    
    // Setup real-time updates (placeholder for future websocket integration)
    function setupRealTimeUpdates() {
        // Update online status
        updateOnlineStatus();
        
        // Refresh data every 30 seconds
        setInterval(updateDashboardData, 30000);
    }
    
    function updateOnlineStatus() {
        // This would be replaced with actual online status checking
        const onlineBadge = document.querySelector('.online-status');
        if (onlineBadge) {
            const isOnline = Math.random() > 0.3; // Demo: 70% chance online
            onlineBadge.classList.toggle('online', isOnline);
            onlineBadge.classList.toggle('offline', !isOnline);
            onlineBadge.innerHTML = `
                <i class="fas fa-${isOnline ? 'wifi' : 'times-circle'}"></i>
                ${isOnline ? 'Online' : 'Offline'}
            `;
        }
    }
    
    function updateDashboardData() {
        // This would fetch fresh data from the server
        console.log('Updating dashboard data...');
        
        // Update counters with animation
        animateCounter('.stat-value', 1000);
        
        // Show update notification
        showUpdateNotification();
    }
    
    function animateCounter(selector, duration) {
    const elements = document.querySelectorAll(selector);
    
    elements.forEach(element => {
        // Store the original value
        const originalText = element.textContent;
        
        // Just add a visual animation without changing the number
        element.style.transition = 'all 0.3s ease';
        element.style.color = 'var(--primary-color)';
        element.style.textShadow = '0 0 8px rgba(var(--primary-rgb), 0.3)';
        
        setTimeout(() => {
            element.style.color = '';
            element.style.textShadow = '';
        }, 1000);
        
        // Ensure the text stays the same
        setTimeout(() => {
            element.textContent = originalText;
        }, duration);
    });
}
    
    function showUpdateNotification() {
        const notification = document.createElement('div');
        notification.className = 'update-notification';
        notification.innerHTML = `
            <div class="notification-content">
                <i class="fas fa-sync-alt"></i>
                <span>Dashboard updated successfully</span>
                <button class="notification-close">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;
        
        // Add styles
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: var(--success-color, #28a745);
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 1000;
            animation: slideIn 0.3s ease-out;
        `;
        
        const content = notification.querySelector('.notification-content');
        content.style.cssText = `
            display: flex;
            align-items: center;
            gap: 10px;
        `;
        
        const closeBtn = notification.querySelector('.notification-close');
        closeBtn.style.cssText = `
            background: none;
            border: none;
            color: white;
            cursor: pointer;
            margin-left: 10px;
            opacity: 0.8;
            transition: opacity 0.2s;
        `;
        
        closeBtn.onmouseenter = () => closeBtn.style.opacity = '1';
        closeBtn.onmouseleave = () => closeBtn.style.opacity = '0.8';
        
        closeBtn.addEventListener('click', () => {
            notification.style.animation = 'slideOut 0.3s ease-in forwards';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        });
        
        // Add keyframe animations
        const style = document.createElement('style');
        style.textContent = `
            @keyframes slideIn {
                from {
                    transform: translateX(100%);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }
            @keyframes slideOut {
                from {
                    transform: translateX(0);
                    opacity: 1;
                }
                to {
                    transform: translateX(100%);
                    opacity: 0;
                }
            }
        `;
        document.head.appendChild(style);
        
        document.body.appendChild(notification);
        
        // Auto remove after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.style.animation = 'slideOut 0.3s ease-in forwards';
                setTimeout(() => {
                    if (notification.parentNode) {
                        notification.parentNode.removeChild(notification);
                    }
                }, 300);
            }
        }, 5000);
    }
    
    // Setup quick links interactions
    function setupQuickLinks() {
        const linkCards = document.querySelectorAll('.link-card');
        
        linkCards.forEach(card => {
            card.addEventListener('mouseenter', function() {
                this.style.transform = 'translateY(-5px)';
                this.style.boxShadow = '0 8px 25px rgba(0,0,0,0.15)';
            });
            
            card.addEventListener('mouseleave', function() {
                this.style.transform = 'translateY(0)';
                this.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)';
            });
            
            // Add click animation
            card.addEventListener('click', function(e) {
                if (!this.href) return;
                
                // Create ripple effect
                const ripple = document.createElement('span');
                const rect = this.getBoundingClientRect();
                const size = Math.max(rect.width, rect.height);
                const x = e.clientX - rect.left - size / 2;
                const y = e.clientY - rect.top - size / 2;
                
                ripple.style.cssText = `
                    position: absolute;
                    border-radius: 50%;
                    background: rgba(255, 255, 255, 0.7);
                    transform: scale(0);
                    animation: ripple 0.6s linear;
                    width: ${size}px;
                    height: ${size}px;
                    left: ${x}px;
                    top: ${y}px;
                    pointer-events: none;
                `;
                
                this.style.position = 'relative';
                this.style.overflow = 'hidden';
                this.appendChild(ripple);
                
                // Remove ripple after animation
                setTimeout(() => {
                    if (ripple.parentNode) {
                        ripple.parentNode.removeChild(ripple);
                    }
                }, 600);
            });
        });
        
        // Add ripple animation keyframes
        const rippleStyle = document.createElement('style');
        rippleStyle.textContent = `
            @keyframes ripple {
                to {
                    transform: scale(4);
                    opacity: 0;
                }
            }
        `;
        document.head.appendChild(rippleStyle);
    }
    
    // Setup action buttons and cards
    function setupActionButtons() {
        // Action items hover effects
        const actionItems = document.querySelectorAll('.action-item');
        
        actionItems.forEach(item => {
            item.addEventListener('mouseenter', function() {
                const icon = this.querySelector('.action-icon');
                if (icon) {
                    icon.style.transform = 'scale(1.1) rotate(5deg)';
                }
            });
            
            item.addEventListener('mouseleave', function() {
                const icon = this.querySelector('.action-icon');
                if (icon) {
                    icon.style.transform = 'scale(1) rotate(0deg)';
                }
            });
        });
        
        // Login items hover effects
        const loginItems = document.querySelectorAll('.login-item');
        loginItems.forEach(item => {
            item.addEventListener('mouseenter', function() {
                this.style.backgroundColor = 'var(--hover-color, #f8f9fa)';
            });
            
            item.addEventListener('mouseleave', function() {
                this.style.backgroundColor = '';
            });
        });
        
        // Report items hover effects
        const reportItems = document.querySelectorAll('.report-item');
        reportItems.forEach(item => {
            item.addEventListener('mouseenter', function() {
                this.style.transform = 'translateX(5px)';
                this.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)';
            });
            
            item.addEventListener('mouseleave', function() {
                this.style.transform = 'translateX(0)';
                this.style.boxShadow = 'none';
            });
        });
    }
    
    // Setup notification system
    function setupNotifications() {
        // Check for any system notifications
        checkSystemNotifications();
        
        // Listen for custom events (for future use)
        document.addEventListener('systemNotification', function(e) {
            showCustomNotification(e.detail);
        });
    }
    
    function checkSystemNotifications() {
        // This would check for system notifications from the server
        // For now, we'll just check for any important statuses
        
        const sheetsCard = document.querySelector('.stat-card.card-warning');
        if (sheetsCard && sheetsCard.querySelector('.fa-times')) {
            // Google Sheets is not configured
            setTimeout(() => {
                showWarningNotification(
                    'Google Sheets Integration',
                    'Google Sheets integration is not configured. Please configure it in settings.',
                    'warning'
                );
            }, 2000);
        }
    }
    
    function showWarningNotification(title, message, type = 'warning') {
        const notification = document.createElement('div');
        notification.className = `system-notification notification-${type}`;
        
        const icons = {
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle',
            success: 'fa-check-circle',
            error: 'fa-times-circle'
        };
        
        notification.innerHTML = `
            <div class="notification-header">
                <i class="fas ${icons[type]}"></i>
                <h4>${title}</h4>
                <button class="notification-close">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="notification-body">
                <p>${message}</p>
            </div>
            <div class="notification-footer">
                <a href="${type === 'warning' ? '/settings' : '#'}" class="btn btn-sm ${type === 'warning' ? 'btn-warning' : 'btn-primary'}">
                    ${type === 'warning' ? 'Configure Now' : 'View Details'}
                </a>
            </div>
        `;
        
        // Add to document
        const notificationsContainer = document.querySelector('.notifications-container') || createNotificationsContainer();
        notificationsContainer.appendChild(notification);
        
        // Animate in
        setTimeout(() => {
            notification.classList.add('show');
        }, 10);
        
        // Setup close button
        const closeBtn = notification.querySelector('.notification-close');
        closeBtn.addEventListener('click', () => {
            notification.classList.remove('show');
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        });
    }
    
    function createNotificationsContainer() {
        const container = document.createElement('div');
        container.className = 'notifications-container';
        container.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            display: flex;
            flex-direction: column;
            gap: 10px;
            max-width: 400px;
        `;
        document.body.appendChild(container);
        return container;
    }
    
    function showCustomNotification(detail) {
        const { title, message, type = 'info', duration = 5000 } = detail;
        showWarningNotification(title, message, type);
        
        if (duration > 0) {
            setTimeout(() => {
                const notifications = document.querySelectorAll('.system-notification');
                if (notifications.length > 0) {
                    const lastNotification = notifications[notifications.length - 1];
                    const closeBtn = lastNotification.querySelector('.notification-close');
                    if (closeBtn) closeBtn.click();
                }
            }, duration);
        }
    }
    
    // Add keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Alt + D: Focus dashboard search
        if (e.altKey && e.key === 'd') {
            e.preventDefault();
            const searchInput = document.querySelector('input[type="search"]');
            if (searchInput) searchInput.focus();
        }
        
        // Alt + N: Show new user form
        if (e.altKey && e.key === 'n') {
            e.preventDefault();
            const newUserBtn = document.querySelector('a[href*="create_user"]');
            if (newUserBtn) newUserBtn.click();
        }
        
        // Alt + R: Refresh dashboard
        if (e.altKey && e.key === 'r') {
            e.preventDefault();
            updateDashboardData();
        }
    });
    
    // Add resize handler for responsive adjustments
    window.addEventListener('resize', debounce(function() {
        adjustLayoutForScreenSize();
    }, 250));
    
    function adjustLayoutForScreenSize() {
        const screenWidth = window.innerWidth;
        const statsGrid = document.querySelector('.stats-grid');
        const contentGrid = document.querySelector('.content-grid');
        
        if (statsGrid && screenWidth < 768) {
            statsGrid.style.gridTemplateColumns = 'repeat(auto-fit, minmax(250px, 1fr))';
        }
        
        if (contentGrid && screenWidth < 1024) {
            contentGrid.style.gridTemplateColumns = '1fr';
        }
    }
    
    // Debounce utility function
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
    
    // Initialize layout adjustments
    adjustLayoutForScreenSize();
});