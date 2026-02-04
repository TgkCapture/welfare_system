// app/static/js/edit_user.js
document.addEventListener('DOMContentLoaded', function() {
    initializeEditUserForm();
    
    function initializeEditUserForm() {
        setupFormValidation();
        setupPasswordToggle();
        setupDeleteConfirmation();
        setupFormSubmission();
        setupRoleChangeWarning();
        setupStatusChangeWarning();
    }
    
    // Setup form validation
    function setupFormValidation() {
        const form = document.getElementById('editUserForm');
        if (!form) return;
        
        const emailInput = form.querySelector('#email');
        const newPasswordInput = form.querySelector('#new_password');
        const confirmPasswordInput = form.querySelector('#confirm_password');
        
        // Real-time email validation
        emailInput.addEventListener('blur', validateEmail);
        
        // Password validation only when filled
        newPasswordInput.addEventListener('input', function() {
            if (this.value.trim()) {
                validateNewPassword();
                validatePasswordMatch();
            } else {
                clearPasswordErrors();
            }
        });
        
        confirmPasswordInput.addEventListener('input', function() {
            if (this.value.trim() || newPasswordInput.value.trim()) {
                validatePasswordMatch();
            }
        });
        
        // Prevent submitting if validation fails
        form.addEventListener('submit', validateForm);
    }
    
    function validateEmail() {
        const emailInput = document.querySelector('#email');
        const email = emailInput.value.trim();
        const errorDiv = emailInput.parentNode.querySelector('.error-feedback') || createErrorDiv(emailInput.parentNode);
        
        if (!email) {
            showError(emailInput, errorDiv, 'Email is required');
            return false;
        }
        
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(email)) {
            showError(emailInput, errorDiv, 'Please enter a valid email address');
            return false;
        }
        
        clearError(emailInput, errorDiv);
        return true;
    }
    
    function validateNewPassword() {
        const newPasswordInput = document.querySelector('#new_password');
        const password = newPasswordInput.value;
        
        if (!password.trim()) {
            return true; // Password is optional
        }
        
        const errorDiv = newPasswordInput.parentNode.querySelector('.error-feedback') || createErrorDiv(newPasswordInput.parentNode);
        
        if (password.length < 8) {
            showError(newPasswordInput, errorDiv, 'Password must be at least 8 characters');
            return false;
        }
        
        const hasUpperCase = /[A-Z]/.test(password);
        const hasLowerCase = /[a-z]/.test(password);
        const hasNumbers = /\d/.test(password);
        
        if (!hasUpperCase || !hasLowerCase || !hasNumbers) {
            showError(newPasswordInput, errorDiv, 'Password must include uppercase, lowercase, and numbers');
            return false;
        }
        
        clearError(newPasswordInput, errorDiv);
        return true;
    }
    
    function validatePasswordMatch() {
        const newPasswordInput = document.querySelector('#new_password');
        const confirmPasswordInput = document.querySelector('#confirm_password');
        
        if (!newPasswordInput.value.trim() && !confirmPasswordInput.value.trim()) {
            return true; // Both empty is fine
        }
        
        const confirmErrorDiv = confirmPasswordInput.parentNode.querySelector('.error-feedback') || createErrorDiv(confirmPasswordInput.parentNode);
        
        if (!confirmPasswordInput.value.trim()) {
            showError(confirmPasswordInput, confirmErrorDiv, 'Please confirm the new password');
            return false;
        }
        
        if (newPasswordInput.value !== confirmPasswordInput.value) {
            showError(confirmPasswordInput, confirmErrorDiv, 'Passwords do not match');
            return false;
        }
        
        clearError(confirmPasswordInput, confirmErrorDiv);
        return true;
    }
    
    function clearPasswordErrors() {
        const newPasswordInput = document.querySelector('#new_password');
        const confirmPasswordInput = document.querySelector('#confirm_password');
        
        [newPasswordInput, confirmPasswordInput].forEach(input => {
            const errorDiv = input.parentNode.querySelector('.error-feedback');
            if (errorDiv) {
                errorDiv.textContent = '';
                errorDiv.style.display = 'none';
            }
            input.classList.remove('is-invalid');
            
            // Remove error icons
            const icon = input.parentNode.querySelector('.input-error-icon');
            if (icon) icon.remove();
        });
    }
    
    // Setup password visibility toggle
    function setupPasswordToggle() {
        const passwordInputs = document.querySelectorAll('input[type="password"]');
        
        passwordInputs.forEach(input => {
            const toggleBtn = document.createElement('button');
            toggleBtn.type = 'button';
            toggleBtn.className = 'password-toggle';
            toggleBtn.innerHTML = '<i class="fas fa-eye"></i>';
            toggleBtn.style.cssText = `
                position: absolute;
                right: 10px;
                top: 50%;
                transform: translateY(-50%);
                background: none;
                border: none;
                color: #6c757d;
                cursor: pointer;
                padding: 5px;
                z-index: 2;
            `;
            
            const inputGroup = input.parentNode;
            inputGroup.style.position = 'relative';
            inputGroup.appendChild(toggleBtn);
            
            toggleBtn.addEventListener('click', function() {
                const isPassword = input.type === 'password';
                input.type = isPassword ? 'text' : 'password';
                this.innerHTML = `<i class="fas fa-${isPassword ? 'eye-slash' : 'eye'}"></i>`;
            });
        });
    }
    
    // Setup delete confirmation modal
    function setupDeleteConfirmation() {
        const deleteBtn = document.getElementById('deleteUserBtn');
        const modal = document.getElementById('deleteUserModal');
        
        if (!deleteBtn || !modal) return;
        
        const closeBtn = modal.querySelector('.close-modal');
        const cancelBtn = modal.querySelector('.cancel-delete');
        
        // Open modal
        deleteBtn.addEventListener('click', function(e) {
            e.preventDefault();
            modal.classList.add('active');
            document.body.style.overflow = 'hidden';
        });
        
        // Close modal functions
        function closeModal() {
            modal.classList.remove('active');
            document.body.style.overflow = '';
        }
        
        closeBtn.addEventListener('click', closeModal);
        cancelBtn.addEventListener('click', closeModal);
        
        // Close on outside click
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                closeModal();
            }
        });
        
        // Close on Escape key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && modal.classList.contains('active')) {
                closeModal();
            }
        });
    }
    
    // Setup role change warning
    function setupRoleChangeWarning() {
        const roleSelect = document.querySelector('#role');
        if (!roleSelect) return;
        
        const originalRole = roleSelect.value;
        
        roleSelect.addEventListener('change', function() {
            if (this.value !== originalRole) {
                const warning = document.querySelector('.role-change-warning') || createRoleChangeWarning();
                warning.style.display = 'block';
                
                // Auto-hide after 10 seconds
                setTimeout(() => {
                    warning.style.display = 'none';
                }, 10000);
            }
        });
    }
    
    function createRoleChangeWarning() {
        const warning = document.createElement('div');
        warning.className = 'role-change-warning alert alert-warning';
        warning.style.cssText = `
            margin-top: 10px;
            padding: 10px;
            border-radius: 4px;
            display: none;
        `;
        warning.innerHTML = `
            <i class="fas fa-exclamation-triangle"></i>
            Changing a user's role will affect their system permissions immediately.
        `;
        
        const roleGroup = document.querySelector('#role').parentNode;
        roleGroup.appendChild(warning);
        return warning;
    }
    
    // Setup status change warning
    function setupStatusChangeWarning() {
        const statusCheckbox = document.querySelector('#is_active');
        if (!statusCheckbox) return;
        
        const originalStatus = statusCheckbox.checked;
        
        statusCheckbox.addEventListener('change', function() {
            if (this.checked !== originalStatus) {
                const action = this.checked ? 'activate' : 'deactivate';
                const message = this.checked 
                    ? 'User will be able to log in immediately.'
                    : 'User will no longer be able to log in.';
                
                if (!confirm(`Are you sure you want to ${action} this user? ${message}`)) {
                    this.checked = originalStatus;
                }
            }
        });
    }
    
    // Setup form submission
    function setupFormSubmission() {
        const form = document.getElementById('editUserForm');
        const submitBtn = form.querySelector('button[type="submit"]');
        
        form.addEventListener('submit', function(e) {
            if (!validateForm()) {
                e.preventDefault();
                return;
            }
            
            // Show loading state
            const originalText = submitBtn.innerHTML;
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving Changes...';
            
            // Re-enable after 2 seconds (for demo)
            setTimeout(() => {
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalText;
            }, 2000);
        });
    }
    
    function validateForm() {
        const isValidEmail = validateEmail();
        const isValidPassword = validateNewPassword();
        const isValidConfirm = validatePasswordMatch();
        
        if (!isValidEmail || !isValidPassword || !isValidConfirm) {
            // Scroll to first error
            const firstError = document.querySelector('.is-invalid');
            if (firstError) {
                firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
                firstError.focus();
            }
            
            // Show error summary
            showErrorSummary();
            return false;
        }
        
        return true;
    }
    
    function showErrorSummary() {
        let errorSummary = document.querySelector('.error-summary');
        
        if (!errorSummary) {
            errorSummary = document.createElement('div');
            errorSummary.className = 'error-summary alert alert-danger';
            errorSummary.style.cssText = `
                margin-bottom: 20px;
                display: none;
            `;
            
            const form = document.getElementById('editUserForm');
            form.parentNode.insertBefore(errorSummary, form);
        }
        
        const errors = document.querySelectorAll('.is-invalid');
        if (errors.length === 0) {
            errorSummary.style.display = 'none';
            return;
        }
        
        errorSummary.innerHTML = `
            <h5 style="margin-top: 0;">
                <i class="fas fa-exclamation-triangle"></i>
                Please fix the following errors:
            </h5>
            <ul class="mb-0" style="padding-left: 20px;">
                ${Array.from(errors).map(input => {
                    const label = input.parentNode.querySelector('label')?.textContent || 'Field';
                    const error = input.parentNode.querySelector('.error-feedback')?.textContent || 'Invalid';
                    return `<li><strong>${label}:</strong> ${error}</li>`;
                }).join('')}
            </ul>
        `;
        errorSummary.style.display = 'block';
    }
    
    // Helper functions for error handling
    function createErrorDiv(parent) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-feedback';
        errorDiv.style.cssText = `
            margin-top: 5px;
            font-size: 12px;
            color: #dc3545;
            display: none;
        `;
        parent.appendChild(errorDiv);
        return errorDiv;
    }
    
    function showError(input, errorDiv, message) {
        input.classList.add('is-invalid');
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
        
        // Add icon to input
        const inputGroup = input.parentNode;
        if (!inputGroup.querySelector('.input-error-icon')) {
            const icon = document.createElement('i');
            icon.className = 'fas fa-exclamation-circle input-error-icon';
            icon.style.cssText = `
                position: absolute;
                right: 40px; // Account for password toggle
                top: 50%;
                transform: translateY(-50%);
                color: #dc3545;
                z-index: 1;
            `;
            inputGroup.style.position = 'relative';
            inputGroup.appendChild(icon);
        }
    }
    
    function clearError(input, errorDiv) {
        input.classList.remove('is-invalid');
        errorDiv.textContent = '';
        errorDiv.style.display = 'none';
        
        // Remove error icon
        const icon = input.parentNode.querySelector('.input-error-icon');
        if (icon) icon.remove();
    }
    
    // Add password generator
    function setupPasswordGenerator() {
        const newPasswordGroup = document.querySelector('#new_password').parentNode;
        
        const generateBtn = document.createElement('button');
        generateBtn.type = 'button';
        generateBtn.className = 'btn btn-sm btn-outline';
        generateBtn.innerHTML = '<i class="fas fa-key"></i> Generate';
        generateBtn.style.marginTop = '5px';
        
        newPasswordGroup.appendChild(generateBtn);
        
        generateBtn.addEventListener('click', function() {
            const password = generateSecurePassword();
            const passwordInput = document.querySelector('#new_password');
            const confirmInput = document.querySelector('#confirm_password');
            
            passwordInput.value = password;
            confirmInput.value = password;
            
            // Trigger validation
            passwordInput.dispatchEvent(new Event('input'));
            confirmInput.dispatchEvent(new Event('input'));
            
            // Show success message
            const message = document.createElement('small');
            message.className = 'text-success';
            message.style.display = 'block';
            message.innerHTML = `<i class="fas fa-check"></i> Secure password generated`;
            
            // Remove previous message
            const prevMessage = newPasswordGroup.querySelector('.text-success');
            if (prevMessage) prevMessage.remove();
            
            newPasswordGroup.appendChild(message);
            
            // Auto-remove message
            setTimeout(() => {
                if (message.parentNode) {
                    message.remove();
                }
            }, 3000);
        });
    }
    
    function generateSecurePassword() {
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
        return password.split('').sort(() => Math.random() - 0.5).join('');
    }
    
    function getRandomChar(charset) {
        return charset.charAt(Math.floor(Math.random() * charset.length));
    }
    
    // Add change tracking
    function setupChangeTracking() {
        const form = document.getElementById('editUserForm');
        const originalData = {};
        
        // Store original values
        ['email', 'role', 'is_active'].forEach(field => {
            const element = form.querySelector(`[name="${field}"]`);
            if (element) {
                originalData[field] = element.type === 'checkbox' ? element.checked : element.value;
            }
        });
        
        // Check for changes before leaving page
        window.addEventListener('beforeunload', function(e) {
            const hasChanges = checkForChanges(originalData);
            
            if (hasChanges) {
                e.preventDefault();
                e.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
            }
        });
        
        // Form submission clears the warning
        form.addEventListener('submit', function() {
            window.removeEventListener('beforeunload', arguments.callee);
        });
    }
    
    function checkForChanges(originalData) {
        const form = document.getElementById('editUserForm');
        let hasChanges = false;
        
        ['email', 'role', 'is_active'].forEach(field => {
            const element = form.querySelector(`[name="${field}"]`);
            if (element) {
                const currentValue = element.type === 'checkbox' ? element.checked : element.value;
                if (currentValue !== originalData[field]) {
                    hasChanges = true;
                }
            }
        });
        
        // Check password fields
        const newPassword = form.querySelector('#new_password').value.trim();
        const confirmPassword = form.querySelector('#confirm_password').value.trim();
        if (newPassword || confirmPassword) {
            hasChanges = true;
        }
        
        return hasChanges;
    }
    
    // Initialize additional features
    setupPasswordGenerator();
    setupChangeTracking();
});