/* base.js — global UI behaviour for every page */
'use strict';

/* ── Sidebar (off-canvas on small screens) ──────────────────────────── */
(function initSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebarOverlay');
  const toggles = document.querySelectorAll('[data-sidebar-toggle]');
  if (!sidebar) return;

  function setOpen(open) {
    sidebar.classList.toggle('is-open', open);
    if (overlay) overlay.hidden = !open;
    toggles.forEach((t) => t.setAttribute('aria-expanded', String(open)));
    document.body.style.overflow = open ? 'hidden' : '';
  }

  toggles.forEach((t) => t.addEventListener('click', () => setOpen(!sidebar.classList.contains('is-open'))));
  overlay && overlay.addEventListener('click', () => setOpen(false));
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') setOpen(false); });
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
  // The clicked button's message wins, so one form can confirm only some actions
  const msg  = (e.submitter && e.submitter.dataset.confirm) || form.dataset.confirm;
  if (msg && !confirm(msg)) e.preventDefault();
});

/* ── Copy to clipboard (data-copy="text") ─────────────────────────── */
document.addEventListener('click', async (e) => {
  const button = e.target.closest('[data-copy]');
  if (!button) return;
  const label = button.innerHTML;
  try {
    await navigator.clipboard.writeText(button.dataset.copy);
    button.innerHTML = '<i class="fas fa-check"></i> Copied';
  } catch {
    // No clipboard access (e.g. plain http): select the text so it can be copied by hand
    const input = button.parentElement.querySelector('input');
    if (input) { input.select(); }
    button.innerHTML = 'Press Ctrl+C';
  }
  setTimeout(() => { button.innerHTML = label; }, 2000);
});
