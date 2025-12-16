// static/js/welfare_rules.js

// ==================== UTILITY FUNCTIONS ====================

// Show loading overlay
function showLoadingOverlay(message = 'Loading...') {
    // Remove existing overlay if any
    hideLoadingOverlay();
    
    const overlay = document.createElement('div');
    overlay.id = 'loadingOverlay';
    overlay.className = 'loading-overlay';
    overlay.innerHTML = `
        <div class="loading-spinner"></div>
        <div class="loading-text">${message}</div>
    `;
    
    document.body.appendChild(overlay);
}

// Hide loading overlay
function hideLoadingOverlay() {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        overlay.remove();
    }
}

// Set button loading state
function setButtonLoading(button, isLoading) {
    if (isLoading) {
        button.classList.add('loading');
        button.setAttribute('disabled', 'disabled');
        
        // Store original HTML
        if (!button.dataset.originalHtml) {
            button.dataset.originalHtml = button.innerHTML;
        }
        
        // Add spinner
        button.innerHTML = `
            <i class="fas fa-spinner fa-spin"></i>
            <span>Generating PDF...</span>
        `;
    } else {
        button.classList.remove('loading');
        button.removeAttribute('disabled');
        
        // Restore original HTML
        if (button.dataset.originalHtml) {
            button.innerHTML = button.dataset.originalHtml;
        }
    }
}

// Show toast notification
function showToast(message, type = 'info') {
    // Check if a global toast function exists (from another source, not this file)
    if (typeof window.displayToast === 'function') {
        window.displayToast(message, type);
        return;
    }
    
    // Check for toastr library
    if (typeof window.toastr !== 'undefined') {
        switch (type) {
            case 'success': toastr.success(message); break;
            case 'error': toastr.error(message); break;
            case 'warning': toastr.warning(message); break;
            default: toastr.info(message);
        }
        return;
    }
    
    // Check for SweetAlert
    if (typeof Swal !== 'undefined') {
        Swal.fire({
            icon: type,
            title: message,
            toast: true,
            position: 'top-end',
            showConfirmButton: false,
            timer: 3000,
            timerProgressBar: true,
        });
        return;
    }
    
    // Fallback: Create simple toast
    console.log(`${type}: ${message}`);
    
    // Remove existing simple toasts
    document.querySelectorAll('.simple-toast').forEach(toast => toast.remove());
    
    const toast = document.createElement('div');
    toast.className = `simple-toast toast-${type}`;
    toast.textContent = message;
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 20px;
        background: ${type === 'success' ? '#10b981' : 
                    type === 'error' ? '#ef4444' : 
                    type === 'warning' ? '#f59e0b' : '#3b82f6'};
        color: white;
        border-radius: 4px;
        z-index: 10000;
        font-size: 14px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        animation: slideIn 0.3s ease;
    `;
    
    // Add animation styles if not already added
    if (!document.getElementById('toast-animations')) {
        const style = document.createElement('style');
        style.id = 'toast-animations';
        style.textContent = `
            @keyframes slideIn {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            @keyframes slideOut {
                from { transform: translateX(0); opacity: 1; }
                to { transform: translateX(100%); opacity: 0; }
            }
        `;
        document.head.appendChild(style);
    }
    
    document.body.appendChild(toast);
    
    // Remove after 3 seconds
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }, 3000);
}

// ==================== CORE FUNCTIONALITY ====================

// Print functionality
function printRules() {
    showToast('Preparing document for printing...', 'info');
    
    setTimeout(() => {
        window.print();
    }, 500);
}

// Download PDF functionality with improved feedback
function downloadRulesPDF(event) {
    if (event) {
        event.preventDefault();
    }
    
    const button = event?.target?.closest('[data-action="pdf"]') || 
                   document.querySelector('[data-action="pdf"]');
    
    if (button) {
        setButtonLoading(button, true);
    }
    
    showLoadingOverlay('Generating PDF document...');
    
    // Get the correct PDF download URL
    let pdfUrl;
    const currentPath = window.location.pathname;
    
    if (currentPath.includes('/welfare-rules')) {
        pdfUrl = currentPath + '/pdf';
    } else if (currentPath.includes('/rules')) {
        pdfUrl = currentPath.replace('/rules', '/welfare-rules/pdf');
    } else {
        pdfUrl = '/welfare-rules/pdf';
    }
    
    // Add timestamp to prevent caching
    pdfUrl += '?_=' + Date.now();
    
    // Create hidden iframe for download
    const iframe = document.createElement('iframe');
    iframe.style.display = 'none';
    iframe.style.position = 'absolute';
    iframe.style.left = '-9999px';
    iframe.id = 'pdfDownloadFrame';
    
    // Handle load event
    iframe.onload = function() {
        setTimeout(() => {
            hideLoadingOverlay();
            
            if (button) {
                setButtonLoading(button, false);
            }
            
            // Check for errors
            try {
                const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
                const bodyContent = iframeDoc.body.innerText || iframeDoc.body.textContent;
                
                if (bodyContent.includes('Error') || 
                    bodyContent.includes('Failed') || 
                    bodyContent.includes('exception')) {
                    showToast('PDF generation failed. Please try again or use HTML download.', 'error');
                } else {
                    showToast('PDF download started! Check your downloads folder.', 'success');
                }
            } catch (e) {
                // Cross-origin restrictions - assume success
                showToast('PDF download started! Check your downloads folder.', 'success');
            }
            
            // Clean up iframe after delay
            setTimeout(() => {
                if (iframe.parentNode) {
                    iframe.parentNode.removeChild(iframe);
                }
            }, 5000);
        }, 1000);
    };
    
    // Handle error event
    iframe.onerror = function() {
        hideLoadingOverlay();
        
        if (button) {
            setButtonLoading(button, false);
        }
        
        showToast('Failed to load PDF. The server might be busy. Please try again.', 'error');
        
        if (iframe.parentNode) {
            iframe.parentNode.removeChild(iframe);
        }
    };
    
    // Set iframe source
    iframe.src = pdfUrl;
    document.body.appendChild(iframe);
    
    // Timeout fallback
    setTimeout(() => {
        if (document.body.contains(iframe)) {
            hideLoadingOverlay();
            
            if (button) {
                setButtonLoading(button, false);
            }
            
            // Try alternative method
            showToast('Using alternative download method...', 'info');
            setTimeout(() => downloadRulesPDFAlternative(pdfUrl), 500);
            
            if (iframe.parentNode) {
                iframe.parentNode.removeChild(iframe);
            }
        }
    }, 15000); // 15 second timeout
}

// Alternative PDF download method using fetch
async function downloadRulesPDFAlternative(pdfUrl) {
    showLoadingOverlay('Trying alternative download method...');
    
    try {
        const response = await fetch(pdfUrl, {
            method: 'GET',
            credentials: 'same-origin',
            headers: {
                'Accept': 'application/pdf',
                'Cache-Control': 'no-cache'
            }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const blob = await response.blob();
        
        // Check if it's actually a PDF
        if (!blob.type.includes('pdf') && blob.size < 100) {
            // Might be an error page
            const text = await blob.text();
            if (text.includes('Error') || text.includes('Failed')) {
                throw new Error('Server returned error page');
            }
        }
        
        // Create download link
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'mzugoss_welfare_rules_v2.pdf';
        a.style.display = 'none';
        
        document.body.appendChild(a);
        a.click();
        
        // Cleanup
        setTimeout(() => {
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        }, 100);
        
        hideLoadingOverlay();
        showToast('PDF downloaded successfully!', 'success');
        
    } catch (error) {
        console.error('Alternative PDF download failed:', error);
        hideLoadingOverlay();
        showToast('Unable to download PDF. Please try the HTML version instead.', 'error');
        
        // Show HTML download option
        setTimeout(() => {
            if (confirm('PDF download failed. Would you like to download the HTML version instead?')) {
                downloadRulesHTML();
            }
        }, 500);
    }
}

// Download HTML version
function downloadRulesHTML(event) {
    if (event) {
        event.preventDefault();
    }
    
    showToast('Preparing HTML document...', 'info');
    
    let htmlUrl;
    const currentPath = window.location.pathname;
    
    if (currentPath.includes('/welfare-rules')) {
        htmlUrl = currentPath + '/html-download';
    } else if (currentPath.includes('/rules')) {
        htmlUrl = currentPath.replace('/rules', '/welfare-rules/html-download');
    } else {
        htmlUrl = '/welfare-rules/html-download';
    }
    
    // Add timestamp
    htmlUrl += '?_=' + Date.now();
    
    // Open in new window/tab
    const newWindow = window.open(htmlUrl, '_blank');
    
    // Check if popup was blocked
    setTimeout(() => {
        if (!newWindow || newWindow.closed || typeof newWindow.closed === 'undefined') {
            showToast('Popup was blocked. Please allow pop-ups for downloads.', 'warning');
            
            // Alternative: Create download link
            const a = document.createElement('a');
            a.href = htmlUrl;
            a.download = 'mzugoss_welfare_rules.html';
            a.style.display = 'none';
            document.body.appendChild(a);
            a.click();
            setTimeout(() => {
                document.body.removeChild(a);
            }, 100);
        }
    }, 1000);
}

// ==================== SHARE FUNCTIONALITY ====================

// Share functionality
function shareRules(event) {
    if (event) {
        event.preventDefault();
    }
    
    const modal = document.getElementById('shareModal');
    if (modal) {
        modal.style.display = 'block';
        modal.classList.add('active');
        
        // Update share link
        const shareLinkInput = document.getElementById('shareLink');
        if (shareLinkInput && !shareLinkInput.value) {
            shareLinkInput.value = window.location.href;
        }
    }
}

function closeShareModal() {
    const modal = document.getElementById('shareModal');
    if (modal) {
        modal.style.display = 'none';
        modal.classList.remove('active');
    }
}

// Share via WhatsApp
function shareViaWhatsApp(event) {
    if (event) event.preventDefault();
    
    const text = "Mzugoss Welfare Rules v2.0 - Check out our updated community welfare rules and contribution system";
    const shareLink = document.getElementById('shareLink');
    const url = shareLink ? shareLink.value : window.location.href;
    const whatsappUrl = `https://wa.me/?text=${encodeURIComponent(text + ' ' + url)}`;
    
    window.open(whatsappUrl, '_blank', 'noopener,noreferrer');
    closeShareModal();
    showToast('Opening WhatsApp...', 'success');
}

// Share via Email
function shareViaEmail(event) {
    if (event) event.preventDefault();
    
    const subject = "Updated: Mzugoss Welfare Rules & Guidelines v2.0";
    const shareLink = document.getElementById('shareLink');
    const url = shareLink ? shareLink.value : window.location.href;
    
    const body = `Hello,

I wanted to share the updated Mzugoss Welfare Rules with you. These outline our community's contribution system and benefits:

${url}

Updated Support Amounts:
- Monthly Contribution: K1,000
- Funeral Support: K50,000
- Wedding Support: K80,000  
- Sickness Support: K15,000
- Member Death Support: K80,000 (NEW)

When a contributing member passes away, their family receives K80,000 in support.

Please review the full updated rules at the link above.

Best regards`;
    
    const mailtoUrl = `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    window.location.href = mailtoUrl;
    closeShareModal();
}

// Share via SMS
function shareViaSMS(event) {
    if (event) event.preventDefault();
    
    const shareLink = document.getElementById('shareLink');
    const url = shareLink ? shareLink.value : window.location.href;
    const text = `Mzugoss Welfare Rules v2.0: ${url} - Monthly: K1000, Funeral: K50000, Wedding: K80000, Sickness: K15000, Member Death: K80000`;
    const smsUrl = `sms:?body=${encodeURIComponent(text)}`;
    
    window.location.href = smsUrl;
    closeShareModal();
}

// Share via Twitter
function shareViaTwitter(event) {
    if (event) event.preventDefault();
    
    const text = "Updated Mzugoss Welfare Rules v2.0! New: Member Death Support K80,000. Wedding: K80,000 | Funeral: K50,000 | Sickness: K15,000";
    const shareLink = document.getElementById('shareLink');
    const url = shareLink ? shareLink.value : window.location.href;
    const twitterUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${encodeURIComponent(url)}`;
    
    window.open(twitterUrl, '_blank', 'noopener,noreferrer');
    closeShareModal();
    showToast('Opening Twitter...', 'success');
}

// Share via Facebook
function shareViaFacebook(event) {
    if (event) event.preventDefault();
    
    const shareLink = document.getElementById('shareLink');
    const url = shareLink ? shareLink.value : window.location.href;
    const facebookUrl = `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}`;
    
    window.open(facebookUrl, '_blank', 'noopener,noreferrer');
    closeShareModal();
    showToast('Opening Facebook...', 'success');
}

// Copy share link
function copyShareLink(event) {
    if (event) event.preventDefault();
    
    const shareLink = document.getElementById('shareLink');
    if (!shareLink) return;
    
    shareLink.select();
    shareLink.setSelectionRange(0, 99999);
    
    // Try modern clipboard API first
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(shareLink.value)
            .then(() => {
                showToast('Link copied to clipboard!', 'success');
            })
            .catch(err => {
                // Fallback to execCommand
                fallbackCopyText(shareLink.value);
            });
    } else {
        // Fallback for older browsers
        fallbackCopyText(shareLink.value);
    }
}

// Fallback copy function
function fallbackCopyText(text) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.opacity = '0';
    textArea.style.left = '-9999px';
    document.body.appendChild(textArea);
    
    try {
        textArea.select();
        const successful = document.execCommand('copy');
        
        if (successful) {
            showToast('Link copied to clipboard!', 'success');
        } else {
            showToast('Failed to copy link. Please copy manually.', 'error');
        }
    } catch (err) {
        showToast('Failed to copy link. Please copy manually.', 'error');
    } finally {
        document.body.removeChild(textArea);
    }
}

// ==================== EVENT HANDLERS ====================

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // Ctrl+P or Cmd+P for print
    if ((e.ctrlKey || e.metaKey) && e.key === 'p') {
        e.preventDefault();
        printRules();
        return false;
    }
    
    // Escape to close modal
    if (e.key === 'Escape') {
        closeShareModal();
        return false;
    }
    
    // Ctrl+S or Cmd+S to save/share
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        shareRules();
        return false;
    }
    
    // Ctrl+D or Cmd+D to download PDF
    if ((e.ctrlKey || e.metaKey) && e.key === 'd') {
        e.preventDefault();
        downloadRulesPDF();
        return false;
    }
});

// Close modal when clicking outside
document.addEventListener('click', function(event) {
    const modal = document.getElementById('shareModal');
    if (modal && event.target === modal) {
        closeShareModal();
    }
});

// ==================== INITIALIZATION ====================

// Initialize functionality when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('Welfare Rules JS initialized');
    
    // Add CSS for loading overlay
    const loadingStyles = document.createElement('style');
    loadingStyles.textContent = `
        .loading-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.8);
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            z-index: 9999;
            color: white;
            font-family: Arial, sans-serif;
        }
        
        .loading-spinner {
            border: 4px solid rgba(255, 255, 255, 0.3);
            border-top: 4px solid white;
            border-radius: 50%;
            width: 50px;
            height: 50px;
            animation: spin 1s linear infinite;
            margin-bottom: 20px;
        }
        
        .loading-text {
            font-size: 18px;
            text-align: center;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .btn-action.loading {
            opacity: 0.7;
            cursor: not-allowed;
        }
        
        .btn-action.loading i:not(.fa-spinner) {
            display: none;
        }
        
        .fa-spin {
            animation: spin 1s linear infinite;
        }
    `;
    document.head.appendChild(loadingStyles);
    
    // Initialize share link input
    const shareLinkInput = document.getElementById('shareLink');
    if (shareLinkInput && !shareLinkInput.value) {
        shareLinkInput.value = window.location.href;
    }
    
    // Set up action button handlers
    const actionHandlers = {
        'print': printRules,
        'pdf': downloadRulesPDF,
        'html': downloadRulesHTML,
        'share': shareRules
    };
    
    document.querySelectorAll('[data-action]').forEach(button => {
        const action = button.getAttribute('data-action');
        if (actionHandlers[action]) {
            button.addEventListener('click', actionHandlers[action]);
        }
    });
    
    // Set up share button handlers
    const shareHandlers = {
        'whatsapp': shareViaWhatsApp,
        'email': shareViaEmail,
        'copy': copyShareLink,
        'sms': shareViaSMS,
        'twitter': shareViaTwitter,
        'facebook': shareViaFacebook
    };
    
    document.querySelectorAll('[data-share]').forEach(button => {
        const shareType = button.getAttribute('data-share');
        if (shareHandlers[shareType]) {
            button.addEventListener('click', shareHandlers[shareType]);
        }
    });
    
    // Remove old onclick handlers and replace with event listeners
    document.querySelectorAll('[onclick]').forEach(element => {
        const onclick = element.getAttribute('onclick');
        
        if (onclick.includes('printRules()')) {
            element.setAttribute('data-action', 'print');
            element.removeAttribute('onclick');
            element.addEventListener('click', printRules);
        }
        else if (onclick.includes('downloadRulesPDF()')) {
            element.setAttribute('data-action', 'pdf');
            element.removeAttribute('onclick');
            element.addEventListener('click', downloadRulesPDF);
        }
        else if (onclick.includes('downloadRulesHTML()')) {
            element.setAttribute('data-action', 'html');
            element.removeAttribute('onclick');
            element.addEventListener('click', downloadRulesHTML);
        }
        else if (onclick.includes('shareRules()')) {
            element.setAttribute('data-action', 'share');
            element.removeAttribute('onclick');
            element.addEventListener('click', shareRules);
        }
        else if (onclick.includes('shareViaWhatsApp()')) {
            element.setAttribute('data-share', 'whatsapp');
            element.removeAttribute('onclick');
            element.addEventListener('click', shareViaWhatsApp);
        }
        else if (onclick.includes('shareViaEmail()')) {
            element.setAttribute('data-share', 'email');
            element.removeAttribute('onclick');
            element.addEventListener('click', shareViaEmail);
        }
        else if (onclick.includes('copyShareLink()')) {
            element.setAttribute('data-share', 'copy');
            element.removeAttribute('onclick');
            element.addEventListener('click', copyShareLink);
        }
        else if (onclick.includes('shareViaSMS()')) {
            element.setAttribute('data-share', 'sms');
            element.removeAttribute('onclick');
            element.addEventListener('click', shareViaSMS);
        }
        else if (onclick.includes('shareViaTwitter()')) {
            element.setAttribute('data-share', 'twitter');
            element.removeAttribute('onclick');
            element.addEventListener('click', shareViaTwitter);
        }
        else if (onclick.includes('shareViaFacebook()')) {
            element.setAttribute('data-share', 'facebook');
            element.removeAttribute('onclick');
            element.addEventListener('click', shareViaFacebook);
        }
    });
    
    // Modal close button
    const modalCloseBtn = document.querySelector('.modal-close');
    if (modalCloseBtn) {
        modalCloseBtn.addEventListener('click', closeShareModal);
    }
    
    // Copy button in modal
    const copyBtn = document.querySelector('.btn-copy');
    if (copyBtn) {
        copyBtn.addEventListener('click', copyShareLink);
    }
    
    // Initialize tooltips
    initializeTooltips();
});

// Initialize tooltips
function initializeTooltips() {
    const tooltips = document.querySelectorAll('[title]');
    tooltips.forEach(element => {
        element.addEventListener('mouseenter', showTooltip);
        element.addEventListener('mouseleave', hideTooltip);
    });
}

function showTooltip(e) {
    const tooltip = document.createElement('div');
    tooltip.className = 'custom-tooltip';
    tooltip.textContent = e.target.title;
    tooltip.style.cssText = `
        position: absolute;
        background: rgba(0,0,0,0.8);
        color: white;
        padding: 5px 10px;
        border-radius: 4px;
        font-size: 12px;
        z-index: 10000;
        white-space: nowrap;
        pointer-events: none;
    `;
    
    document.body.appendChild(tooltip);
    
    const rect = e.target.getBoundingClientRect();
    tooltip.style.left = rect.left + 'px';
    tooltip.style.top = (rect.top - tooltip.offsetHeight - 6) + 'px';

    // Store actual element (not string)
    e.target._tooltipEl = tooltip;
}

function hideTooltip(e) {
    const tooltip = e.target._tooltipEl;
    if (tooltip && tooltip.parentNode) {
        tooltip.parentNode.removeChild(tooltip);
        e.target._tooltipEl = null;
    }
}


// Make functions available globally
window.welfareRules = {
    showToast,
    printRules,
    downloadRulesPDF,
    downloadRulesHTML,
    shareRules,
    closeShareModal,
    shareViaWhatsApp,
    shareViaEmail,
    shareViaSMS,
    shareViaTwitter,
    shareViaFacebook,
    copyShareLink
};