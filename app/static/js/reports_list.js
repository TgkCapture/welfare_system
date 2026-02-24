// app/static/js/reports_list.js
document.addEventListener('DOMContentLoaded', function() {
    initializeReportsList();
    
    function initializeReportsList() {
        setupReportFilters();
        setupReportActions();
        setupReportAnimations();
        setupEmptyState();
        setupAdminControls();
        setupKeyboardShortcuts();
    }
    
    // Filter functionality
    function setupReportFilters() {
        const yearFilter = document.getElementById('yearFilter');
        const monthFilter = document.getElementById('monthFilter');
        const statusFilter = document.getElementById('statusFilter');
        const reportCards = document.querySelectorAll('.report-card');
        
        function applyFilters() {
            const selectedYear = yearFilter ? yearFilter.value : '';
            const selectedMonth = monthFilter ? monthFilter.value : '';
            const selectedStatus = statusFilter ? statusFilter.value : '';
            
            let visibleCount = 0;
            
            reportCards.forEach(card => {
                const year = card.getAttribute('data-year');
                const month = card.getAttribute('data-month');
                const isArchived = card.getAttribute('data-archived') === 'true';
                
                let show = true;
                
                if (selectedYear && year !== selectedYear) {
                    show = false;
                }
                
                if (selectedMonth && month !== selectedMonth) {
                    show = false;
                }
                
                if (selectedStatus === 'active' && isArchived) {
                    show = false;
                }
                
                if (selectedStatus === 'archived' && !isArchived) {
                    show = false;
                }
                
                if (show) {
                    card.style.display = 'flex';
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
            
            updateEmptyState(visibleCount);
        }
        
        // Add event listeners
        if (yearFilter) yearFilter.addEventListener('change', applyFilters);
        if (monthFilter) monthFilter.addEventListener('change', applyFilters);
        if (statusFilter) statusFilter.addEventListener('change', applyFilters);
        
        // Initialize filters
        applyFilters();
    }
    
    // Report actions (download, archive, etc.)
    function setupReportActions() {
        // Download buttons
        const downloadButtons = document.querySelectorAll('.btn-primary[href*="download"]');
        downloadButtons.forEach(button => {
            button.addEventListener('click', function(e) {
                const isArchiveLink = this.href.includes('archive');
                const isDeleteLink = this.href.includes('delete');
                
                if (isArchiveLink || isDeleteLink) {
                    // Handled by setupAdminControls
                    return;
                }
                
                // Show loading state for download
                const originalHTML = this.innerHTML;
                this.innerHTML = `
                    <i class="fas fa-spinner fa-spin"></i>
                    <span>Preparing...</span>
                `;
                this.disabled = true;
                
                // Reset after 5 seconds (in case download fails)
                setTimeout(() => {
                    this.innerHTML = originalHTML;
                    this.disabled = false;
                }, 5000);
            });
        });
        
        // Preview cards click
        const reportCards = document.querySelectorAll('.report-card');
        reportCards.forEach(card => {
            card.addEventListener('click', function(e) {
                // Don't trigger if clicking on buttons or links
                if (e.target.closest('a') || e.target.closest('button') || e.target.closest('.dropdown')) {
                    return;
                }
                
                const previewLink = this.querySelector('a[href*="preview"]');
                if (previewLink) {
                    previewLink.click();
                }
            });
        });
    }
    
    // Report animations
    function setupReportAnimations() {
        const reportCards = document.querySelectorAll('.report-card');
        
        reportCards.forEach((card, index) => {
            // Staggered animation
            card.style.animationDelay = `${index * 0.1}s`;
            
            // Hover effect
            card.addEventListener('mouseenter', function() {
                if (this.style.display !== 'none') {
                    this.style.transform = 'translateY(-5px)';
                    this.style.boxShadow = '0 10px 25px rgba(0, 0, 0, 0.1)';
                }
            });
            
            card.addEventListener('mouseleave', function() {
                if (this.style.display !== 'none') {
                    this.style.transform = 'translateY(0)';
                    this.style.boxShadow = '';
                }
            });
        });
    }
    
    // Empty state management
    function setupEmptyState() {
        const emptyState = document.querySelector('.empty-state');
        if (emptyState) {
            // Add animation to empty state icon
            const icon = emptyState.querySelector('i');
            if (icon) {
                icon.style.animation = 'pulse 2s infinite';
            }
        }
    }
    
    function updateEmptyState(visibleCount) {
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
    
    // Admin controls functionality
    function setupAdminControls() {
        // Archive confirmation
        const archiveLinks = document.querySelectorAll('a[href*="archive"]');
        archiveLinks.forEach(link => {
            link.addEventListener('click', function(e) {
                if (!confirm('Are you sure you want to archive this report?\n\nArchived reports are not visible to viewers but can be restored by admins.')) {
                    e.preventDefault();
                } else {
                    showLoadingState(this);
                }
            });
        });
        
        // Regenerate confirmation
        const regenerateLinks = document.querySelectorAll('a[href*="regenerate"]');
        regenerateLinks.forEach(link => {
            link.addEventListener('click', function(e) {
                if (!confirm('Regenerate this report?\n\nA new copy will be created with current date.')) {
                    e.preventDefault();
                } else {
                    showLoadingState(this);
                }
            });
        });
        
        // Cleanup confirmation
        const cleanupLinks = document.querySelectorAll('a[href*="cleanup"]');
        cleanupLinks.forEach(link => {
            link.addEventListener('click', function(e) {
                if (!confirm('Clean up old reports?\n\nThis will permanently delete files older than the retention period.\n\nThis action cannot be undone.')) {
                    e.preventDefault();
                } else {
                    showLoadingState(this);
                }
            });
        });
        
        function showLoadingState(element) {
            const originalHTML = element.innerHTML;
            element.innerHTML = `<i class="fas fa-spinner fa-spin"></i>`;
            element.style.pointerEvents = 'none';
            
            // Reset after 5 seconds (in case something goes wrong)
            setTimeout(() => {
                element.innerHTML = originalHTML;
                element.style.pointerEvents = '';
            }, 5000);
        }
    }
    
    // Keyboard shortcuts
    function setupKeyboardShortcuts() {
        document.addEventListener('keydown', function(e) {
            // Ctrl/Cmd + F to focus filter
            if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
                e.preventDefault();
                const yearFilter = document.getElementById('yearFilter');
                if (yearFilter) {
                    yearFilter.focus();
                }
            }
            
            // Escape to clear filters
            if (e.key === 'Escape') {
                const yearFilter = document.getElementById('yearFilter');
                const monthFilter = document.getElementById('monthFilter');
                const statusFilter = document.getElementById('statusFilter');
                
                if (yearFilter) yearFilter.value = '';
                if (monthFilter) monthFilter.value = '';
                if (statusFilter) statusFilter.value = '';
                
                // Trigger filter change
                if (yearFilter) yearFilter.dispatchEvent(new Event('change'));
            }
        });
    }
    
    // Search functionality (if search input is added)
    const searchInput = document.getElementById('reportSearch');
    if (searchInput) {
        searchInput.addEventListener('input', debounce(function() {
            const searchTerm = this.value.toLowerCase();
            const reportCards = document.querySelectorAll('.report-card');
            
            let visibleCount = 0;
            
            reportCards.forEach(card => {
                const cardText = card.textContent.toLowerCase();
                
                if (cardText.includes(searchTerm)) {
                    card.style.display = 'flex';
                    visibleCount++;
                } else {
                    card.style.display = 'none';
                }
            });
            
            updateEmptyState(visibleCount);
        }, 300));
    }
    
    // Utility: Debounce function
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
    
    // Add CSS for animations if not already added
    if (!document.getElementById('reports-animations')) {
        const style = document.createElement('style');
        style.id = 'reports-animations';
        style.textContent = `
            @keyframes pulse {
                0% { transform: scale(1); opacity: 0.7; }
                50% { transform: scale(1.1); opacity: 1; }
                100% { transform: scale(1); opacity: 0.7; }
            }
            
            .empty-state {
                animation: fadeIn 0.5s ease;
                transition: all 0.3s ease;
            }
            
            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(20px); }
                to { opacity: 1; transform: translateY(0); }
            }
            
            .fa-spinner {
                animation: spin 1s linear infinite;
            }
            
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
        `;
        document.head.appendChild(style);
    }
});