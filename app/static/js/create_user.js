// app/static/js/create_user.js
document.addEventListener('DOMContentLoaded', function() {
    initializeCreateUserForm();
    
    function initializeCreateUserForm() {
        setupFormValidation();
        setupPasswordStrength();
        setupRoleSelection();
        setupFormSubmission();
    }
    
    // Setup form validation
    function setupFormValidation() {
        const form = document.getElementById('createUserForm');
        if (!form) return;
        
        const emailInput = form.querySelector('#email');
        const passwordInput = form.querySelector('#password');
        const confirmInput = form.querySelector('#confirm');
        const roleSelect = form.querySelector('#role');
        
        // Real-time email validation
        emailInput.addEventListener('blur', validateEmail);
        emailInput.addEventListener('input', clearEmailError);
        
        // Password validation
        passwordInput.addEventListener('input', validatePassword);
        confirmInput.addEventListener('input', validatePasswordMatch);
        
        // Role selection guidance
        roleSelect.addEventListener('change', updateRoleGuidance);
        
        // Form submission validation
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
        
        // Check if email already exists (this would typically be an API call)
        // For now, we'll simulate a check
        if (email.includes('existing')) {
            showError(emailInput, errorDiv, 'This email is already registered');
            return false;
        }
        
        clearError(emailInput, errorDiv);
        return true;
    }
    
    function clearEmailError() {
        const emailInput = document.querySelector('#email');
        const errorDiv = emailInput.parentNode.querySelector('.error-feedback');
        if (errorDiv) {
            errorDiv.textContent = '';
            errorDiv.style.display = 'none';
        }
        emailInput.classList.remove('is-invalid');
    }
    
    function validatePassword() {
        const passwordInput = document.querySelector('#password');
        const password = passwordInput.value;
        const errorDiv = passwordInput.parentNode.querySelector('.error-feedback') || createErrorDiv(passwordInput.parentNode);
        
        if (!password) {
            showError(passwordInput, errorDiv, 'Password is required');
            return false;
        }
        
        if (password.length < 8) {
            showError(passwordInput, errorDiv, 'Password must be at least 8 characters');
            return false;
        }
        
        const hasUpperCase = /[A-Z]/.test(password);
        const hasLowerCase = /[a-z]/.test(password);
        const hasNumbers = /\d/.test(password);
        const hasSpecialChar = /[!@#$%^&*(),.?":{}|<>]/.test(password);
        
        if (!hasUpperCase || !hasLowerCase || !hasNumbers) {
            showError(passwordInput, errorDiv, 'Password must include uppercase, lowercase, and numbers');
            return false;
        }
        
        clearError(passwordInput, errorDiv);
        updatePasswordStrength(password);
        validatePasswordMatch();
        return true;
    }
    
    function validatePasswordMatch() {
        const passwordInput = document.querySelector('#password');
        const confirmInput = document.querySelector('#confirm');
        const confirmErrorDiv = confirmInput.parentNode.querySelector('.error-feedback') || createErrorDiv(confirmInput.parentNode);
        
        if (!confirmInput.value) {
            showError(confirmInput, confirmErrorDiv, 'Please confirm password');
            return false;
        }
        
        if (passwordInput.value !== confirmInput.value) {
            showError(confirmInput, confirmErrorDiv, 'Passwords do not match');
            return false;
        }
        
        clearError(confirmInput, confirmErrorDiv);
        return true;
    }
    
    function setupPasswordStrength() {
        const passwordInput = document.querySelector('#password');
        const strengthMeter = document.createElement('div');
        strengthMeter.className = 'password-strength';
        strengthMeter.style.cssText = `
            margin-top: 5px;
            height: 4px;
            background: #e9ecef;
            border-radius: 2px;
            overflow: hidden;
        `;
        
        const strengthBar = document.createElement('div');
        strengthBar.style.cssText = `
            height: 100%;
            width: 0%;
            background: #dc3545;
            transition: width 0.3s, background 0.3s;
        `;
        
        strengthMeter.appendChild(strengthBar);
        passwordInput.parentNode.appendChild(strengthMeter);
        
        // Add strength text
        const strengthText = document.createElement('small');
        strengthText.className = 'strength-text';
        strengthText.style.cssText = `
            display: block;
            margin-top: 5px;
            font-size: 12px;
            color: #6c757d;
        `;
        strengthMeter.parentNode.insertBefore(strengthText, strengthMeter.nextSibling);
        
        passwordInput.addEventListener('input', function() {
            updatePasswordStrength(this.value);
        });
    }
    
    function updatePasswordStrength(password) {
        const strengthBar = document.querySelector('.password-strength div');
        const strengthText = document.querySelector('.strength-text');
        
        if (!password) {
            strengthBar.style.width = '0%';
            strengthBar.style.background = '#dc3545';
            strengthText.textContent = '';
            return;
        }
        
        let strength = 0;
        
        // Length check
        if (password.length >= 8) strength += 25;
        if (password.length >= 12) strength += 25;
        
        // Complexity checks
        if (/[A-Z]/.test(password)) strength += 25;
        if (/[a-z]/.test(password)) strength += 25;
        if (/\d/.test(password)) strength += 25;
        if (/[!@#$%^&*(),.?":{}|<>]/.test(password)) strength += 25;
        
        // Cap at 100%
        strength = Math.min(strength, 100);
        
        strengthBar.style.width = `${strength}%`;
        
        // Update color and text based on strength
        if (strength < 50) {
            strengthBar.style.background = '#dc3545';
            strengthText.textContent = 'Weak password';
            strengthText.style.color = '#dc3545';
        } else if (strength < 75) {
            strengthBar.style.background = '#ffc107';
            strengthText.textContent = 'Fair password';
            strengthText.style.color = '#ffc107';
        } else {
            strengthBar.style.background = '#28a745';
            strengthText.textContent = 'Strong password';
            strengthText.style.color = '#28a745';
        }
    }
    
    function setupRoleSelection() {
        const roleSelect = document.querySelector('#role');
        const roleDescriptions = document.querySelector('.role-descriptions');
        
        if (!roleDescriptions) return;
        
        // Highlight selected role description
        roleSelect.addEventListener('change', function() {
            const selectedRole = this.value;
            
            roleDescriptions.querySelectorAll('.role-info').forEach(info => {
                info.style.opacity = '0.6';
                info.style.transform = 'scale(0.98)';
            });
            
            const selectedInfo = roleDescriptions.querySelector(`.role-info.${selectedRole}`);
            if (selectedInfo) {
                selectedInfo.style.opacity = '1';
                selectedInfo.style.transform = 'scale(1)';
                selectedInfo.style.boxShadow = '0 2px 8px rgba(0,0,0,0.1)';
            }
        });
        
        // Trigger initial highlight
        roleSelect.dispatchEvent(new Event('change'));
        
        // Make role descriptions clickable
        roleDescriptions.querySelectorAll('.role-info').forEach(info => {
            info.style.cursor = 'pointer';
            info.style.transition = 'all 0.3s ease';
            
            info.addEventListener('click', function() {
                const role = this.className.split(' ')[1];
                roleSelect.value = role;
                roleSelect.dispatchEvent(new Event('change'));
            });
        });
    }
    
    function updateRoleGuidance() {
        const role = this.value;
        const guidance = {
            'admin': 'Admin users have full system access including user management. Use this role carefully.',
            'clerk': 'Clerks can upload data and generate reports but cannot manage users.',
            'viewer': 'Viewers can only view reports and data. They cannot make changes.'
        };
        
        // Show guidance tooltip
        const tooltip = document.querySelector('.role-guidance') || createRoleGuidance();
        tooltip.textContent = guidance[role] || '';
        tooltip.style.display = guidance[role] ? 'block' : 'none';
    }
    
    function createRoleGuidance() {
        const tooltip = document.createElement('div');
        tooltip.className = 'role-guidance';
        tooltip.style.cssText = `
            margin-top: 10px;
            padding: 10px;
            background: #e7f3ff;
            border-left: 4px solid #007bff;
            border-radius: 4px;
            font-size: 14px;
            color: #004085;
        `;
        
        const roleGroup = document.querySelector('#role').parentNode;
        roleGroup.appendChild(tooltip);
        return tooltip;
    }
    
    function setupFormSubmission() {
        const form = document.getElementById('createUserForm');
        const submitBtn = form.querySelector('button[type="submit"]');
        
        form.addEventListener('submit', function(e) {
            if (!validateForm()) {
                e.preventDefault();
                return;
            }
            
            // Show loading state
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Creating User...';
            
            // Simulate API call delay
            setTimeout(() => {
                submitBtn.innerHTML = '<i class="fas fa-user-plus"></i> Create User';
                submitBtn.disabled = false;
            }, 2000);
        });
    }
    
    function validateForm() {
        const isValidEmail = validateEmail();
        const isValidPassword = validatePassword();
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
            errorSummary.className = 'error-summary';
            errorSummary.style.cssText = `
                margin-bottom: 20px;
                padding: 15px;
                background: #f8d7da;
                border: 1px solid #f5c6cb;
                border-radius: 6px;
                color: #721c24;
            `;
            
            const form = document.getElementById('createUserForm');
            form.parentNode.insertBefore(errorSummary, form);
        }
        
        const errors = document.querySelectorAll('.is-invalid');
        if (errors.length === 0) {
            errorSummary.style.display = 'none';
            return;
        }
        
        errorSummary.innerHTML = `
            <h4 style="margin-top: 0; margin-bottom: 10px;">
                <i class="fas fa-exclamation-triangle"></i>
                Please fix the following errors:
            </h4>
            <ul style="margin: 0; padding-left: 20px;">
                ${Array.from(errors).map(input => {
                    const label = input.parentNode.querySelector('label')?.textContent || 'Field';
                    const error = input.parentNode.querySelector('.error-feedback')?.textContent || 'Invalid';
                    return `<li><strong>${label}:</strong> ${error}</li>`;
                }).join('')}
            </ul>
        `;
        errorSummary.style.display = 'block';
        
        // Auto-hide after 10 seconds
        setTimeout(() => {
            errorSummary.style.display = 'none';
        }, 10000);
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
                right: 10px;
                top: 50%;
                transform: translateY(-50%);
                color: #dc3545;
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
    
    // Add password visibility toggle
    function setupPasswordVisibility() {
        const passwordInputs = document.querySelectorAll('input[type="password"]');
        
        passwordInputs.forEach(input => {
            const toggleBtn = document.createElement('button');
            toggleBtn.type = 'button';
            toggleBtn.className = 'password-toggle';
            toggleBtn.innerHTML = '<i class="fas fa-eye"></i>';
            toggleBtn.style.cssText = `
                position: absolute;
                right: 35px;
                top: 50%;
                transform: translateY(-50%);
                background: none;
                border: none;
                color: #6c757d;
                cursor: pointer;
                padding: 5px;
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
    
    // Initialize additional features
    setupPasswordVisibility();
    
    // Add form auto-save (localStorage)
    function setupAutoSave() {
        const form = document.getElementById('createUserForm');
        const inputs = form.querySelectorAll('input, select');
        const saveKey = 'create_user_draft';
        
        // Load saved data
        const savedData = JSON.parse(localStorage.getItem(saveKey) || '{}');
        Object.keys(savedData).forEach(key => {
            const input = form.querySelector(`[name="${key}"]`);
            if (input) {
                input.value = savedData[key];
                input.dispatchEvent(new Event('input'));
            }
        });
        
        // Save on input
        inputs.forEach(input => {
            input.addEventListener('input', debounce(function() {
                const formData = {};
                inputs.forEach(i => {
                    if (i.name) formData[i.name] = i.value;
                });
                localStorage.setItem(saveKey, JSON.stringify(formData));
            }, 500));
        });
        
        // Clear on successful submission
        form.addEventListener('submit', function() {
            localStorage.removeItem(saveKey);
        });
    }
    
    // Debounce utility
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
    
    // Initialize auto-save
    setupAutoSave();
});