// app/static/js/dashboard.js
document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const fileUploadToggle = document.getElementById('file_upload_toggle');
    const sheetsToggle = document.getElementById('sheets_toggle');
    const fileUploadSection = document.getElementById('file_upload_section');
    const sheetsSection = document.getElementById('sheets_section');
    const fileInput = document.getElementById('file-upload');
    const dropArea = document.getElementById('dropArea');
    const uploadPlaceholder = document.getElementById('uploadPlaceholder');
    const filePreview = document.getElementById('filePreview');
    const fileName = document.getElementById('fileName');
    const fileSize = document.getElementById('fileSize');
    const removeFile = document.getElementById('removeFile');
    const sheetUrlInput = document.getElementById('sheet_url');
    const submitBtn = document.getElementById('submitBtn');
    const yearSelect = document.getElementById('year');
    const monthSelect = document.getElementById('month');
    const selectedMonthYear = document.getElementById('selectedMonthYear');
    const uploadForm = document.getElementById('uploadForm');

    // Month names for display
    const monthNames = ['January', 'February', 'March', 'April', 'May', 'June', 
                       'July', 'August', 'September', 'October', 'November', 'December'];

    // Update month/year display
    function updateDateDisplay() {
        if (yearSelect && monthSelect && selectedMonthYear) {
            const selectedMonth = monthNames[parseInt(monthSelect.value) - 1];
            selectedMonthYear.textContent = `${selectedMonth} ${yearSelect.value}`;
        }
    }

    if (yearSelect && monthSelect && selectedMonthYear) {
        yearSelect.addEventListener('change', updateDateDisplay);
        monthSelect.addEventListener('change', updateDateDisplay);
        updateDateDisplay(); // Initial call
    }

    // Toggle between file upload and Google Sheets
    function toggleInputMethod() {
        if (!fileUploadToggle || !sheetsToggle) return;
        
        const useSheets = sheetsToggle.checked;
        
        if (useSheets) {
            fileUploadSection.classList.remove('active');
            sheetsSection.classList.add('active');
            
            // Remove required from file input and disable it
            if (fileInput) {
                fileInput.removeAttribute('required');
                fileInput.setAttribute('disabled', 'disabled'); 
            }
            
            // Enable and add required to sheet URL input
            if (sheetUrlInput) {
                sheetUrlInput.removeAttribute('disabled');
                sheetUrlInput.setAttribute('required', 'required');
            }
        } else {
            fileUploadSection.classList.add('active');
            sheetsSection.classList.remove('active');
            
            // Enable and add required to file input
            if (fileInput) {
                fileInput.removeAttribute('disabled');
                fileInput.setAttribute('required', 'required');
            }
            
            // Remove required from sheet URL input and disable it
            if (sheetUrlInput) {
                sheetUrlInput.removeAttribute('required');
                sheetUrlInput.setAttribute('disabled', 'disabled'); 
            }
        }
    }

    if (fileUploadToggle && sheetsToggle) {
        fileUploadToggle.addEventListener('change', toggleInputMethod);
        sheetsToggle.addEventListener('change', toggleInputMethod);
        toggleInputMethod(); // Initial call
    }

    // File upload drag and drop functionality
    if (dropArea) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropArea.addEventListener(eventName, preventDefaults, false);
        });

        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }

        ['dragenter', 'dragover'].forEach(eventName => {
            dropArea.addEventListener(eventName, highlight, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropArea.addEventListener(eventName, unhighlight, false);
        });

        function highlight() {
            if (!sheetsToggle || !sheetsToggle.checked) {
                dropArea.classList.add('highlight');
            }
        }

        function unhighlight() {
            dropArea.classList.remove('highlight');
        }

        // Handle dropped files
        dropArea.addEventListener('drop', handleDrop, false);

        function handleDrop(e) {
            if (sheetsToggle && sheetsToggle.checked) return;
            
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                handleFile(files[0]);
            }
        }

        // Handle file selection
        if (fileInput) {
            fileInput.addEventListener('change', function() {
                if (this.files.length > 0) {
                    handleFile(this.files[0]);
                }
            });
        }

        function handleFile(file) {
            const validTypes = [
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'application/vnd.ms-excel'
            ];
            const validExtensions = ['.xlsx', '.xls'];
            
            const isValidType = validTypes.includes(file.type);
            const isValidExtension = validExtensions.some(ext => 
                file.name.toLowerCase().endsWith(ext)
            );
            
            if (isValidType || isValidExtension) {
                // Show file preview
                fileName.textContent = file.name;
                fileSize.textContent = formatFileSize(file.size);
                uploadPlaceholder.style.display = 'none';
                filePreview.style.display = 'flex';
                
                // Update file input
                const dataTransfer = new DataTransfer();
                dataTransfer.items.add(file);
                fileInput.files = dataTransfer.files;
            } else {
                showAlert('Please select a valid Excel file (.xlsx, .xls)', 'error');
                resetFileInput();
            }
        }

        // Remove file
        if (removeFile) {
            removeFile.addEventListener('click', function(e) {
                e.preventDefault();
                resetFileInput();
            });
        }

        function resetFileInput() {
            if (fileInput) {
                fileInput.value = '';
                // Clear the file list
                const dataTransfer = new DataTransfer();
                fileInput.files = dataTransfer.files;
            }
            uploadPlaceholder.style.display = 'flex';
            filePreview.style.display = 'none';
        }
    }

    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    // Form submission
    if (uploadForm) {
        uploadForm.addEventListener('submit', function(e) {
            // Prevent default browser validation
            e.preventDefault();
            
            let isValid = true;
            let errorMessage = '';
            
            if (sheetsToggle && sheetsToggle.checked) {
                // Google Sheets validation
                if (!sheetUrlInput || !sheetUrlInput.value.trim()) {
                    isValid = false;
                    errorMessage = 'Please enter a Google Sheets URL';
                } else if (!isValidGoogleSheetsUrl(sheetUrlInput.value.trim())) {
                    isValid = false;
                    errorMessage = 'Please enter a valid Google Sheets URL';
                }
                
                // Clear file input if using sheets
                if (fileInput) {
                    fileInput.value = '';
                }
            } else {
                // File upload validation
                if (!fileInput || fileInput.files.length === 0) {
                    isValid = false;
                    errorMessage = 'Please select an Excel file';
                } else {
                    const file = fileInput.files[0];
                    const validExtensions = ['.xlsx', '.xls'];
                    const isValidExtension = validExtensions.some(ext => 
                        file.name.toLowerCase().endsWith(ext)
                    );
                    
                    if (!isValidExtension) {
                        isValid = false;
                        errorMessage = 'Please select a valid Excel file (.xlsx, .xls)';
                    }
                }
                
                // Clear sheet URL if using file upload
                if (sheetUrlInput) {
                    sheetUrlInput.value = '';
                }
            }
            
            if (!isValid) {
                showAlert(errorMessage, 'error');
                return false;
            }
            
            // Show loading state
            if (submitBtn) {
                submitBtn.disabled = true;
                const btnText = submitBtn.querySelector('.btn-text');
                const btnLoading = submitBtn.querySelector('.btn-loading');
                if (btnText) btnText.style.display = 'none';
                if (btnLoading) btnLoading.style.display = 'flex';
            }
            
            // Submit the form
            this.submit();
        });
    }

    // Google Sheets URL validation helper
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

    // Show alert/toast notification
    function showAlert(message, type = 'info') {
        // Remove existing toasts
        const existingToasts = document.querySelectorAll('.toast');
        existingToasts.forEach(toast => {
            if (toast.parentNode) {
                document.body.removeChild(toast);
            }
        });
        
        // Create toast element
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <div class="toast-content">
                <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
                <span>${message}</span>
            </div>
            <button class="toast-close">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        document.body.appendChild(toast);
        
        // Show toast
        setTimeout(() => {
            toast.classList.add('show');
        }, 10);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => {
                if (toast.parentNode) {
                    document.body.removeChild(toast);
                }
            }, 300);
        }, 5000);
        
        // Close button
        const closeBtn = toast.querySelector('.toast-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                toast.classList.remove('show');
                setTimeout(() => {
                    if (toast.parentNode) {
                        document.body.removeChild(toast);
                    }
                }, 300);
            });
        }
    }

    // Add toast styles dynamically
    if (!document.getElementById('toast-styles')) {
        const style = document.createElement('style');
        style.id = 'toast-styles';
        style.textContent = `
            .toast {
                position: fixed;
                top: 20px;
                right: 20px;
                padding: 1rem 1.5rem;
                border-radius: var(--radius-lg);
                background: white;
                box-shadow: var(--shadow-lg);
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 1rem;
                z-index: 10000;
                transform: translateX(120%);
                transition: transform 0.3s ease;
                max-width: 400px;
            }
            
            .toast.show {
                transform: translateX(0);
            }
            
            .toast-success {
                border-left: 4px solid var(--success-color);
                background: linear-gradient(135deg, #f0fdf4, #dcfce7);
            }
            
            .toast-error {
                border-left: 4px solid var(--danger-color);
                background: linear-gradient(135deg, #fef2f2, #fee2e2);
            }
            
            .toast-info {
                border-left: 4px solid var(--info-color);
                background: linear-gradient(135deg, #f0f9ff, #e0f2fe);
            }
            
            .toast-content {
                display: flex;
                align-items: center;
                gap: 0.75rem;
                flex: 1;
            }
            
            .toast-content i {
                font-size: 1.25rem;
            }
            
            .toast-success .toast-content i {
                color: var(--success-color);
            }
            
            .toast-error .toast-content i {
                color: var(--danger-color);
            }
            
            .toast-info .toast-content i {
                color: var(--info-color);
            }
            
            .toast-close {
                background: none;
                border: none;
                color: var(--text-light);
                cursor: pointer;
                padding: 0.25rem;
                border-radius: var(--radius-sm);
                transition: var(--transition);
            }
            
            .toast-close:hover {
                background: rgba(0, 0, 0, 0.1);
                color: var(--text-primary);
            }
        `;
        document.head.appendChild(style);
    }
});