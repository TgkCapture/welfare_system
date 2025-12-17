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

    // Update month/year display
    function updateDateDisplay() {
        const monthNames = [
            'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'
        ];
        const selectedMonth = monthNames[parseInt(monthSelect.value) - 1];
        if (selectedMonthYear) {
            selectedMonthYear.textContent = `${selectedMonth} ${yearSelect.value}`;
        }
    }

    if (yearSelect && monthSelect && selectedMonthYear) {
        yearSelect.addEventListener('change', updateDateDisplay);
        monthSelect.addEventListener('change', updateDateDisplay);
        updateDateDisplay();
    }

    // Toggle between file upload and Google Sheets
    function toggleInputMethod() {
        const useSheets = sheetsToggle.checked;
        
        if (useSheets) {
            fileUploadSection.classList.remove('active');
            sheetsSection.classList.add('active');
            fileInput.removeAttribute('required');
            sheetUrlInput.setAttribute('required', 'required');
        } else {
            fileUploadSection.classList.add('active');
            sheetsSection.classList.remove('active');
            fileInput.setAttribute('required', 'required');
            sheetUrlInput.removeAttribute('required');
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
                showToast('Please select a valid Excel file (.xlsx, .xls)', 'error');
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
            if (fileInput) fileInput.value = '';
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
            if (sheetsToggle && sheetsToggle.checked && (!sheetUrlInput || !sheetUrlInput.value.trim())) {
                e.preventDefault();
                showToast('Please enter a Google Sheets URL', 'error');
                return;
            }

            if ((!sheetsToggle || !sheetsToggle.checked) && fileInput && fileInput.files.length === 0) {
                e.preventDefault();
                showToast('Please select an Excel file', 'error');
                return;
            }

            // Show loading state
            if (submitBtn) {
                submitBtn.disabled = true;
                const btnText = submitBtn.querySelector('.btn-text');
                const btnLoading = submitBtn.querySelector('.btn-loading');
                if (btnText) btnText.style.display = 'none';
                if (btnLoading) btnLoading.style.display = 'flex';
            }
        });
    }

    // Toast notification function
    function showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <div class="toast-content">
                <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
                <span>${message}</span>
            </div>
        `;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.classList.add('show');
        }, 10);
        
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => {
                document.body.removeChild(toast);
            }, 300);
        }, 3000);
    }
});