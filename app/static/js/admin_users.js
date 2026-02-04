// app/static/js/admin_users.js
document.addEventListener('DOMContentLoaded', function() {
    initializeUserManagement();
    
    function initializeUserManagement() {
        setupUserTable();
        setupDeleteModals();
        setupStatusToggle();
        setupSearchFilter();
        setupRoleFilter();
    }
    
    // Setup interactive user table
    function setupUserTable() {
        const table = document.querySelector('.users-table');
        if (!table) return;
        
        const rows = table.querySelectorAll('tbody tr');
        
        // Add hover effects
        rows.forEach(row => {
            row.addEventListener('mouseenter', function() {
                this.style.backgroundColor = 'var(--table-hover-bg, #f8f9fa)';
            });
            
            row.addEventListener('mouseleave', function() {
                this.style.backgroundColor = '';
            });
            
            // Add click to highlight (except on action buttons)
            row.addEventListener('click', function(e) {
                if (!e.target.closest('.action-buttons') && !e.target.closest('a')) {
                    rows.forEach(r => r.classList.remove('selected'));
                    this.classList.add('selected');
                }
            });
        });
        
        // Make table rows sortable
        const headers = table.querySelectorAll('thead th');
        headers.forEach((header, index) => {
            if (index !== headers.length - 1) { // Skip actions column
                header.style.cursor = 'pointer';
                header.addEventListener('click', () => sortTable(index));
            }
        });
        
        // Add keyboard navigation
        table.addEventListener('keydown', function(e) {
            const selected = table.querySelector('tr.selected');
            if (!selected) return;
            
            const rows = Array.from(table.querySelectorAll('tbody tr'));
            const currentIndex = rows.indexOf(selected);
            
            switch(e.key) {
                case 'ArrowUp':
                    e.preventDefault();
                    if (currentIndex > 0) {
                        rows[currentIndex].classList.remove('selected');
                        rows[currentIndex - 1].classList.add('selected');
                        rows[currentIndex - 1].scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }
                    break;
                case 'ArrowDown':
                    e.preventDefault();
                    if (currentIndex < rows.length - 1) {
                        rows[currentIndex].classList.remove('selected');
                        rows[currentIndex + 1].classList.add('selected');
                        rows[currentIndex + 1].scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }
                    break;
                case 'Enter':
                    e.preventDefault();
                    const editBtn = selected.querySelector('a[href*="edit"]');
                    if (editBtn) editBtn.click();
                    break;
                case 'Delete':
                    e.preventDefault();
                    const deleteBtn = selected.querySelector('.delete-user-btn');
                    if (deleteBtn) deleteBtn.click();
                    break;
            }
        });
    }
    
    // Sort table by column
    function sortTable(columnIndex) {
        const table = document.querySelector('.users-table');
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));
        
        // Determine sort direction
        const isAscending = !table.dataset.sortColumn || 
                           table.dataset.sortColumn !== columnIndex.toString() ||
                           table.dataset.sortDirection === 'desc';
        
        // Sort rows
        rows.sort((a, b) => {
            const aValue = getCellValue(a, columnIndex);
            const bValue = getCellValue(b, columnIndex);
            
            // Handle different data types
            if (columnIndex === 0) { // ID column
                return isAscending ? aValue - bValue : bValue - aValue;
            } else if (columnIndex === 3) { // Status column
                const statusOrder = { 'Active': 1, 'Inactive': 2 };
                return isAscending ? statusOrder[aValue] - statusOrder[bValue] : statusOrder[bValue] - statusOrder[aValue];
            } else if (columnIndex === 2) { // Role column
                const roleOrder = { 'Admin': 1, 'Clerk': 2, 'Viewer': 3 };
                return isAscending ? roleOrder[aValue] - roleOrder[bValue] : roleOrder[bValue] - roleOrder[aValue];
            } else {
                return isAscending ? aValue.localeCompare(bValue) : bValue.localeCompare(aValue);
            }
        });
        
        // Clear table body
        while (tbody.firstChild) {
            tbody.removeChild(tbody.firstChild);
        }
        
        // Re-add sorted rows
        rows.forEach(row => tbody.appendChild(row));
        
        // Update sort indicators
        updateSortIndicator(columnIndex, isAscending);
        table.dataset.sortColumn = columnIndex;
        table.dataset.sortDirection = isAscending ? 'asc' : 'desc';
    }
    
    function getCellValue(row, columnIndex) {
        const cell = row.children[columnIndex];
        if (columnIndex === 1) { // User info column
            return cell.querySelector('strong').textContent;
        } else if (columnIndex === 2 || columnIndex === 3) { // Role or status badges
            return cell.querySelector('.badge').textContent.trim();
        }
        return cell.textContent.trim();
    }
    
    function updateSortIndicator(columnIndex, isAscending) {
        const headers = document.querySelectorAll('.users-table th');
        headers.forEach(header => {
            header.classList.remove('sort-asc', 'sort-desc');
            const icon = header.querySelector('.sort-icon');
            if (icon) icon.remove();
        });
        
        const activeHeader = headers[columnIndex];
        activeHeader.classList.add(isAscending ? 'sort-asc' : 'sort-desc');
        
        const sortIcon = document.createElement('i');
        sortIcon.className = `fas fa-sort-${isAscending ? 'up' : 'down'} sort-icon`;
        activeHeader.appendChild(sortIcon);
    }
    
    // Setup delete user modals
    function setupDeleteModals() {
        const deleteButtons = document.querySelectorAll('.delete-user-btn');
        const modal = document.getElementById('deleteUserModal');
        
        if (!modal) return;
        
        const closeBtn = modal.querySelector('.close-modal');
        const cancelBtn = modal.querySelector('.cancel-delete');
        const deleteForm = document.getElementById('deleteUserForm');
        const deleteUserName = document.getElementById('deleteUserName');
        
        // Open modal when delete button is clicked
        deleteButtons.forEach(button => {
            button.addEventListener('click', function(e) {
                e.preventDefault();
                const userId = this.dataset.userId;
                const userEmail = this.dataset.userEmail;
                
                deleteUserName.textContent = userEmail;
                deleteForm.action = `/admin/delete-user/${userId}`;
                
                modal.classList.add('active');
                document.body.style.overflow = 'hidden';
            });
        });
        
        // Close modal functions
        function closeModal() {
            modal.classList.remove('active');
            document.body.style.overflow = '';
        }
        
        closeBtn.addEventListener('click', closeModal);
        cancelBtn.addEventListener('click', closeModal);
        
        // Close modal on outside click
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                closeModal();
            }
        });
        
        // Close on Escape key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && modal.classList.contains('active')) {
                closeModal();
            }
        });
    }
    
    // Setup status toggle confirmation
    function setupStatusToggle() {
        const toggleForms = document.querySelectorAll('.inline-form');
        
        toggleForms.forEach(form => {
            const button = form.querySelector('button[type="submit"]');
            
            button.addEventListener('click', function(e) {
                if (!confirm(`Are you sure you want to ${this.dataset.action || 'toggle'} this user's status?`)) {
                    e.preventDefault();
                }
            });
        });
    }
    
    // Setup search filter
    function setupSearchFilter() {
        const searchInput = document.createElement('input');
        searchInput.type = 'search';
        searchInput.placeholder = 'Search users...';
        searchInput.className = 'table-search';
        searchInput.style.cssText = `
            margin-bottom: 20px;
            padding: 10px 15px;
            width: 100%;
            max-width: 400px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
        `;
        
        const tableContainer = document.querySelector('.table-responsive');
        if (tableContainer) {
            tableContainer.parentNode.insertBefore(searchInput, tableContainer);
            
            searchInput.addEventListener('input', debounce(function(e) {
                filterTable(e.target.value);
            }, 300));
            
            // Add keyboard shortcut
            document.addEventListener('keydown', function(e) {
                if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
                    e.preventDefault();
                    searchInput.focus();
                    searchInput.select();
                }
            });
        }
    }
    
    function filterTable(searchTerm) {
        const table = document.querySelector('.users-table');
        if (!table) return;
        
        const rows = table.querySelectorAll('tbody tr');
        searchTerm = searchTerm.toLowerCase();
        
        rows.forEach(row => {
            const rowText = row.textContent.toLowerCase();
            const isVisible = rowText.includes(searchTerm);
            row.style.display = isVisible ? '' : 'none';
            
            // Highlight search term
            if (isVisible && searchTerm) {
                highlightSearchTerm(row, searchTerm);
            } else {
                removeHighlights(row);
            }
        });
        
        // Show/hide empty state
        const visibleRows = Array.from(rows).filter(row => row.style.display !== 'none');
        const emptyState = document.querySelector('.empty-state');
        if (emptyState) {
            emptyState.style.display = visibleRows.length === 0 ? 'block' : 'none';
        }
    }
    
    function highlightSearchTerm(row, term) {
        removeHighlights(row);
        
        const cells = row.querySelectorAll('td');
        cells.forEach(cell => {
            const html = cell.innerHTML;
            const regex = new RegExp(`(${term})`, 'gi');
            cell.innerHTML = html.replace(regex, '<mark>$1</mark>');
        });
    }
    
    function removeHighlights(row) {
        const marks = row.querySelectorAll('mark');
        marks.forEach(mark => {
            const parent = mark.parentNode;
            parent.replaceChild(document.createTextNode(mark.textContent), mark);
            parent.normalize();
        });
    }
    
    // Setup role filter
    function setupRoleFilter() {
        const roleBadges = document.querySelectorAll('.role-badge');
        const filterContainer = document.createElement('div');
        filterContainer.className = 'role-filters';
        filterContainer.style.cssText = `
            display: flex;
            gap: 10px;
            margin-bottom: 15px;
            flex-wrap: wrap;
        `;
        
        const roles = ['all', 'admin', 'clerk', 'viewer'];
        const roleNames = {
            'all': 'All Users',
            'admin': 'Admins',
            'clerk': 'Clerks',
            'viewer': 'Viewers'
        };
        
        roles.forEach(role => {
            const button = document.createElement('button');
            button.className = `btn btn-sm ${role === 'all' ? 'btn-primary' : 'btn-outline'}`;
            button.dataset.role = role;
            button.innerHTML = `
                <i class="fas fa-${role === 'admin' ? 'user-shield' : role === 'clerk' ? 'user-edit' : 'user'}"></i>
                ${roleNames[role]}
            `;
            
            button.addEventListener('click', function() {
                // Update active button
                filterContainer.querySelectorAll('button').forEach(btn => {
                    btn.className = `btn btn-sm ${btn === this ? 'btn-primary' : 'btn-outline'}`;
                });
                
                // Filter table
                filterByRole(role);
            });
            
            filterContainer.appendChild(button);
        });
        
        const searchInput = document.querySelector('.table-search');
        if (searchInput) {
            searchInput.parentNode.insertBefore(filterContainer, searchInput.nextSibling);
        }
    }
    
    function filterByRole(role) {
        const rows = document.querySelectorAll('.users-table tbody tr');
        
        rows.forEach(row => {
            if (role === 'all') {
                row.style.display = '';
            } else {
                const userRole = row.querySelector('.role-badge').className.includes(role);
                row.style.display = userRole ? '' : 'none';
            }
        });
    }
    
    // Setup bulk actions
    function setupBulkActions() {
        const bulkActions = document.createElement('div');
        bulkActions.className = 'bulk-actions';
        bulkActions.style.cssText = `
            display: none;
            margin-top: 20px;
            padding: 15px;
            background: var(--light-bg, #f8f9fa);
            border-radius: 8px;
            align-items: center;
            gap: 15px;
        `;
        
        bulkActions.innerHTML = `
            <span class="selected-count">0 users selected</span>
            <button class="btn btn-sm btn-outline" id="bulkActivate">
                <i class="fas fa-check"></i> Activate
            </button>
            <button class="btn btn-sm btn-outline" id="bulkDeactivate">
                <i class="fas fa-ban"></i> Deactivate
            </button>
            <button class="btn btn-sm btn-danger" id="bulkDelete">
                <i class="fas fa-trash"></i> Delete
            </button>
            <button class="btn btn-sm btn-outline" id="clearSelection">
                <i class="fas fa-times"></i> Clear
            </button>
        `;
        
        document.querySelector('.content-card').appendChild(bulkActions);
        
        // Add checkboxes to table
        const table = document.querySelector('.users-table thead tr');
        if (table) {
            const th = document.createElement('th');
            th.innerHTML = '<input type="checkbox" id="selectAll">';
            th.style.width = '50px';
            table.insertBefore(th, table.firstChild);
            
            const rows = document.querySelectorAll('.users-table tbody tr');
            rows.forEach(row => {
                const td = document.createElement('td');
                td.innerHTML = '<input type="checkbox" class="user-checkbox">';
                row.insertBefore(td, row.firstChild);
            });
        }
        
        // Setup checkbox logic
        const selectAll = document.getElementById('selectAll');
        const userCheckboxes = document.querySelectorAll('.user-checkbox');
        
        selectAll.addEventListener('change', function() {
            userCheckboxes.forEach(checkbox => {
                checkbox.checked = this.checked;
            });
            updateBulkActions();
        });
        
        userCheckboxes.forEach(checkbox => {
            checkbox.addEventListener('change', updateBulkActions);
        });
        
        // Bulk action handlers
        document.getElementById('bulkActivate').addEventListener('click', () => performBulkAction('activate'));
        document.getElementById('bulkDeactivate').addEventListener('click', () => performBulkAction('deactivate'));
        document.getElementById('bulkDelete').addEventListener('click', () => performBulkAction('delete'));
        document.getElementById('clearSelection').addEventListener('click', clearSelection);
    }
    
    function updateBulkActions() {
        const selected = document.querySelectorAll('.user-checkbox:checked');
        const bulkActions = document.querySelector('.bulk-actions');
        const countSpan = bulkActions.querySelector('.selected-count');
        
        if (selected.length > 0) {
            bulkActions.style.display = 'flex';
            countSpan.textContent = `${selected.length} user${selected.length > 1 ? 's' : ''} selected`;
        } else {
            bulkActions.style.display = 'none';
        }
    }
    
    function performBulkAction(action) {
        const selected = Array.from(document.querySelectorAll('.user-checkbox:checked'))
            .map(checkbox => checkbox.closest('tr').querySelector('.user-id').textContent);
        
        if (selected.length === 0) return;
        
        if (confirm(`Are you sure you want to ${action} ${selected.length} user${selected.length > 1 ? 's' : ''}?`)) {
            // This would typically make an API call
            console.log(`${action} users:`, selected);
            alert(`${action.charAt(0).toUpperCase() + action.slice(1)} action would be performed on selected users.`);
        }
    }
    
    function clearSelection() {
        document.querySelectorAll('.user-checkbox').forEach(checkbox => {
            checkbox.checked = false;
        });
        document.getElementById('selectAll').checked = false;
        updateBulkActions();
    }
    
    // Debounce utility
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
    
    // Add export functionality
    function setupExport() {
        const exportBtn = document.createElement('button');
        exportBtn.className = 'btn btn-sm btn-outline';
        exportBtn.innerHTML = '<i class="fas fa-download"></i> Export Users';
        exportBtn.style.marginLeft = '10px';
        
        const headerActions = document.querySelector('.header-actions');
        if (headerActions) {
            headerActions.appendChild(exportBtn);
            
            exportBtn.addEventListener('click', exportUsers);
        }
    }
    
    function exportUsers() {
        const rows = document.querySelectorAll('.users-table tbody tr');
        const data = [];
        
        rows.forEach(row => {
            if (row.style.display !== 'none') {
                const cells = row.querySelectorAll('td');
                data.push({
                    id: cells[1].textContent.trim(),
                    email: cells[2].querySelector('strong').textContent,
                    role: cells[3].querySelector('.badge').textContent.trim(),
                    status: cells[4].querySelector('.badge').textContent.trim(),
                    created: cells[5].textContent.trim(),
                    lastLogin: cells[6].textContent.trim()
                });
            }
        });
        
        // Create CSV
        const csvContent = [
            ['ID', 'Email', 'Role', 'Status', 'Created', 'Last Login'],
            ...data.map(user => [user.id, user.email, user.role, user.status, user.created, user.lastLogin])
        ].map(row => row.join(',')).join('\n');
        
        // Download file
        const blob = new Blob([csvContent], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `users_export_${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
    
    // Initialize additional features
    setupBulkActions();
    setupExport();
});