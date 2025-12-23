// app/static/js/base.js
document.addEventListener('DOMContentLoaded', function() {
    // Mobile Navigation
    const mobileMenuBtn = document.getElementById('mobileMenuBtn');
    const mobileNavOverlay = document.getElementById('mobileNavOverlay');
    const closeMobileNav = document.getElementById('closeMobileNav');

    function openMobileNav() {
        mobileNavOverlay.classList.add('active');
        document.body.style.overflow = 'hidden';
    }

    function closeMobileNavFunc() {
        mobileNavOverlay.classList.remove('active');
        document.body.style.overflow = '';
    }

    if (mobileMenuBtn && mobileNavOverlay && closeMobileNav) {
        mobileMenuBtn.addEventListener('click', openMobileNav);
        closeMobileNav.addEventListener('click', closeMobileNavFunc);
        mobileNavOverlay.addEventListener('click', function(e) {
            if (e.target === mobileNavOverlay) {
                closeMobileNavFunc();
            }
        });

        // Close mobile nav when clicking on links
        document.querySelectorAll('.mobile-nav-link').forEach(link => {
            link.addEventListener('click', closeMobileNavFunc);
        });
    }

    // Auto-dismiss flash messages after 5 seconds
    setTimeout(() => {
        document.querySelectorAll('.alert').forEach(alert => {
            alert.style.transition = 'opacity 0.3s ease';
            alert.style.opacity = '0';
            setTimeout(() => {
                alert.style.display = 'none';
            }, 300);
        });
    }, 5000);

    // Close alert on button click
    document.querySelectorAll('.alert-close').forEach(button => {
        button.addEventListener('click', function() {
            const alert = this.closest('.alert');
            alert.style.transition = 'opacity 0.3s ease';
            alert.style.opacity = '0';
            setTimeout(() => {
                alert.style.display = 'none';
            }, 300);
        });
    });
});