// app/static/js/welfare_rules.js
document.addEventListener('DOMContentLoaded', function() {
    // Initialize any required functionality
    initWelfareRules();
});

function initWelfareRules() {
    // Setup event listeners for share modal
    setupModalListeners();
    
    // Setup keyboard shortcuts
    setupKeyboardShortcuts();
    
    // Setup toast notifications if not already available
    if (typeof window.showToast === 'undefined') {
        setupToastNotifications();
    }
}

// Print functionality
function printRules() {
    // Show loading feedback
    showToast('Preparing document for printing...', 'info');
    
    setTimeout(() => {
        window.print();
    }, 500);
}

// Download PDF functionality
function downloadRulesPDF() {
    // Show loading state
    showToast('Generating PDF document...', 'info');
    
    // Redirect to PDF download endpoint
    // This assumes you have a route named 'main.download_welfare_rules_pdf'
    const pdfUrl = document.querySelector('[data-pdf-url]')?.dataset.pdfUrl || 
                   '/download-welfare-rules-pdf';
    window.location.href = pdfUrl;
}

// Share functionality
function shareRules() {
    const modal = document.getElementById('shareModal');
    if (modal) {
        modal.style.display = 'block';
        document.body.style.overflow = 'hidden';
    }
}

function closeShareModal() {
    const modal = document.getElementById('shareModal');
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = '';
    }
}

// Setup modal event listeners
function setupModalListeners() {
    const modal = document.getElementById('shareModal');
    const closeBtn = document.querySelector('.modal-close');
    
    if (modal && closeBtn) {
        // Close modal when clicking outside
        modal.addEventListener('click', function(event) {
            if (event.target === modal) {
                closeShareModal();
            }
        });
        
        // Close modal with escape key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && modal.style.display === 'block') {
                closeShareModal();
            }
        });
    }
}

// Share via WhatsApp
function shareViaWhatsApp() {
    const text = "Mzugoss Welfare Rules & Guidelines - Check out our community welfare rules and contribution system";
    const url = window.location.href;
    const whatsappUrl = `https://wa.me/?text=${encodeURIComponent(text + ' ' + url)}`;
    window.open(whatsappUrl, '_blank');
    closeShareModal();
    showToast('Opening WhatsApp...', 'success');
}

// Share via Email
function shareViaEmail() {
    const subject = "Mzugoss Welfare Rules & Guidelines";
    const body = `Hello,

I wanted to share the updated Mzugoss Welfare Rules with you. These outline our community's contribution system and benefits:

${window.location.href}

Key Updated Points:
- Monthly Contribution: K1,000
- Funeral Support: K50,000
- Wedding Support: K80,000  
- Sickness Support: K15,000
- Member Death Support: K80,000

Please review the full rules at the link above.

Best regards`;
    
    const mailtoUrl = `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    window.location.href = mailtoUrl;
    closeShareModal();
}

// Share via SMS
function shareViaSMS() {
    const text = `Mzugoss Welfare Rules: ${window.location.href} - Monthly: K1000, Funeral: K50000, Wedding: K80000, Sickness: K15000, Member Death: K80000`;
    const smsUrl = `sms:?body=${encodeURIComponent(text)}`;
    window.location.href = smsUrl;
    closeShareModal();
}

// Copy share link
function copyShareLink() {
    const shareLink = document.getElementById('shareLink');
    if (!shareLink) return;
    
    shareLink.select();
    shareLink.setSelectionRange(0, 99999);
    
    try {
        navigator.clipboard.writeText(shareLink.value).then(() => {
            showToast('Link copied to clipboard!', 'success');
        }).catch(() => {
            // Fallback for older browsers
            document.execCommand('copy');
            showToast('Link copied to clipboard!', 'success');
        });
    } catch (err) {
        // Fallback for older browsers
        document.execCommand('copy');
        showToast('Link copied to clipboard!', 'success');
    }
}

// Setup keyboard shortcuts
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', function(e) {
        // Ctrl+P or Cmd+P for print
        if ((e.ctrlKey || e.metaKey) && e.key === 'p') {
            e.preventDefault();
            printRules();
        }
    });
}

// Toast notification system
function setupToastNotifications() {
    // Create toast container if it doesn't exist
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            display: flex;
            flex-direction: column;
            gap: 10px;
        `;
        document.body.appendChild(toastContainer);
    }
    
    // Define showToast globally
    window.showToast = function(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <div class="toast-content">
                <i class="fas fa-${getToastIcon(type)}"></i>
                <span>${message}</span>
            </div>
            <button class="toast-close">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        // Add CSS if not already added
        if (!document.getElementById('toast-styles')) {
            const style = document.createElement('style');
            style.id = 'toast-styles';
            style.textContent = `
                .toast {
                    padding: 1rem 1.5rem;
                    border-radius: var(--radius-lg);
                    background: white;
                    box-shadow: var(--shadow-lg);
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    gap: 1rem;
                    transform: translateX(120%);
                    transition: transform 0.3s ease;
                    max-width: 400px;
                    animation: slideIn 0.3s ease forwards;
                }
                
                @keyframes slideIn {
                    to {
                        transform: translateX(0);
                    }
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
        
        toastContainer.appendChild(toast);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            toast.style.animation = 'slideOut 0.3s ease forwards';
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 300);
        }, 5000);
        
        // Add slideOut animation if not defined
        if (!document.getElementById('slideOut-animation')) {
            const style = document.createElement('style');
            style.id = 'slideOut-animation';
            style.textContent = `
                @keyframes slideOut {
                    from {
                        transform: translateX(0);
                        opacity: 1;
                    }
                    to {
                        transform: translateX(120%);
                        opacity: 0;
                    }
                }
            `;
            document.head.appendChild(style);
        }
        
        // Close button
        const closeBtn = toast.querySelector('.toast-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                toast.style.animation = 'slideOut 0.3s ease forwards';
                setTimeout(() => {
                    if (toast.parentNode) {
                        toast.parentNode.removeChild(toast);
                    }
                }, 300);
            });
        }
        
        return toast;
    };
}

// Helper function to get toast icon
function getToastIcon(type) {
    switch(type) {
        case 'success': return 'check-circle';
        case 'error': return 'exclamation-circle';
        case 'warning': return 'exclamation-triangle';
        default: return 'info-circle';
    }
}

// Export functions for global use
window.printRules = printRules;
window.downloadRulesPDF = downloadRulesPDF;
window.shareRules = shareRules;
window.closeShareModal = closeShareModal;
window.shareViaWhatsApp = shareViaWhatsApp;
window.shareViaEmail = shareViaEmail;
window.shareViaSMS = shareViaSMS;
window.copyShareLink = copyShareLink;