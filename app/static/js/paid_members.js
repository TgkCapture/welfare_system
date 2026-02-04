// app/static/js/paid_members.js
document.addEventListener('DOMContentLoaded', function() {
    // Initialize paid members page
    initializePaidMembers();
    
    function initializePaidMembers() {
        setupTableInteractions();
        setupPrintReceipts();
        setupExportFunctionality();
        setupEmptyState();
    }
    
    // Setup table interactions
    function setupTableInteractions() {
        const tableRows = document.querySelectorAll('tbody tr');
        
        tableRows.forEach(row => {
            // Hover effect
            row.addEventListener('mouseenter', function() {
                this.style.backgroundColor = 'var(--bg-color)';
            });
            
            row.addEventListener('mouseleave', function() {
                this.style.backgroundColor = '';
            });
            
            // Click to select row
            row.addEventListener('click', function(e) {
                if (!e.target.closest('button') && !e.target.closest('a')) {
                    this.classList.toggle('selected');
                }
            });
        });
        
        // Add CSS for selected rows
        const rowSelectionStyle = document.createElement('style');
        rowSelectionStyle.textContent = `
            tbody tr.selected {
                background-color: rgba(37, 99, 235, 0.1) !important;
                border-left: 3px solid var(--primary-color);
            }
            
            tbody tr.selected:hover {
                background-color: rgba(37, 99, 235, 0.15) !important;
            }
        `;
        document.head.appendChild(rowSelectionStyle);
    }
    
    // Setup print receipt functionality
    function setupPrintReceipts() {
        const printButtons = document.querySelectorAll('.btn-outline[onclick*="print"]');
        
        printButtons.forEach(button => {
            button.addEventListener('click', function(e) {
                e.preventDefault();
                
                const row = this.closest('tr');
                const memberName = row.cells[1].textContent.trim();
                const amount = row.cells[2].querySelector('.amount-badge').textContent.trim();
                
                // Generate receipt content
                const receiptContent = generateReceipt(memberName, amount);
                
                // Open print dialog
                printReceipt(receiptContent);
            });
        });
    }
    
    function generateReceipt(name, amount) {
        const currentDate = new Date().toLocaleDateString('en-US', {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });
        
        const currentTime = new Date().toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit'
        });
        
        return `
            <!DOCTYPE html>
            <html>
            <head>
                <title>Payment Receipt - ${name}</title>
                <style>
                    body {
                        font-family: Arial, sans-serif;
                        line-height: 1.6;
                        max-width: 400px;
                        margin: 0 auto;
                        padding: 20px;
                    }
                    .receipt-header {
                        text-align: center;
                        margin-bottom: 30px;
                        border-bottom: 2px solid #333;
                        padding-bottom: 15px;
                    }
                    .receipt-header h1 {
                        margin: 0;
                        color: #2563eb;
                    }
                    .receipt-details {
                        margin-bottom: 20px;
                    }
                    .receipt-details div {
                        display: flex;
                        justify-content: space-between;
                        margin-bottom: 8px;
                    }
                    .receipt-details strong {
                        color: #333;
                    }
                    .receipt-footer {
                        margin-top: 30px;
                        padding-top: 15px;
                        border-top: 1px dashed #ccc;
                        text-align: center;
                        font-size: 12px;
                        color: #666;
                    }
                    @media print {
                        body {
                            padding: 0;
                        }
                        .no-print {
                            display: none;
                        }
                    }
                </style>
            </head>
            <body>
                <div class="receipt-header">
                    <h1>Mzugoss Welfare</h1>
                    <p>Payment Receipt</p>
                </div>
                
                <div class="receipt-details">
                    <div>
                        <strong>Member Name:</strong>
                        <span>${name}</span>
                    </div>
                    <div>
                        <strong>Amount Paid:</strong>
                        <span>${amount}</span>
                    </div>
                    <div>
                        <strong>Payment Date:</strong>
                        <span>${currentDate}</span>
                    </div>
                    <div>
                        <strong>Payment Time:</strong>
                        <span>${currentTime}</span>
                    </div>
                    <div>
                        <strong>Payment Status:</strong>
                        <span style="color: #10b981; font-weight: bold;">COMPLETED</span>
                    </div>
                </div>
                
                <div class="receipt-footer">
                    <p>Thank you for your contribution to the Mzugoss Welfare Fund.</p>
                    <p>This is an auto-generated receipt. No signature required.</p>
                </div>
                
                <div class="no-print" style="text-align: center; margin-top: 20px;">
                    <button onclick="window.print()" style="
                        background: #2563eb;
                        color: white;
                        border: none;
                        padding: 10px 20px;
                        border-radius: 5px;
                        cursor: pointer;
                    ">
                        Print Receipt
                    </button>
                </div>
            </body>
            </html>
        `;
    }
    
    function printReceipt(content) {
        const printWindow = window.open('', '_blank');
        printWindow.document.write(content);
        printWindow.document.close();
        
        // Auto-print after content loads
        printWindow.onload = function() {
            printWindow.print();
        };
    }
    
    // Setup export functionality
    function setupExportFunctionality() {
        const downloadImageBtn = document.querySelector('a[href*="download_paid_members"]');
        if (downloadImageBtn) {
            downloadImageBtn.addEventListener('click', function(e) {
                // Show loading state
                const originalHTML = this.innerHTML;
                this.innerHTML = `
                    <i class="fas fa-spinner fa-spin"></i>
                    <span>Generating Image...</span>
                `;
                this.classList.add('loading');
                
                // Reset after 3 seconds
                setTimeout(() => {
                    this.innerHTML = originalHTML;
                    this.classList.remove('loading');
                }, 3000);
            });
        }
    }
    
    // Setup empty state
    function setupEmptyState() {
        const emptyState = document.querySelector('.empty-state');
        if (emptyState) {
            // Add animation to icon
            const icon = emptyState.querySelector('i');
            if (icon) {
                icon.style.animation = 'float 3s ease-in-out infinite';
                
                // Add CSS for float animation
                if (!document.getElementById('float-animation')) {
                    const style = document.createElement('style');
                    style.id = 'float-animation';
                    style.textContent = `
                        @keyframes float {
                            0%, 100% { transform: translateY(0); }
                            50% { transform: translateY(-10px); }
                        }
                    `;
                    document.head.appendChild(style);
                }
            }
        }
    }
    
    // Add loading state CSS
    const loadingStyle = document.createElement('style');
    loadingStyle.textContent = `
        .loading {
            opacity: 0.7;
            cursor: wait !important;
        }
        
        .loading:hover {
            transform: none !important;
        }
    `;
    document.head.appendChild(loadingStyle);
});