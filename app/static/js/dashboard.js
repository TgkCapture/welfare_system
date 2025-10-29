// Dashboard specific functionality
document.addEventListener('DOMContentLoaded', function() {
    // Data source toggle
    const sourceFile = document.getElementById('sourceFile');
    const sourceSheets = document.getElementById('sourceSheets');
    const fileSection = document.getElementById('fileSection');
    const sheetsSection = document.getElementById('sheetsSection');

    function toggleDataSource() {
        if (sourceFile.checked) {
            fileSection.style.display = 'block';
            sheetsSection.style.display = 'none';
        } else {
            fileSection.style.display = 'none';
            sheetsSection.style.display = 'block';
        }
    }

    if (sourceFile && sourceSheets) {
        sourceFile.addEventListener('change', toggleDataSource);
        sourceSheets.addEventListener('change', toggleDataSource);
        toggleDataSource(); // Initialize
    }

    // File upload drag and drop
    const dropArea = document.getElementById('dropArea');
    const fileInput = document.getElementById('fileInput');
    const filePreview = document.getElementById('filePreview');

    if (dropArea && fileInput) {
        // Prevent default drag behaviors
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropArea.addEventListener(eventName, preventDefaults, false);
            document.body.addEventListener(eventName, preventDefaults, false);
        });

        // Highlight drop area when item is dragged over it
        ['dragenter', 'dragover'].forEach(eventName => {
            dropArea.addEventListener(eventName, highlight, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropArea.addEventListener(eventName, unhighlight, false);
        });

        // Handle dropped files
        dropArea.addEventListener('drop', handleDrop, false);

        // Handle file input change
        fileInput.addEventListener('change', handleFileSelect);
    }

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    function highlight() {
        dropArea.classList.add('dragover');
    }

    function unhighlight() {
        dropArea.classList.remove('dragover');
    }

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    }

    function handleFileSelect() {
        handleFiles(this.files);
    }

    function handleFiles(files) {
        if (files.length > 0) {
            const file = files[0];
            if (isExcelFile(file)) {
                showFilePreview(file);
            } else {
                showError('Please select a valid Excel file (.xlsx, .xls)');
                fileInput.value = '';
            }
        }
    }

    function isExcelFile(file) {
        const allowedTypes = [
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.ms-excel'
        ];
        const allowedExtensions = ['.xlsx', '.xls'];
        
        return allowedTypes.includes(file.type) || 
               allowedExtensions.some(ext => file.name.toLowerCase().endsWith(ext));
    }

    function showFilePreview(file) {
        filePreview.innerHTML = `
            <div class="file-preview-content">
                <i class="fas fa-file-excel text-success"></i>
                <div>
                    <strong>${file.name}</strong>
                    <br>
                    <small>${formatFileSize(file.size)}</small>
                </div>
            </div>
        `;
        filePreview.style.display = 'block';
    }

    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    function showError(message) {
        filePreview.innerHTML = `
            <div class="file-preview-content text-danger">
                <i class="fas fa-exclamation-triangle"></i>
                ${message}
            </div>
        `;
        filePreview.style.display = 'block';
        
        setTimeout(() => {
            filePreview.style.display = 'none';
        }, 3000);
    }

    // Initialize dashboard stats (placeholder - you'll replace with real data)
    initializeStats();
});

function initializeStats() {
    // Placeholder stats - replace with actual API calls
    document.getElementById('totalMembers').textContent = '50';
    document.getElementById('monthlyContributions').textContent = 'MWK 250K';
    document.getElementById('pendingContributions').textContent = '5';
    document.getElementById('totalBalance').textContent = 'MWK 5.2M';
    document.getElementById('lastSync').textContent = new Date().toLocaleString();
    document.getElementById('activeMembers').textContent = '45';
}