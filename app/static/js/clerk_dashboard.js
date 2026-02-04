// app/static/js/clerk_dashboard.js
document.addEventListener('DOMContentLoaded', function() {
    initializeClerkDashboard();
    
    function initializeClerkDashboard() {
        setupCardAnimations();
        setupActionButtons();
        setupQuickLinks();
        setupStatusUpdates();
    }
    
    // Setup card animations
    function setupCardAnimations() {
        const cards = document.querySelectorAll('.stat-card, .action-item, .link-card');
        
        cards.forEach(card => {
            card.style.opacity = '0';
            card.style.transform = 'translateY(20px)';
            
            setTimeout(() => {
                card.style.transition = 'opacity 0.5s, transform 0.5s';
                card.style.opacity = '1';
                card.style.transform = 'translateY(0)';
            }, 100);
        });
    }
    
    // Setup action buttons hover effects
    function setupActionButtons() {
        const actionItems = document.querySelectorAll('.action-item');
        
        actionItems.forEach(item => {
            item.addEventListener('mouseenter', function() {
                const icon = this.querySelector('.action-icon');
                if (icon) {
                    icon.style.transform = 'scale(1.1) rotate(5deg)';
                }
            });
            
            item.addEventListener('mouseleave', function() {
                const icon = this.querySelector('.action-icon');
                if (icon) {
                    icon.style.transform = 'scale(1) rotate(0deg)';
                }
            });
        });
        
        // Report items hover effects
        const reportItems = document.querySelectorAll('.report-item');
        reportItems.forEach(item => {
            item.addEventListener('mouseenter', function() {
                this.style.transform = 'translateX(5px)';
                this.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)';
            });
            
            item.addEventListener('mouseleave', function() {
                this.style.transform = 'translateX(0)';
                this.style.boxShadow = 'none';
            });
        });
    }
    
    // Setup quick links interactions
    function setupQuickLinks() {
        const linkCards = document.querySelectorAll('.link-card');
        
        linkCards.forEach(card => {
            card.addEventListener('mouseenter', function() {
                this.style.transform = 'translateY(-5px) scale(1.02)';
                this.style.boxShadow = '0 12px 30px rgba(0,0,0,0.15)';
                
                const icon = this.querySelector('i');
                if (icon) {
                    icon.style.transform = 'scale(1.2)';
                    icon.style.transition = 'transform 0.3s';
                }
            });
            
            card.addEventListener('mouseleave', function() {
                this.style.transform = 'translateY(0) scale(1)';
                this.style.boxShadow = '0 4px 15px rgba(0,0,0,0.08)';
                
                const icon = this.querySelector('i');
                if (icon) {
                    icon.style.transform = 'scale(1)';
                }
            });
            
            // Add click animation
            card.addEventListener('click', function(e) {
                if (!this.href) return;
                
                // Create ripple effect
                const ripple = document.createElement('span');
                const rect = this.getBoundingClientRect();
                const size = Math.max(rect.width, rect.height);
                const x = e.clientX - rect.left - size / 2;
                const y = e.clientY - rect.top - size / 2;
                
                ripple.style.cssText = `
                    position: absolute;
                    border-radius: 50%;
                    background: rgba(66, 153, 225, 0.3);
                    transform: scale(0);
                    animation: ripple 0.6s linear;
                    width: ${size}px;
                    height: ${size}px;
                    left: ${x}px;
                    top: ${y}px;
                    pointer-events: none;
                    z-index: 1;
                `;
                
                this.style.position = 'relative';
                this.style.overflow = 'hidden';
                this.appendChild(ripple);
                
                // Remove ripple after animation
                setTimeout(() => {
                    if (ripple.parentNode) {
                        ripple.parentNode.removeChild(ripple);
                    }
                }, 600);
            });
        });
        
        // Add ripple animation
        const style = document.createElement('style');
        style.textContent = `
            @keyframes ripple {
                to {
                    transform: scale(4);
                    opacity: 0;
                }
            }
        `;
        document.head.appendChild(style);
    }
    
    // Setup status updates and notifications
    function setupStatusUpdates() {
        // Check Google Sheets status
        checkSheetsStatus();
        
        // Auto-refresh reports list every 30 seconds
        setInterval(checkForNewReports, 30000);
        
        // Setup keyboard shortcuts
        setupKeyboardShortcuts();
    }
    
    function checkSheetsStatus() {
        const sheetsCard = document.querySelector('.stat-card.card-warning, .stat-card.card-success');
        if (!sheetsCard) return;
        
        // This would typically make an API call to check Sheets status
        // For now, we'll just animate the status icon
        const icon = sheetsCard.querySelector('.stat-icon i');
        if (icon) {
            icon.style.transition = 'transform 0.5s';
            setTimeout(() => {
                icon.style.transform = 'scale(1.2)';
                setTimeout(() => {
                    icon.style.transform = 'scale(1)';
                }, 300);
            }, 1000);
        }
    }
    
    function checkForNewReports() {
        // This would check for new reports from the server
        // For now, we'll just show a subtle notification
        const reportsList = document.querySelector('.reports-list');
        if (!reportsList || reportsList.querySelector('.empty-state')) return;
        
        // Add pulsing animation to the badge
        const badge = document.querySelector('.card-header .badge');
        if (badge) {
            badge.style.animation = 'pulse 1s infinite';
            setTimeout(() => {
                badge.style.animation = '';
            }, 3000);
        }
        
        // Add pulse animation
        const pulseStyle = document.createElement('style');
        pulseStyle.textContent = `
            @keyframes pulse {
                0% { box-shadow: 0 0 0 0 rgba(66, 153, 225, 0.4); }
                70% { box-shadow: 0 0 0 10px rgba(66, 153, 225, 0); }
                100% { box-shadow: 0 0 0 0 rgba(66, 153, 225, 0); }
            }
        `;
        document.head.appendChild(pulseStyle);
    }
    
    function setupKeyboardShortcuts() {
        document.addEventListener('keydown', function(e) {
            // Alt + G: Go to Generate Report
            if (e.altKey && e.key === 'g') {
                e.preventDefault();
                const generateBtn = document.querySelector('a[href*="upload-dashboard"]');
                if (generateBtn) generateBtn.click();
            }
            
            // Alt + R: Go to Reports
            if (e.altKey && e.key === 'r') {
                e.preventDefault();
                const reportsBtn = document.querySelector('a[href*="reports_list"]');
                if (reportsBtn) reportsBtn.click();
            }
            
            // Alt + S: Go to Settings
            if (e.altKey && e.key === 's') {
                e.preventDefault();
                const settingsBtn = document.querySelector('a[href*="settings"]');
                if (settingsBtn) settingsBtn.click();
            }
            
            // Alt + H: Show Help
            if (e.altKey && e.key === 'h') {
                e.preventDefault();
                const helpSection = document.querySelector('.content-card:last-child');
                if (helpSection) {
                    helpSection.scrollIntoView({ behavior: 'smooth' });
                    
                    // Add highlight animation
                    helpSection.style.boxShadow = '0 0 0 3px rgba(66, 153, 225, 0.3)';
                    setTimeout(() => {
                        helpSection.style.boxShadow = '';
                    }, 2000);
                }
            }
        });
        
        // Show keyboard shortcuts help on Ctrl + /
        document.addEventListener('keydown', function(e) {
            if ((e.ctrlKey || e.metaKey) && e.key === '/') {
                e.preventDefault();
                showKeyboardShortcutsHelp();
            }
        });
    }
    
    function showKeyboardShortcutsHelp() {
        const helpModal = document.createElement('div');
        helpModal.className = 'shortcuts-modal';
        helpModal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
            animation: fadeIn 0.3s;
        `;
        
        const shortcuts = [
            { key: 'Alt + G', description: 'Go to Generate Report' },
            { key: 'Alt + R', description: 'Go to Reports' },
            { key: 'Alt + S', description: 'Go to Settings' },
            { key: 'Alt + H', description: 'Scroll to Help' },
            { key: 'Ctrl + /', description: 'Show this help' }
        ];
        
        helpModal.innerHTML = `
            <div class="modal-content" style="
                background: white;
                border-radius: 12px;
                padding: 30px;
                max-width: 500px;
                width: 90%;
                max-height: 80vh;
                overflow-y: auto;
                animation: slideUp 0.3s;
            ">
                <div class="modal-header" style="
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 20px;
                ">
                    <h3 style="margin: 0; font-size: 20px; color: #2d3748;">
                        <i class="fas fa-keyboard"></i>
                        Keyboard Shortcuts
                    </h3>
                    <button class="close-modal" style="
                        background: none;
                        border: none;
                        font-size: 24px;
                        color: #a0aec0;
                        cursor: pointer;
                        padding: 5px;
                    ">&times;</button>
                </div>
                <div class="modal-body">
                    <div style="
                        display: grid;
                        gap: 15px;
                    ">
                        ${shortcuts.map(shortcut => `
                            <div style="
                                display: flex;
                                justify-content: space-between;
                                align-items: center;
                                padding: 12px 15px;
                                background: #f7fafc;
                                border-radius: 8px;
                            ">
                                <span style="
                                    font-weight: 600;
                                    color: #4a5568;
                                    background: #e2e8f0;
                                    padding: 4px 8px;
                                    border-radius: 4px;
                                    font-family: monospace;
                                ">${shortcut.key}</span>
                                <span style="color: #718096;">${shortcut.description}</span>
                            </div>
                        `).join('')}
                    </div>
                </div>
                <div class="modal-footer" style="
                    margin-top: 20px;
                    text-align: center;
                ">
                    <small style="color: #a0aec0;">
                        <i class="fas fa-info-circle"></i>
                        Press ESC to close
                    </small>
                </div>
            </div>
        `;
        
        document.body.appendChild(helpModal);
        
        // Close modal functions
        const closeBtn = helpModal.querySelector('.close-modal');
        closeBtn.addEventListener('click', closeModal);
        
        helpModal.addEventListener('click', function(e) {
            if (e.target === helpModal) {
                closeModal();
            }
        });
        
        document.addEventListener('keydown', function closeOnEsc(e) {
            if (e.key === 'Escape') {
                closeModal();
                document.removeEventListener('keydown', closeOnEsc);
            }
        });
        
        function closeModal() {
            helpModal.style.animation = 'fadeOut 0.3s';
            setTimeout(() => {
                if (helpModal.parentNode) {
                    helpModal.parentNode.removeChild(helpModal);
                }
            }, 300);
        }
        
        // Add animations
        const animations = document.createElement('style');
        animations.textContent = `
            @keyframes fadeIn {
                from { opacity: 0; }
                to { opacity: 1; }
            }
            @keyframes fadeOut {
                from { opacity: 1; }
                to { opacity: 0; }
            }
            @keyframes slideUp {
                from {
                    opacity: 0;
                    transform: translateY(30px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
        `;
        document.head.appendChild(animations);
    }
    
    // Add tip cycling for help section
    function setupTipCycling() {
        const tipItems = document.querySelectorAll('.tip-item');
        if (tipItems.length === 0) return;
        
        let currentTip = 0;
        
        // Create navigation dots
        const tipsContainer = document.querySelector('.tips-list');
        if (tipsContainer) {
            const dotsContainer = document.createElement('div');
            dotsContainer.style.cssText = `
                display: flex;
                justify-content: center;
                gap: 8px;
                margin-top: 20px;
            `;
            
            tipItems.forEach((_, index) => {
                const dot = document.createElement('button');
                dot.className = 'tip-dot';
                dot.dataset.index = index;
                dot.style.cssText = `
                    width: 10px;
                    height: 10px;
                    border-radius: 50%;
                    background: ${index === 0 ? '#4299e1' : '#e2e8f0'};
                    border: none;
                    cursor: pointer;
                    transition: background 0.3s;
                    padding: 0;
                `;
                
                dot.addEventListener('click', function() {
                    showTip(index);
                });
                
                dotsContainer.appendChild(dot);
            });
            
            tipsContainer.parentNode.appendChild(dotsContainer);
            
            // Auto-cycle tips every 10 seconds
            setInterval(() => {
                currentTip = (currentTip + 1) % tipItems.length;
                showTip(currentTip);
            }, 10000);
        }
    }
    
    function showTip(index) {
        const tipItems = document.querySelectorAll('.tip-item');
        const dots = document.querySelectorAll('.tip-dot');
        
        tipItems.forEach((item, i) => {
            item.style.display = i === index ? 'flex' : 'none';
        });
        
        dots.forEach((dot, i) => {
            dot.style.background = i === index ? '#4299e1' : '#e2e8f0';
        });
    }
    
    // Initialize tip cycling
    setupTipCycling();
    
    // Add print report functionality
    function setupPrintFunctionality() {
        const printBtn = document.createElement('button');
        printBtn.className = 'btn btn-sm btn-outline';
        printBtn.innerHTML = '<i class="fas fa-print"></i> Print Dashboard';
        printBtn.style.marginTop = '20px';
        
        const welcomeSection = document.querySelector('.welcome-section');
        if (welcomeSection) {
            welcomeSection.parentNode.insertBefore(printBtn, welcomeSection.nextSibling);
            
            printBtn.addEventListener('click', function() {
                window.print();
            });
        }
    }
    
    // Initialize print functionality
    setupPrintFunctionality();
});