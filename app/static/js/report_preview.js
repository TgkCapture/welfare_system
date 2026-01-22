// app/static/js/report_preview.js
document.addEventListener('DOMContentLoaded', function() {
    // Initialize report preview
    initializeReportPreview();
    
    function initializeReportPreview() {
        setupCardAnimations();
        setupDownloadProgress();
        setupCopyToClipboard();
        setupPrintFunctionality();
    }
    
    // Setup staggered card animations
    function setupCardAnimations() {
        const cards = document.querySelectorAll('.summary-card, .action-card');
        
        cards.forEach((card, index) => {
            card.style.animationDelay = `${index * 0.1}s`;
            
            // Add hover effect
            card.addEventListener('mouseenter', function() {
                this.style.transform = 'translateY(-5px)';
            });
            
            card.addEventListener('mouseleave', function() {
                this.style.transform = 'translateY(0)';
            });
        });
    }
    
    // Setup download progress indicators
    function setupDownloadProgress() {
        const downloadLinks = document.querySelectorAll('.action-card[href*="download"]');
        
        downloadLinks.forEach(link => {
            link.addEventListener('click', function(e) {
                // Only handle if it's a download link
                if (this.href.includes('download')) {
                    e.preventDefault();
                    
                    const originalHTML = this.innerHTML;
                    const href = this.href;
                    
                    // Show loading state
                    this.innerHTML = `
                        <div class="action-icon">
                            <i class="fas fa-spinner fa-spin"></i>
                        </div>
                        <div class="action-content">
                            <h3>Preparing Download...</h3>
                            <p>Please wait while we prepare your file</p>
                        </div>
                        <div class="action-arrow">
                            <i class="fas fa-spinner fa-spin"></i>
                        </div>
                    `;
                    
                    this.classList.add('downloading');
                    
                    // Simulate download preparation
                    setTimeout(() => {
                        // Create invisible iframe for download
                        const iframe = document.createElement('iframe');
                        iframe.style.display = 'none';
                        iframe.src = href;
                        document.body.appendChild(iframe);
                        
                        // Reset button after download starts
                        setTimeout(() => {
                            this.innerHTML = originalHTML;
                            this.classList.remove('downloading');
                            document.body.removeChild(iframe);
                        }, 1000);
                    }, 1500);
                }
            });
        });
    }
    
    // Setup copy to clipboard for report details
    function setupCopyToClipboard() {
        const detailItems = document.querySelectorAll('.detail-item');
        
        detailItems.forEach(item => {
            item.style.cursor = 'pointer';
            item.title = 'Click to copy';
            
            item.addEventListener('click', function() {
                const valueElement = this.querySelector('.detail-value');
                if (valueElement) {
                    const textToCopy = valueElement.textContent.trim();
                    
                    // Use modern clipboard API
                    if (navigator.clipboard && window.isSecureContext) {
                        navigator.clipboard.writeText(textToCopy)
                            .then(() => {
                                showToast('Copied to clipboard!', 'success');
                            })
                            .catch(err => {
                                console.error('Failed to copy: ', err);
                                showToast('Failed to copy to clipboard', 'error');
                            });
                    } else {
                        // Fallback for older browsers
                        const textArea = document.createElement('textarea');
                        textArea.value = textToCopy;
                        textArea.style.position = 'fixed';
                        textArea.style.left = '-999999px';
                        textArea.style.top = '-999999px';
                        document.body.appendChild(textArea);
                        textArea.focus();
                        textArea.select();
                        
                        try {
                            document.execCommand('copy');
                            showToast('Copied to clipboard!', 'success');
                        } catch (err) {
                            console.error('Failed to copy: ', err);
                            showToast('Failed to copy to clipboard', 'error');
                        }
                        
                        document.body.removeChild(textArea);
                    }
                }
            });
            
            // Add hover effect
            item.addEventListener('mouseenter', function() {
                this.style.backgroundColor = 'var(--bg-color)';
            });
            
            item.addEventListener('mouseleave', function() {
                this.style.backgroundColor = '';
            });
        });
    }
    
    // Setup print functionality
    function setupPrintFunctionality() {
        // Check if we're in print preview mode
        if (window.matchMedia) {
            const mediaQueryList = window.matchMedia('print');
            mediaQueryList.addListener((mql) => {
                if (mql.matches) {
                    // Before print
                    document.body.classList.add('printing');
                } else {
                    // After print
                    setTimeout(() => {
                        document.body.classList.remove('printing');
                    }, 500);
                }
            });
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
    
    // Add print styles dynamically
    const printStyles = document.createElement('style');
    printStyles.textContent = `
        @media print {
            .main-header,
            .main-footer,
            .mobile-nav-overlay,
            .user-dropdown,
            .alert {
                display: none !important;
            }
            
            .main-content {
                padding: 0 !important;
            }
            
            .report-preview-container {
                box-shadow: none !important;
                border: none !important;
            }
            
            .action-card {
                break-inside: avoid;
            }
            
            body {
                background: white !important;
                color: black !important;
            }
            
            a {
                color: black !important;
                text-decoration: none !important;
            }
            
            .btn {
                display: none !important;
            }
        }
    `;
    document.head.appendChild(printStyles);
});