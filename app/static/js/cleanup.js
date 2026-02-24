// Cleanup Page JavaScript
document.addEventListener('DOMContentLoaded', function() {
    initializeCleanupPage();
    
    function initializeCleanupPage() {
        setupCleanupForm();
        setupRealTimeUpdates();
        setupStorageProgress();
        setupConfirmationDialogs();
        setupAutoRefresh();
    }
    
    // Cleanup form submission
    function setupCleanupForm() {
        const cleanupForm = document.getElementById('cleanupForm');
        if (!cleanupForm) return;
        
        cleanupForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const daysToKeep = parseInt(document.getElementById('daysToKeep').value);
            const dryRun = document.getElementById('dryRun').checked;
            const forceCleanup = document.getElementById('forceCleanup').checked;
            
            if (!forceCleanup) {
                const confirmed = confirm(
                    `Cleanup files older than ${daysToKeep} days?\n\n` +
                    `${dryRun ? 'This is a DRY RUN - no files will be deleted.' : 'This will PERMANENTLY DELETE old files.'}\n\n` +
                    'Are you sure you want to proceed?'
                );
                
                if (!confirmed) {
                    return;
                }
            }
            
            // Show loading state
            const submitButton = this.querySelector('button[type="submit"]');
            const originalText = submitButton.innerHTML;
            submitButton.innerHTML = `
                <i class="fas fa-spinner fa-spin"></i>
                ${dryRun ? 'Analyzing...' : 'Cleaning up...'}
            `;
            submitButton.disabled = true;
            
            // Collect form data
            const formData = new FormData(this);
            
            // Submit via AJAX
            fetch(this.action, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showCleanupResults(data);
                    updateStorageStats(data.storage_stats);
                } else {
                    showError(data.error || 'Cleanup failed');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showError('An error occurred during cleanup');
            })
            .finally(() => {
                // Reset button
                submitButton.innerHTML = originalText;
                submitButton.disabled = false;
            });
        });
    }
    
    // Real-time storage updates
    function setupRealTimeUpdates() {
        // Update storage stats every 30 seconds
        setInterval(updateStorageDisplay, 30000);
        
        // Initial update
        updateStorageDisplay();
    }
    
    function updateStorageDisplay() {
        fetch('/admin/storage-status?json=true')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    updateStorageStats(data);
                }
            })
            .catch(error => {
                console.error('Failed to update storage stats:', error);
            });
    }
    
    function updateStorageStats(stats) {
        // Update total storage
        const totalElement = document.getElementById('totalStorage');
        if (totalElement && stats.total_size_mb) {
            totalElement.textContent = `${stats.total_size_mb.toFixed(2)} MB`;
        }
        
        // Update file count
        const fileCountElement = document.getElementById('totalFiles');
        if (fileCountElement && stats.total_files) {
            fileCountElement.textContent = stats.total_files.toLocaleString();
        }
        
        // Update folder-specific stats
        if (stats.folders) {
            for (const [folderName, folderStats] of Object.entries(stats.folders)) {
                const sizeElement = document.getElementById(`${folderName}Size`);
                const countElement = document.getElementById(`${folderName}Count`);
                
                if (sizeElement && folderStats.size_mb) {
                    sizeElement.textContent = `${folderStats.size_mb.toFixed(2)} MB`;
                }
                
                if (countElement && folderStats.file_count) {
                    countElement.textContent = folderStats.file_count.toLocaleString();
                }
            }
        }
        
        // Update progress bars
        updateStorageProgress();
    }
    
    // Storage progress visualization
    function setupStorageProgress() {
        updateStorageProgress();
    }
    
    function updateStorageProgress() {
        const progressBars = document.querySelectorAll('.progress-bar');
        
        progressBars.forEach(bar => {
            const folder = bar.dataset.folder;
            const current = parseFloat(bar.dataset.current) || 0;
            const limit = parseFloat(bar.dataset.limit) || 100;
            
            const percentage = Math.min((current / limit) * 100, 100);
            bar.style.width = `${percentage}%`;
            
            // Update color based on percentage
            if (percentage >= 90) {
                bar.style.background = 'linear-gradient(90deg, #e74c3c, #c0392b)';
            } else if (percentage >= 75) {
                bar.style.background = 'linear-gradient(90deg, #f39c12, #e67e22)';
            } else {
                bar.style.background = 'linear-gradient(90deg, #3498db, #2ecc71)';
            }
            
            // Update percentage text
            const percentageText = bar.parentElement.querySelector('.progress-percentage');
            if (percentageText) {
                percentageText.textContent = `${percentage.toFixed(1)}%`;
            }
        });
    }
    
    // Confirmation dialogs for destructive actions
    function setupConfirmationDialogs() {
        // Emergency cleanup button
        const emergencyBtn = document.getElementById('emergencyCleanup');
        if (emergencyBtn) {
            emergencyBtn.addEventListener('click', function(e) {
                e.preventDefault();
                
                const confirmed = confirm(
                    '⚠️ EMERGENCY CLEANUP ⚠️\n\n' +
                    'This will delete ALL files older than 1 day.\n' +
                    'Only reports from yesterday will be kept.\n\n' +
                    'This action is IRREVERSIBLE.\n\n' +
                    'Are you absolutely sure?'
                );
                
                if (confirmed) {
                    const confirmedAgain = confirm(
                        'FINAL WARNING:\n\n' +
                        'This will delete most of your stored files.\n' +
                        'Are you REALLY sure you want to continue?'
                    );
                    
                    if (confirmedAgain) {
                        performEmergencyCleanup(this);
                    }
                }
            });
        }
        
        // Reset all button
        const resetBtn = document.getElementById('resetAll');
        if (resetBtn) {
            resetBtn.addEventListener('click', function(e) {
                e.preventDefault();
                
                const confirmed = confirm(
                    'Reset all cleanup settings?\n\n' +
                    'This will reset all form values to their defaults.'
                );
                
                if (confirmed) {
                    document.getElementById('cleanupForm').reset();
                    showNotification('Settings reset to defaults', 'success');
                }
            });
        }
    }
    
    function performEmergencyCleanup(button) {
        const originalHTML = button.innerHTML;
        button.innerHTML = `
            <i class="fas fa-spinner fa-spin"></i>
            Emergency Cleanup in Progress...
        `;
        button.disabled = true;
        
        fetch('/admin/cleanup/emergency', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showCleanupResults(data);
                showNotification('Emergency cleanup completed successfully', 'success');
            } else {
                showError(data.error || 'Emergency cleanup failed');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showError('Emergency cleanup failed');
        })
        .finally(() => {
            button.innerHTML = originalHTML;
            button.disabled = false;
        });
    }
    
    // Show cleanup results
    function showCleanupResults(data) {
        const resultsSection = document.getElementById('cleanupResults');
        if (!resultsSection) return;
        
        let html = `
            <div class="alert alert-${data.success ? 'success' : 'danger'}">
                <i class="fas fa-${data.success ? 'check-circle' : 'exclamation-triangle'}"></i>
                <div>
                    <strong>${data.success ? 'Cleanup Completed' : 'Cleanup Failed'}</strong>
                    <p>${data.message || (data.success ? 'Files have been cleaned up successfully.' : 'An error occurred during cleanup.')}</p>
                </div>
            </div>
        `;
        
        if (data.stats) {
            html += `
                <div class="results-table-container">
                    <table class="results-table">
                        <thead>
                            <tr>
                                <th>Folder</th>
                                <th>Files Deleted</th>
                                <th>Space Freed</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>
            `;
            
            for (const [folder, stats] of Object.entries(data.stats.folder_stats || {})) {
                html += `
                    <tr>
                        <td>${folder}</td>
                        <td>${stats.deleted || 0}</td>
                        <td>${(stats.freed_mb || 0).toFixed(2)} MB</td>
                        <td>
                            <span class="badge badge-${stats.exists ? 'success' : 'secondary'}">
                                ${stats.exists ? '✓ Cleaned' : '✗ Not found'}
                            </span>
                        </td>
                    </tr>
                `;
            }
            
            html += `
                        </tbody>
                        <tfoot>
                            <tr>
                                <th>Total</th>
                                <th>${data.stats.deleted_count || 0}</th>
                                <th>${(data.stats.freed_space_mb || 0).toFixed(2)} MB</th>
                                <th></th>
                            </tr>
                        </tfoot>
                    </table>
                </div>
            `;
        }
        
        resultsSection.innerHTML = html;
        resultsSection.style.display = 'block';
        
        // Scroll to results
        resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    
    // Auto-refresh functionality
    function setupAutoRefresh() {
        // Refresh storage stats every minute if auto-refresh is enabled
        const autoRefreshCheckbox = document.getElementById('autoRefresh');
        if (autoRefreshCheckbox) {
            let refreshInterval;
            
            autoRefreshCheckbox.addEventListener('change', function() {
                if (this.checked) {
                    refreshInterval = setInterval(updateStorageDisplay, 60000);
                    showNotification('Auto-refresh enabled (every minute)', 'info');
                } else {
                    clearInterval(refreshInterval);
                    showNotification('Auto-refresh disabled', 'info');
                }
            });
            
            // Cleanup on page unload
            window.addEventListener('beforeunload', function() {
                clearInterval(refreshInterval);
            });
        }
    }
    
    // Utility functions
    function showError(message) {
        showNotification(message, 'danger');
    }
    
    function showNotification(message, type = 'info') {
        // Remove existing notifications
        const existingNotifications = document.querySelectorAll('.notification');
        existingNotifications.forEach(notification => notification.remove());
        
        // Create new notification
        const notification = document.createElement('div');
        notification.className = `notification alert alert-${type}`;
        notification.innerHTML = `
            <i class="fas fa-${getNotificationIcon(type)}"></i>
            <span>${message}</span>
            <button class="notification-close">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        // Add styles
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            padding: 15px 20px;
            border-radius: 8px;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
            display: flex;
            align-items: center;
            gap: 10px;
            animation: slideInRight 0.3s ease;
            max-width: 400px;
        `;
        
        // Add close button functionality
        const closeBtn = notification.querySelector('.notification-close');
        closeBtn.style.cssText = `
            background: transparent;
            border: none;
            cursor: pointer;
            padding: 0;
            margin-left: auto;
            color: inherit;
            opacity: 0.7;
            transition: opacity 0.2s;
        `;
        
        closeBtn.addEventListener('click', () => {
            notification.style.animation = 'slideOutRight 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        });
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (notification.parentElement) {
                notification.style.animation = 'slideOutRight 0.3s ease';
                setTimeout(() => notification.remove(), 300);
            }
        }, 5000);
        
        document.body.appendChild(notification);
        
        // Add animation styles if not already present
        if (!document.getElementById('notification-styles')) {
            const style = document.createElement('style');
            style.id = 'notification-styles';
            style.textContent = `
                @keyframes slideInRight {
                    from {
                        transform: translateX(100%);
                        opacity: 0;
                    }
                    to {
                        transform: translateX(0);
                        opacity: 1;
                    }
                }
                
                @keyframes slideOutRight {
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
        }
    }
    
    function getNotificationIcon(type) {
        const icons = {
            'success': 'check-circle',
            'danger': 'exclamation-circle',
            'warning': 'exclamation-triangle',
            'info': 'info-circle'
        };
        return icons[type] || 'info-circle';
    }
    
    // Keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Ctrl/Cmd + Shift + C to focus cleanup form
        if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'C') {
            e.preventDefault();
            const daysInput = document.getElementById('daysToKeep');
            if (daysInput) {
                daysInput.focus();
                daysInput.select();
            }
        }
        
        // Escape to close notifications
        if (e.key === 'Escape') {
            const notifications = document.querySelectorAll('.notification');
            notifications.forEach(notification => notification.remove());
        }
    });
});