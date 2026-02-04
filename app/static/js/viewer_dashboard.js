// app/static/js/viewer_dashboard.js
document.addEventListener('DOMContentLoaded', function() {
    // Initialize viewer dashboard
    initializeViewerDashboard();
    
    function initializeViewerDashboard() {
        setupReportInteractions();
        setupPlaceholderAnimations();
        setupEmptyState();
    }
    
    // Setup report card interactions
    function setupReportInteractions() {
        const reportCards = document.querySelectorAll('.report-card, .report-item');
        
        reportCards.forEach(card => {
            card.addEventListener('click', function(e) {
                // Only trigger if not clicking on a button or link
                if (!e.target.closest('a') && !e.target.closest('button')) {
                    const previewLink = this.querySelector('a[href*="preview"]');
                    if (previewLink) {
                        previewLink.click();
                    }
                }
            });
            
            // Add hover effect
            card.addEventListener('mouseenter', function() {
                this.style.transform = 'translateY(-2px)';
            });
            
            card.addEventListener('mouseleave', function() {
                this.style.transform = 'translateY(0)';
            });
        });
    }
    
    // Setup placeholder animations
    function setupPlaceholderAnimations() {
        const placeholderStats = document.querySelectorAll('.placeholder-stat');
        
        placeholderStats.forEach((stat, index) => {
            // Add staggered animation
            stat.style.animationDelay = `${index * 0.2}s`;
            
            // Simulate loading animation
            const valueElement = stat.querySelector('.placeholder-value');
            if (valueElement) {
                simulateLoading(valueElement);
            }
        });
    }
    
    function simulateLoading(element) {
        let count = 0;
        const target = parseInt(element.textContent) || 0;
        const increment = target / 20;
        
        const interval = setInterval(() => {
            count += increment;
            if (count >= target) {
                count = target;
                clearInterval(interval);
            }
            element.textContent = Math.floor(count);
        }, 50);
    }
    
    // Setup empty state
    function setupEmptyState() {
        const emptyStates = document.querySelectorAll('.empty-state');
        
        emptyStates.forEach(state => {
            // Add pulse animation to icon
            const icon = state.querySelector('i');
            if (icon) {
                icon.style.animation = 'pulse 2s infinite';
                
                // Add CSS for pulse animation
                if (!document.getElementById('pulse-animation')) {
                    const style = document.createElement('style');
                    style.id = 'pulse-animation';
                    style.textContent = `
                        @keyframes pulse {
                            0% { transform: scale(1); opacity: 0.7; }
                            50% { transform: scale(1.1); opacity: 1; }
                            100% { transform: scale(1); opacity: 0.7; }
                        }
                    `;
                    document.head.appendChild(style);
                }
            }
        });
    }
    
    // Handle report downloads with progress indication
    const downloadLinks = document.querySelectorAll('a[href*="download"]');
    
    downloadLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            if (this.getAttribute('disabled')) {
                e.preventDefault();
                return false;
            }
            
            // Show download progress
            const originalHTML = this.innerHTML;
            this.innerHTML = `
                <i class="fas fa-spinner fa-spin"></i>
                <span>Downloading...</span>
            `;
            this.classList.add('downloading');
            
            // Reset after 5 seconds (in case download fails)
            setTimeout(() => {
                this.innerHTML = originalHTML;
                this.classList.remove('downloading');
            }, 5000);
        });
    });
    
    // Add CSS for downloading state
    const downloadStyle = document.createElement('style');
    downloadStyle.textContent = `
        .downloading {
            opacity: 0.7;
            cursor: wait !important;
        }
        
        .downloading:hover {
            transform: none !important;
        }
    `;
    document.head.appendChild(downloadStyle);
});