/* base.js — global UI behaviour for every page */
'use strict';

/* ── User dropdown ──────────────────────────────────────────────────── */
(function initUserMenu() {
  const menu   = document.getElementById('userMenu');
  const btn    = document.getElementById('userMenuBtn');
  const drop   = document.getElementById('userDropdown');
  if (!menu || !btn || !drop) return;

  function open()  {
    menu.classList.add('is-open');
    btn.setAttribute('aria-expanded', 'true');
    drop.setAttribute('aria-hidden', 'false');
  }
  function close() {
    menu.classList.remove('is-open');
    btn.setAttribute('aria-expanded', 'false');
    drop.setAttribute('aria-hidden', 'true');
  }

  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    menu.classList.contains('is-open') ? close() : open();
  });

  document.addEventListener('click', (e) => {
    if (!menu.contains(e.target)) close();
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') close();
  });
})();

/* ── Mobile drawer ──────────────────────────────────────────────────── */
(function initMobileNav() {
  const hamburger = document.getElementById('hamburgerBtn');
  const nav       = document.getElementById('mobileNav');
  const overlay   = document.getElementById('mobileOverlay');
  const closeBtn  = document.getElementById('mobileNavClose');
  if (!hamburger || !nav) return;

  function openNav() {
    nav.classList.add('is-open');
    overlay && overlay.classList.add('is-open');
    hamburger.setAttribute('aria-expanded', 'true');
    nav.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
  }
  function closeNav() {
    nav.classList.remove('is-open');
    overlay && overlay.classList.remove('is-open');
    hamburger.setAttribute('aria-expanded', 'false');
    nav.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
  }

  hamburger.addEventListener('click', openNav);
  closeBtn  && closeBtn.addEventListener('click', closeNav);
  overlay   && overlay.addEventListener('click', closeNav);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeNav(); });
})();

/* ── Flash auto-dismiss (after 6 s) ────────────────────────────────── */
(function initFlashDismiss() {
  document.querySelectorAll('.flash').forEach((el) => {
    setTimeout(() => {
      el.style.transition = 'opacity .4s ease, transform .4s ease';
      el.style.opacity    = '0';
      el.style.transform  = 'translateY(-6px)';
      setTimeout(() => el.remove(), 420);
    }, 6000);
  });
})();

/* ── Password show/hide toggle ──────────────────────────────────────── */
(function initPasswordToggles() {
  document.querySelectorAll('.input-suffix[data-toggle-pwd]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const wrap  = btn.closest('.input-wrap');
      const input = wrap && wrap.querySelector('input');
      if (!input) return;
      const isText = input.type === 'text';
      input.type   = isText ? 'password' : 'text';
      const icon   = btn.querySelector('i');
      if (icon) icon.className = isText ? 'fas fa-eye' : 'fas fa-eye-slash';
    });
  });
})();

/* ── Modal helpers (data-modal-open / data-modal-close) ─────────────── */
(function initModals() {
  function openModal(id) {
    const bd = document.getElementById(id);
    if (!bd) return;
    bd.classList.add('is-open');
    document.body.style.overflow = 'hidden';
    // focus first focusable element
    const first = bd.querySelector('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
    first && first.focus();
  }
  function closeModal(id) {
    const bd = document.getElementById(id);
    if (!bd) return;
    bd.classList.remove('is-open');
    document.body.style.overflow = '';
  }

  document.addEventListener('click', (e) => {
    const opener = e.target.closest('[data-modal-open]');
    if (opener) { openModal(opener.dataset.modalOpen); return; }

    const closer = e.target.closest('[data-modal-close]');
    if (closer) { closeModal(closer.dataset.modalClose); return; }

    // click on backdrop itself
    if (e.target.classList.contains('modal-backdrop')) {
      e.target.classList.remove('is-open');
      document.body.style.overflow = '';
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    document.querySelectorAll('.modal-backdrop.is-open').forEach((bd) => {
      bd.classList.remove('is-open');
      document.body.style.overflow = '';
    });
  });

  // expose globally for inline onclick usage
  window.openModal  = openModal;
  window.closeModal = closeModal;
})();

/* ── Inline form confirmation (data-confirm) ────────────────────────── */
document.addEventListener('submit', (e) => {
  const form = e.target;
  const msg  = form.dataset.confirm;
  if (msg && !confirm(msg)) e.preventDefault();
});

/* ── Active nav link highlight (fallback for pages that set it) ─────── */
(function highlightActiveLink() {
  const path = window.location.pathname;
  document.querySelectorAll('.topnav__link, .mobile-nav__link').forEach((a) => {
    if (a.getAttribute('href') === path) a.classList.add('is-active');
  });
})();