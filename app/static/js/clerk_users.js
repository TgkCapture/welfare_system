// app/static/js/clerk_users.js

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    const tooltipTriggers = document.querySelectorAll('[title]');
    tooltipTriggers.forEach(trigger => {
        trigger.addEventListener('mouseenter', function(e) {
            const title = this.getAttribute('title');
            if (title) {
                const tooltip = document.createElement('div');
                tooltip.className = 'custom-tooltip';
                tooltip.textContent = title;
                document.body.appendChild(tooltip);
                
                const rect = this.getBoundingClientRect();
                tooltip.style.top = (rect.top - tooltip.offsetHeight - 10) + 'px';
                tooltip.style.left = (rect.left + (rect.width / 2) - (tooltip.offsetWidth / 2)) + 'px';
                
                this.setAttribute('data-original-title', title);
                this.removeAttribute('title');
            }
        });
        
        trigger.addEventListener('mouseleave', function() {
            const originalTitle = this.getAttribute('data-original-title');
            if (originalTitle) {
                this.setAttribute('title', originalTitle);
                this.removeAttribute('data-original-title');
            }
            
            const tooltip = document.querySelector('.custom-tooltip');
            if (tooltip) {
                tooltip.remove();
            }
        });
    });

    // Add CSS for custom tooltips
    const tooltipStyles = document.createElement('style');
    tooltipStyles.textContent = `
        .custom-tooltip {
            position: fixed;
            background: rgba(0, 0, 0, 0.8);
            color: white;
            padding: 8px 12px;
            border-radius: 4px;
            font-size: 0.85rem;
            z-index: 9999;
            pointer-events: none;
            white-space: nowrap;
            transform: translateY(-5px);
            opacity: 0;
            animation: fadeIn 0.2s ease forwards;
        }
        
        @keyframes fadeIn {
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
    `;
    document.head.appendChild(tooltipStyles);

    // Handle form submissions with confirmation
    const toggleForms = document.querySelectorAll('.inline-form');
    toggleForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const button = this.querySelector('button');
            const action = button.getAttribute('title') || 'perform this action';
            
            if (!confirm(`Are you sure you want to ${action}?`)) {
                e.preventDefault();
                return false;
            }
            
            // Show loading state
            const originalHTML = button.innerHTML;
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            button.disabled = true;
            
            // Revert after 3 seconds if submission fails
            setTimeout(() => {
                if (button.disabled) {
                    button.innerHTML = originalHTML;
                    button.disabled = false;
                }
            }, 3000);
        });
    });

    // Add row highlight on hover effect
    const tableRows = document.querySelectorAll('.users-table tbody tr');
    tableRows.forEach(row => {
        row.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-2px)';
            this.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.1)';
            this.style.transition = 'all 0.2s ease';
        });
        
        row.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
            this.style.boxShadow = 'none';
        });
    });

    // Filter functionality (if needed in future)
    function setupFilter() {
        const filterInput = document.createElement('input');
        filterInput.type = 'text';
        filterInput.placeholder = 'Filter by email or status...';
        filterInput.className = 'filter-input';
        
        const filterContainer = document.createElement('div');
        filterContainer.className = 'filter-container';
        filterContainer.style.marginBottom = '20px';
        filterContainer.appendChild(filterInput);
        
        const contentCard = document.querySelector('.content-card');
        if (contentCard) {
            contentCard.insertBefore(filterContainer, contentCard.firstChild);
            
            filterInput.addEventListener('input', function() {
                const searchTerm = this.value.toLowerCase();
                const rows = document.querySelectorAll('.users-table tbody tr');
                
                rows.forEach(row => {
                    const email = row.querySelector('td:first-child strong').textContent.toLowerCase();
                    const status = row.querySelector('.status-badge').textContent.toLowerCase();
                    
                    if (email.includes(searchTerm) || status.includes(searchTerm)) {
                        row.style.display = '';
                    } else {
                        row.style.display = 'none';
                    }
                });
            });
        }
    }

    // Initialize filter if there are more than 5 users
    const userCount = document.querySelectorAll('.users-table tbody tr').length;
    if (userCount > 5) {
        setupFilter();
        
        // Add styles for filter
        const filterStyles = document.createElement('style');
        filterStyles.textContent = `
            .filter-container {
                padding: 15px;
                border-bottom: 1px solid #e9ecef;
            }
            
            .filter-input {
                width: 100%;
                padding: 10px 15px;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                font-size: 1rem;
                transition: border-color 0.2s;
            }
            
            .filter-input:focus {
                outline: none;
                border-color: #3498db;
                box-shadow: 0 0 0 3px rgba(52, 152, 219, 0.1);
            }
        `;
        document.head.appendChild(filterStyles);
    }

    // Status badge animation
    const statusBadges = document.querySelectorAll('.status-badge');
    statusBadges.forEach(badge => {
        badge.addEventListener('click', function() {
            if (this.classList.contains('active')) {
                this.style.transform = 'scale(1.05)';
                setTimeout(() => {
                    this.style.transform = 'scale(1)';
                }, 200);
            }
        });
    });

    // Export functionality (optional future feature)
    function setupExportButton() {
        const exportBtn = document.createElement('button');
        exportBtn.className = 'btn btn-outline';
        exportBtn.innerHTML = '<i class="fas fa-download"></i> Export List';
        exportBtn.style.marginLeft = '10px';
        
        exportBtn.addEventListener('click', function() {
            // In a real implementation, this would make an API call
            // For now, just show a message
            alert('Export feature coming soon!');
        });
        
        const pageActions = document.querySelector('.page-actions');
        if (pageActions) {
            pageActions.appendChild(exportBtn);
        }
    }

    // Check if we should show export button (for larger datasets)
    if (userCount > 10) {
        setupExportButton();
    }

    // Add animation to empty state
    const emptyState = document.querySelector('.empty-state');
    if (emptyState) {
        emptyState.style.opacity = '0';
        emptyState.style.transform = 'translateY(20px)';
        
        setTimeout(() => {
            emptyState.style.transition = 'all 0.5s ease';
            emptyState.style.opacity = '1';
            emptyState.style.transform = 'translateY(0)';
        }, 100);
    }

    // Initialize table rows animation
    setTimeout(() => {
        tableRows.forEach((row, index) => {
            row.style.opacity = '0';
            row.style.transform = 'translateX(-20px)';
            
            setTimeout(() => {
                row.style.transition = 'all 0.3s ease';
                row.style.opacity = '1';
                row.style.transform = 'translateX(0)';
            }, index * 50);
        });
    }, 200);

    // Handle window resize
    let resizeTimer;
    window.addEventListener('resize', function() {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(function() {
            // Adjust table responsiveness
            const tableContainer = document.querySelector('.users-table-container');
            if (tableContainer && window.innerWidth < 768) {
                tableContainer.style.overflowX = 'scroll';
            }
        }, 250);
    });
});