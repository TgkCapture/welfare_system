// app/static/js/settings.js
document.addEventListener('DOMContentLoaded', function() {
    // Initialize settings page
    initializeSettings();
    
    function initializeSettings() {
        setupFormValidation();
        setupTestConnection();
        setupAutoSave();
    }
    
    // Setup form validation
    function setupFormValidation() {
        const settingsForm = document.getElementById('settingsForm');
        const sheetUrlInput = document.getElementById('sheet_url');
        const saveBtn = document.getElementById('saveBtn');
        
        if (!settingsForm || !sheetUrlInput || !saveBtn) return;
        
        // Validate Google Sheets URL format
        function isValidGoogleSheetsUrl(url) {
            try {
                const urlObj = new URL(url);
                const isValidDomain = urlObj.hostname === 'docs.google.com';
                const isValidPath = urlObj.pathname.includes('/spreadsheets/d/');
                return isValidDomain && isValidPath;
            } catch (_) {
                return false;
            }
        }
        
        // Real-time validation
        sheetUrlInput.addEventListener('input', function() {
            const url = this.value.trim();
            const isValid = url === '' || isValidGoogleSheetsUrl(url);
            
            if (url && !isValid) {
                this.classList.add('is-invalid');
                this.classList.remove('is-valid');
                showValidationFeedback(this, 'Please enter a valid Google Sheets URL', 'error');
            } else if (url && isValid) {
                this.classList.remove('is-invalid');
                this.classList.add('is-valid');
                showValidationFeedback(this, 'Valid Google Sheets URL', 'success');
            } else {
                this.classList.remove('is-invalid', 'is-valid');
                clearValidationFeedback(this);
            }
        });
        
        // Form submission
        settingsForm.addEventListener('submit', function(e) {
            const url = sheetUrlInput.value.trim();
            
            if (url && !isValidGoogleSheetsUrl(url)) {
                e.preventDefault();
                showToast('Please enter a valid Google Sheets URL', 'error');
                sheetUrlInput.focus();
                return false;
            }
            
            // Show loading state
            showLoadingState(true);
        });
    }
    
    // Setup test connection functionality
    function setupTestConnection() {
        const testConnectionBtn = document.getElementById('testConnectionBtn');
        
        if (!testConnectionBtn) return;
        
        testConnectionBtn.addEventListener('click', function() {
            const sheetUrlInput = document.getElementById('sheet_url');
            const url = sheetUrlInput ? sheetUrlInput.value.trim() : '';
            
            if (!url) {
                showToast('Please enter a Google Sheets URL first', 'error');
                if (sheetUrlInput) sheetUrlInput.focus();
                return;
            }
            
            // Show connecting state
            this.classList.add('connecting');
            this.innerHTML = `
                <i class="fas fa-spinner fa-spin"></i>
                <span>Testing Connection...</span>
            `;
            this.disabled = true;
            
            // Simulate connection test (replace with actual API call)
            setTimeout(() => {
                // This would be replaced with actual API call to test Google Sheets connection
                const isSuccess = Math.random() > 0.3; // 70% success rate for demo
                
                this.classList.remove('connecting');
                this.disabled = false;
                this.innerHTML = `
                    <i class="fas fa-plug"></i>
                    <span>Test Connection</span>
                `;
                
                if (isSuccess) {
                    showToast('Connection successful! Google Sheets integration is working.', 'success');
                } else {
                    showToast('Connection failed. Please check the URL and sharing settings.', 'error');
                }
            }, 2000);
        });
    }
    
    // Setup auto-save indicator
    function setupAutoSave() {
        const sheetUrlInput = document.getElementById('sheet_url');
        const saveBtn = document.getElementById('saveBtn');
        
        if (!sheetUrlInput || !saveBtn) return;
        
        let originalValue = sheetUrlInput.value;
        let isChanged = false;
        
        sheetUrlInput.addEventListener('input', function() {
            isChanged = this.value !== originalValue;
            updateSaveButtonState();
        });
        
        function updateSaveButtonState() {
            if (isChanged) {
                saveBtn.innerHTML = `
                    <i class="fas fa-save"></i>
                    <span class="btn-text">Save Changes</span>
                `;
                saveBtn.classList.add('btn-warning');
                saveBtn.classList.remove('btn-primary');
            } else {
                saveBtn.innerHTML = `
                    <i class="fas fa-save"></i>
                    <span class="btn-text">Save Settings</span>
                `;
                saveBtn.classList.remove('btn-warning');
                saveBtn.classList.add('btn-primary');
            }
        }
        
        // Reset on successful save
        const settingsForm = document.getElementById('settingsForm');
        if (settingsForm) {
            settingsForm.addEventListener('submit', function() {
                originalValue = sheetUrlInput.value;
                isChanged = false;
                setTimeout(updateSaveButtonState, 100);
            });
        }
        
        // Warn before leaving unsaved changes
        window.addEventListener('beforeunload', function(e) {
            if (isChanged) {
                e.preventDefault();
                e.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
                return 'You have unsaved changes. Are you sure you want to leave?';
            }
        });
    }
    
    // Helper functions
    function showValidationFeedback(input, message, type) {
        // Remove existing feedback
        const existingFeedback = input.parentNode.querySelector('.validation-feedback');
        if (existingFeedback) {
            existingFeedback.remove();
        }
        
        // Add new feedback
        const feedback = document.createElement('div');
        feedback.className = `validation-feedback validation-${type}`;
        feedback.innerHTML = `
            <i class="fas fa-${type === 'error' ? 'exclamation-circle' : 'check-circle'}"></i>
            <span>${message}</span>
        `;
        
        input.parentNode.appendChild(feedback);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (feedback.parentNode) {
                feedback.remove();
            }
        }, 5000);
    }
    
    function clearValidationFeedback(input) {
        const feedback = input.parentNode.querySelector('.validation-feedback');
        if (feedback) {
            feedback.remove();
        }
    }
    
    function showLoadingState(show) {
        const saveBtn = document.getElementById('saveBtn');
        if (!saveBtn) return;
        
        if (show) {
            saveBtn.disabled = true;
            const btnText = saveBtn.querySelector('.btn-text');
            const btnLoading = saveBtn.querySelector('.btn-loading');
            if (btnText) btnText.style.display = 'none';
            if (btnLoading) btnLoading.style.display = 'flex';
        } else {
            saveBtn.disabled = false;
            const btnText = saveBtn.querySelector('.btn-text');
            const btnLoading = saveBtn.querySelector('.btn-loading');
            if (btnText) btnText.style.display = 'flex';
            if (btnLoading) btnLoading.style.display = 'none';
        }
    }
    
    // Show toast notification (uses base.js function)
    function showToast(message, type = 'info') {
        if (typeof window.showToast === 'function') {
            window.showToast(message, type);
        } else {
            alert(message);
        }
    }
    
    // Add validation feedback styles
    const validationStyles = document.createElement('style');
    validationStyles.textContent = `
        .is-valid {
            border-color: var(--success-color) !important;
            box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.1) !important;
        }
        
        .is-invalid {
            border-color: var(--danger-color) !important;
            box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.1) !important;
        }
        
        .validation-feedback {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-top: 0.5rem;
            font-size: 0.875rem;
            padding: 0.5rem;
            border-radius: var(--radius-sm);
            animation: slideInDown 0.3s ease;
        }
        
        .validation-error {
            background: rgba(239, 68, 68, 0.1);
            color: var(--danger-color);
            border: 1px solid rgba(239, 68, 68, 0.2);
        }
        
        .validation-success {
            background: rgba(16, 185, 129, 0.1);
            color: var(--success-color);
            border: 1px solid rgba(16, 185, 129, 0.2);
        }
        
        .btn-warning {
            background: linear-gradient(135deg, var(--warning-color), #fbbf24);
            color: white;
        }
        
        .btn-warning:hover {
            background: linear-gradient(135deg, #f59e0b, #fbbf24);
        }
        
        @keyframes slideInDown {
            from {
                opacity: 0;
                transform: translateY(-10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
    `;
    document.head.appendChild(validationStyles);
});