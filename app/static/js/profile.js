// app/static/js/profile.js
document.addEventListener('DOMContentLoaded', function() {
    initializeProfilePage();
    
    function initializeProfilePage() {
        setupPasswordManagement();
        setupFormValidation();
        setupModals();
        setupPasswordStrength();
        setupThemeToggle();
    }
    
    // Password Management
    function setupPasswordManagement() {
        // Password visibility toggle
        const passwordToggles = document.querySelectorAll('.password-toggle');
        passwordToggles.forEach(toggle => {
            toggle.addEventListener('click', function() {
                const input = this.parentNode.querySelector('input');
                const isPassword = input.type === 'password';
                input.type = isPassword ? 'text' : 'password';
                this.innerHTML = `<i class="fas fa-${isPassword ? 'eye-slash' : 'eye'}"></i>`;
            });
        });
        
        // Generate password button
        const generateBtn = document.getElementById('generatePasswordBtn');
        if (generateBtn) {
            generateBtn.addEventListener('click', generateStrongPassword);
        }
    }
    
    function generateStrongPassword() {
        const length = 12;
        const charset = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*";
        let password = "";
        
        // Ensure at least one of each required character type
        password += getRandomChar("abcdefghijklmnopqrstuvwxyz");
        password += getRandomChar("ABCDEFGHIJKLMNOPQRSTUVWXYZ");
        password += getRandomChar("0123456789");
        password += getRandomChar("!@#$%^&*");
        
        // Fill the rest
        for (let i = password.length; i < length; i++) {
            password += charset.charAt(Math.floor(Math.random() * charset.length));
        }
        
        // Shuffle the password
        password = password.split('').sort(() => Math.random() - 0.5).join('');
        
        // Set password fields
        const newPasswordInput = document.getElementById('new_password');
        const confirmInput = document.getElementById('confirm_password');
        
        if (newPasswordInput && confirmInput) {
            newPasswordInput.value = password;
            confirmInput.value = password;
            
            // Trigger validation
            newPasswordInput.dispatchEvent(new Event('input'));
            
            // Show success message
            showNotification('Strong password generated!', 'success');
        }
    }
    
    function getRandomChar(charset) {
        return charset.charAt(Math.floor(Math.random() * charset.length));
    }
    
    // Password Strength Indicator
    function setupPasswordStrength() {
        const passwordInput = document.getElementById('new_password');
        if (!passwordInput) return;
        
        const strengthBar = document.querySelector('.strength-bar');
        const strengthText = document.querySelector('.strength-text');
        
        passwordInput.addEventListener('input', function() {
            const password = this.value;
            let strength = 0;
            
            // Length check
            if (password.length >= 8) strength += 25;
            if (password.length >= 12) strength += 25;
            
            // Complexity checks
            if (/[A-Z]/.test(password)) strength += 25;
            if (/[a-z]/.test(password)) strength += 25;
            if (/\d/.test(password)) strength += 25;
            if (/[!@#$%^&*]/.test(password)) strength += 25;
            
            // Cap at 100%
            strength = Math.min(strength, 100);
            
            // Update visual indicator
            strengthBar.style.setProperty('--strength-width', `${strength}%`);
            
            // Update text and color
            if (strength < 50) {
                strengthBar.style.setProperty('--strength-color', '#dc3545');
                strengthText.textContent = 'Weak password';
                strengthText.style.color = '#dc3545';
            } else if (strength < 75) {
                strengthBar.style.setProperty('--strength-color', '#ffc107');
                strengthText.textContent = 'Fair password';
                strengthText.style.color = '#ffc107';
            } else {
                strengthBar.style.setProperty('--strength-color', '#28a745');
                strengthText.textContent = 'Strong password';
                strengthText.style.color = '#28a745';
            }
        });
        
        // Add CSS variable for dynamic styling
        const style = document.createElement('style');
        style.textContent = `
            .strength-bar::after {
                width: var(--strength-width, 0%);
                background: var(--strength-color, #dc3545);
            }
        `;
        document.head.appendChild(style);
    }
    
    // Form Validation
    function setupFormValidation() {
        const changePasswordForm = document.getElementById('changePasswordForm');
        const updateProfileForm = document.getElementById('updateProfileForm');
        
        if (changePasswordForm) {
            changePasswordForm.addEventListener('submit', validatePasswordForm);
        }
        
        if (updateProfileForm) {
            updateProfileForm.addEventListener('submit', validateProfileForm);
        }
    }
    
    function validatePasswordForm(e) {
        const currentPassword = document.getElementById('current_password').value;
        const newPassword = document.getElementById('new_password').value;
        const confirmPassword = document.getElementById('confirm_password').value;
        
        // Basic validation
        if (!currentPassword) {
            e.preventDefault();
            showNotification('Please enter your current password', 'error');
            return false;
        }
        
        if (newPassword.length < 8) {
            e.preventDefault();
            showNotification('New password must be at least 8 characters', 'error');
            return false;
        }
        
        if (newPassword !== confirmPassword) {
            e.preventDefault();
            showNotification('Passwords do not match', 'error');
            return false;
        }
        
        // Check if new password is different from current
        if (newPassword === currentPassword) {
            e.preventDefault();
            showNotification('New password must be different from current password', 'error');
            return false;
        }
        
        return true;
    }
    
    function validateProfileForm(e) {
        const email = document.getElementById('email').value;
        
        if (!email) {
            e.preventDefault();
            showNotification('Email address is required', 'error');
            return false;
        }
        
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(email)) {
            e.preventDefault();
            showNotification('Please enter a valid email address', 'error');
            return false;
        }
        
        return true;
    }
    
    // Modals
    function setupModals() {
        // Delete Account Modal
        const deleteAccountBtn = document.getElementById('deleteAccountBtn');
        const deleteAccountModal = document.getElementById('deleteAccountModal');
        const confirmDeleteInput = document.getElementById('confirmDelete');
        const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');
        
        if (deleteAccountBtn && deleteAccountModal) {
            deleteAccountBtn.addEventListener('click', () => openModal(deleteAccountModal));
            
            // Close modal buttons
            const closeModal = deleteAccountModal.querySelector('.close-modal');
            const cancelDelete = deleteAccountModal.querySelector('.cancel-delete');
            
            closeModal.addEventListener('click', () => closeModalFunc(deleteAccountModal));
            cancelDelete.addEventListener('click', () => closeModalFunc(deleteAccountModal));
            
            // Confirm delete validation
            confirmDeleteInput.addEventListener('input', function() {
                confirmDeleteBtn.disabled = this.value !== 'DELETE';
            });
            
            // Confirm delete action
            confirmDeleteBtn.addEventListener('click', function() {
                if (confirm('Are you absolutely sure? This cannot be undone!')) {
                    // This would typically make an API call
                    showNotification('Account deletion request submitted', 'warning');
                    closeModalFunc(deleteAccountModal);
                    
                    // Simulate account deletion process
                    setTimeout(() => {
                        showNotification('Account has been scheduled for deletion', 'warning');
                    }, 1000);
                }
            });
        }
        
        // Export Data Modal
        const exportDataBtn = document.getElementById('exportDataBtn');
        const exportDataModal = document.getElementById('exportDataModal');
        
        if (exportDataBtn && exportDataModal) {
            exportDataBtn.addEventListener('click', () => openModal(exportDataModal));
            
            const closeModal = exportDataModal.querySelector('.close-modal');
            const cancelExport = exportDataModal.querySelector('.cancel-export');
            const startExportBtn = exportDataModal.querySelector('#startExportBtn');
            
            closeModal.addEventListener('click', () => closeModalFunc(exportDataModal));
            cancelExport.addEventListener('click', () => closeModalFunc(exportDataModal));
            
            startExportBtn.addEventListener('click', function() {
                const format = document.getElementById('exportFormat').value;
                const selectedOptions = Array.from(exportDataModal.querySelectorAll('input[type="checkbox"]:checked'))
                    .map(cb => cb.name.replace('export_', ''));
                
                // This would typically make an API call
                showNotification(`Exporting data in ${format.toUpperCase()} format...`, 'info');
                closeModalFunc(exportDataModal);
                
                // Simulate export process
                setTimeout(() => {
                    showNotification('Data export completed. Download will start shortly.', 'success');
                    simulateDownload(`user_data_export_${new Date().toISOString().split('T')[0]}.${format}`);
                }, 2000);
            });
        }
        
        // Clear History Modal
        const clearHistoryBtn = document.getElementById('clearHistoryBtn');
        const clearHistoryModal = document.getElementById('clearHistoryModal');
        
        if (clearHistoryBtn && clearHistoryModal) {
            clearHistoryBtn.addEventListener('click', () => openModal(clearHistoryModal));
            
            const closeModal = clearHistoryModal.querySelector('.close-modal');
            const cancelClear = clearHistoryModal.querySelector('.cancel-clear');
            const confirmClearBtn = clearHistoryModal.querySelector('#confirmClearBtn');
            
            closeModal.addEventListener('click', () => closeModalFunc(clearHistoryModal));
            cancelClear.addEventListener('click', () => closeModalFunc(clearHistoryModal));
            
            confirmClearBtn.addEventListener('click', function() {
                const clearAll = document.getElementById('clearAllHistory').checked;
                
                // This would typically make an API call
                showNotification(`Clearing ${clearAll ? 'all' : 'old'} activity history...`, 'warning');
                closeModalFunc(clearHistoryModal);
                
                // Simulate clearing process
                setTimeout(() => {
                    showNotification('Activity history has been cleared', 'success');
                    // Refresh the activity list
                    const activityTimeline = document.querySelector('.activity-timeline');
                    if (activityTimeline) {
                        activityTimeline.innerHTML = `
                            <div class="empty-state">
                                <i class="fas fa-history"></i>
                                <p>No recent activity</p>
                            </div>
                        `;
                    }
                }, 1500);
            });
        }
        
        // Close modal on outside click
        document.addEventListener('click', function(e) {
            const modals = document.querySelectorAll('.modal.active');
            modals.forEach(modal => {
                if (e.target === modal) {
                    closeModalFunc(modal);
                }
            });
        });
        
        // Close modal on Escape key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                const modals = document.querySelectorAll('.modal.active');
                modals.forEach(modal => closeModalFunc(modal));
            }
        });
    }
    
    function openModal(modal) {
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
    
    function closeModalFunc(modal) {
        modal.classList.remove('active');
        document.body.style.overflow = '';
    }
    
    function simulateDownload(filename) {
        // Create a dummy download link
        const link = document.createElement('a');
        link.href = 'data:text/plain;charset=utf-8,' + encodeURIComponent('This is a simulated file download.\nYour data export is ready.');
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }
    
    // Theme Toggle
    function setupThemeToggle() {
        const themeSelect = document.getElementById('theme_preference');
        if (!themeSelect) return;
        
        // Load saved theme preference
        const savedTheme = localStorage.getItem('theme_preference') || 'light';
        themeSelect.value = savedTheme;
        applyTheme(savedTheme);
        
        // Save theme preference on change
        themeSelect.addEventListener('change', function() {
            const theme = this.value;
            localStorage.setItem('theme_preference', theme);
            applyTheme(theme);
            showNotification(`Theme changed to ${theme}`, 'success');
        });
    }
    
    function applyTheme(theme) {
        document.body.classList.remove('theme-light', 'theme-dark');
        
        if (theme === 'dark' || (theme === 'auto' && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
            document.body.classList.add('theme-dark');
        } else {
            document.body.classList.add('theme-light');
        }
    }
    
    // Notification System
    function showNotification(message, type = 'info') {
        // Remove existing notifications
        const existingNotifications = document.querySelectorAll('.profile-notification');
        existingNotifications.forEach(n => n.remove());
        
        const notification = document.createElement('div');
        notification.className = `profile-notification notification-${type}`;
        notification.innerHTML = `
            <div class="notification-content">
                <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
                <span>${message}</span>
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
            background: ${type === 'success' ? '#48bb78' : type === 'error' ? '#fc8181' : '#4299e1'};
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 9999;
            animation: slideIn 0.3s ease-out;
            max-width: 400px;
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
            padding: 0;
        `;
        
        closeBtn.onmouseenter = () => closeBtn.style.opacity = '1';
        closeBtn.onmouseleave = () => closeBtn.style.opacity = '0.8';
        
        closeBtn.addEventListener('click', () => {
            notification.style.animation = 'slideOut 0.3s ease-in forwards';
            setTimeout(() => notification.remove(), 300);
        });
        
        document.body.appendChild(notification);
        
        // Auto remove after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.style.animation = 'slideOut 0.3s ease-in forwards';
                setTimeout(() => {
                    if (notification.parentNode) {
                        notification.remove();
                    }
                }, 300);
            }
        }, 5000);
        
        // Add animation keyframes
        const style = document.createElement('style');
        if (!document.querySelector('#notification-animations')) {
            style.id = 'notification-animations';
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
        }
    }
    
    // Keyboard Shortcuts
    document.addEventListener('keydown', function(e) {
        // Ctrl + Shift + P: Focus password form
        if (e.ctrlKey && e.shiftKey && e.key === 'P') {
            e.preventDefault();
            const passwordInput = document.getElementById('current_password');
            if (passwordInput) passwordInput.focus();
        }
        
        // Ctrl + Shift + E: Focus email form
        if (e.ctrlKey && e.shiftKey && e.key === 'E') {
            e.preventDefault();
            const emailInput = document.getElementById('email');
            if (emailInput) emailInput.focus();
        }
        
        // Ctrl + /: Show keyboard shortcuts help
        if (e.ctrlKey && e.key === '/') {
            e.preventDefault();
            showKeyboardShortcutsHelp();
        }
    });
    
    function showKeyboardShortcutsHelp() {
        const helpText = `
            Profile Page Keyboard Shortcuts:
            
            Ctrl + Shift + P: Focus password form
            Ctrl + Shift + E: Focus email form
            Ctrl + /: Show this help
            
            Tab: Navigate between form fields
            Enter: Submit current form
            Escape: Close any open modal
        `;
        
        alert(helpText);
    }
    
    // Initialize theme on load
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
        const themeSelect = document.getElementById('theme_preference');
        if (themeSelect && themeSelect.value === 'auto') {
            applyTheme('auto');
        }
    });
});