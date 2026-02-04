// app/static/js/reports_list.js
document.addEventListener('DOMContentLoaded', function() {
    // Initialize reports list
    initializeReportsList();
    
    function initializeReportsList() {
        setupReportFilters();
        setupReportSorting();
        setupReportAnimations();
        setupEmptyState();
    }
    
    // Setup report filtering (if filters are added in the future)
    function setupReportFilters() {
        // This can be expanded when filters are added to the UI
        const filterButtons = document.querySelectorAll('.filter-btn');
        
        filterButtons.forEach(button => {
            button.addEventListener('click', function() {
                filterButtons.forEach(btn => btn.classList.remove('active'));
                this.classList.add('active');
                
                const filterValue = this.dataset.filter;
                filterReports(filterValue);
            });
        });
    }
    
    function filterReports(filter) {
        const reportCards = document.querySelectorAll('.report-card');
        let visibleCount = 0;
        
        reportCards.forEach(card => {
            const shouldShow = filter === 'all' || card.dataset.category === filter;
            
            if (shouldShow) {
                card.style.display = 'block';
                visibleCount++;
                
                // Add animation for showing
                setTimeout(() => {
                    card.style.opacity = '1';
                    card.style.transform = 'translateY(0)';
                }, 10);
            } else {
                card.style.opacity = '0';
                card.style.transform = 'translateY(10px)';
                
                setTimeout(() => {
                    card.style.display = 'none';
                }, 300);
            }
        });
        
        // Show empty state if no reports visible
        const emptyState = document.querySelector('.empty-state');
        if (emptyState) {
            if (visibleCount === 0) {
                emptyState.style.display = 'block';
                setTimeout(() => {
                    emptyState.style.opacity = '1';
                    emptyState.style.transform = 'translateY(0)';
                }, 10);
            } else {
                emptyState.style.opacity = '0';
                emptyState.style.transform = 'translateY(20px)';
                setTimeout(() => {
                    emptyState.style.display = 'none';
                }, 300);
            }
        }
    }
    
    // Setup report sorting
    function setupReportSorting() {
        const sortSelect = document.querySelector('#sortReports');
        if (sortSelect) {
            sortSelect.addEventListener('change', function() {
                const sortBy = this.value;
                sortReports(sortBy);
            });
        }
    }
    
    function sortReports(sortBy) {
        const reportsGrid = document.querySelector('.reports-grid');
        if (!reportsGrid) return;
        
        const reportCards = Array.from(reportsGrid.querySelectorAll('.report-card'));
        
        reportCards.sort((a, b) => {
            let aValue, bValue;
            
            switch (sortBy) {
                case 'date-desc':
                    aValue = getReportDate(a);
                    bValue = getReportDate(b);
                    return bValue - aValue;
                    
                case 'date-asc':
                    aValue = getReportDate(a);
                    bValue = getReportDate(b);
                    return aValue - bValue;
                    
                case 'amount-desc':
                    aValue = getReportAmount(a);
                    bValue = getReportAmount(b);
                    return bValue - aValue;
                    
                case 'amount-asc':
                    aValue = getReportAmount(a);
                    bValue = getReportAmount(b);
                    return aValue - bValue;
                    
                default:
                    return 0;
            }
        });
        
        // Reorder the grid
        reportCards.forEach((card, index) => {
            card.style.order = index;
            card.style.animationDelay = `${index * 0.05}s`;
            
            // Trigger reflow for animation
            card.style.animation = 'none';
            setTimeout(() => {
                card.style.animation = '';
            }, 10);
        });
    }
    
    function getReportDate(card) {
        const dateElement = card.querySelector('.report-date');
        if (dateElement) {
            const dateText = dateElement.textContent.trim();
            return new Date(dateText).getTime() || 0;
        }
        return 0;
    }
    
    function getReportAmount(card) {
        const amountElement = card.querySelector('.stat-value');
        if (amountElement) {
            const amountText = amountElement.textContent.trim();
            const amount = parseFloat(amountText.replace(/[^0-9.]/g, ''));
            return isNaN(amount) ? 0 : amount;
        }
        return 0;
    }
    
    // Setup report animations
    function setupReportAnimations() {
        const reportCards = document.querySelectorAll('.report-card');
        
        reportCards.forEach((card, index) => {
            // Staggered animation
            card.style.animationDelay = `${index * 0.1}s`;
            
            // Hover effect
            card.addEventListener('mouseenter', function() {
                this.style.transform = 'translateY(-5px)';
            });
            
            card.addEventListener('mouseleave', function() {
                this.style.transform = 'translateY(0)';
            });
            
            // Click effect
            card.addEventListener('click', function(e) {
                if (!e.target.closest('a') && !e.target.closest('button')) {
                    const previewLink = this.querySelector('a[href*="preview"]');
                    if (previewLink) {
                        previewLink.click();
                    }
                }
            });
        });
    }
    
    // Setup empty state
    function setupEmptyState() {
        const emptyState = document.querySelector('.empty-state');
        if (emptyState) {
            // Add animation to empty state icon
            const icon = emptyState.querySelector('i');
            if (icon) {
                icon.style.animation = 'pulse 2s infinite';
                
                // Add CSS for pulse animation if not already added
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
        }
    }
    
    // Handle report downloads
    const downloadButtons = document.querySelectorAll('.btn-primary');
    
    downloadButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            if (this.href.includes('download')) {
                // Show loading state
                const originalHTML = this.innerHTML;
                this.innerHTML = `
                    <i class="fas fa-spinner fa-spin"></i>
                    <span>Downloading...</span>
                `;
                this.disabled = true;
                
                // Reset after 5 seconds
                setTimeout(() => {
                    this.innerHTML = originalHTML;
                    this.disabled = false;
                }, 5000);
            }
        });
    });
});