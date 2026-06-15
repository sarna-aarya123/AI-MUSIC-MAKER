// ── One-Shot UI wiring ─────────────────────────────────────────────────────────
// Connects the #oneshot-panel controls to OneShotEngine.
// Zero interaction with DAW_STATE, transport, or scheduler.

(function () {
  const panel      = document.getElementById('oneshot-panel');
  if (!panel) return;

  const inputEl    = document.getElementById('oneshot-input');
  const previewBtn = document.getElementById('btn-oneshot-preview');
  const toggleBtn  = document.getElementById('btn-oneshot-toggle');
  const bodyEl     = document.getElementById('oneshot-body');
  const infoEl     = document.getElementById('oneshot-info');
  const assignBtns = document.querySelectorAll('.btn-assign');

  // ── Collapse / expand ───────────────────────────────────────────────────────
  toggleBtn?.addEventListener('click', () => {
    const collapsed = bodyEl.classList.toggle('collapsed');
    toggleBtn.textContent = collapsed ? '+' : '–';
    toggleBtn.title       = collapsed ? 'Expand' : 'Collapse';
  });

  // ── Preview ─────────────────────────────────────────────────────────────────
  async function doPreview() {
    const text = inputEl?.value.trim();
    if (!text) { _info('enter a description first', 'err'); return; }

    previewBtn.disabled = true;
    _info('playing…', '');
    try {
      const p = await OneShotEngine.previewOneShot(text);
      _info(_summarise(p), 'ok');
    } catch (e) {
      _info(`error: ${e.message}`, 'err');
      console.error('[OneShotUI]', e);
    } finally {
      previewBtn.disabled = false;
    }
  }

  previewBtn?.addEventListener('click', doPreview);

  // Enter triggers preview; stop propagation so DAW key handlers don't fire.
  inputEl?.addEventListener('keydown', e => {
    e.stopPropagation();             // prevents Delete/Space/Backspace reaching editor.js
    if (e.key === 'Enter') doPreview();
  });

  // ── Assign to drum slot ──────────────────────────────────────────────────────
  for (const btn of assignBtns) {
    btn.addEventListener('click', async () => {
      const text = inputEl?.value.trim();
      const slot = btn.dataset.slot;
      if (!text) { _info('enter a description first', 'err'); return; }

      try {
        await OneShotEngine.assignToDrumSlot(text, slot);
        assignBtns.forEach(b => b.classList.remove('assigned'));
        btn.classList.add('assigned');
        _info(`assigned "${text}" → ${slot}`, 'ok');
      } catch (e) {
        _info(`assign failed: ${e.message}`, 'err');
      }
    });
  }

  // ── Helpers ─────────────────────────────────────────────────────────────────
  function _info(msg, cls) {
    if (!infoEl) return;
    infoEl.textContent = msg;
    infoEl.className   = `oneshot-info${cls ? ' ' + cls : ''}`;
  }

  function _summarise(p) {
    if (!p || typeof p !== 'object') return '';
    const tags = [p.type];
    if (p.tight)    tags.push('tight');
    if (p.long)     tags.push('long');
    if (p.punchy)   tags.push('punchy');
    if (p.soft)     tags.push('soft');
    if (p.bright)   tags.push('bright');
    if (p.dark)     tags.push('dark');
    if (p.metallic) tags.push('metallic');
    if (p.airy)     tags.push('airy');
    return `→ ${tags.join(' · ')}   decay ${p.decayTime.toFixed(2)}s`;
  }
})();
