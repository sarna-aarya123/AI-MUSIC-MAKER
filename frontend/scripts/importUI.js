// ── Import UI ─────────────────────────────────────────────────────────────────
// Wires the #import-panel controls to MelodyExtractor and refreshMelodyTrack().
// Zero interaction with AudioEngine, AudioScheduler, or the transport clock.

(function () {
  const panel      = document.getElementById('import-panel');
  if (!panel) return;

  const dropZone   = document.getElementById('import-dropzone');
  const fileInput  = document.getElementById('import-file-input');
  const progressEl = document.getElementById('import-progress');
  const barEl      = document.getElementById('import-progress-bar');
  const statusEl   = document.getElementById('import-status');
  const generateBtn = document.getElementById('btn-import-generate');
  const toggleBtn  = document.getElementById('btn-import-toggle');
  const bodyEl     = document.getElementById('import-body');
  const dropLabel  = dropZone?.querySelector('.import-drop-label');

  let loadedFile = null;

  // ── Collapse / expand ────────────────────────────────────────────────────────
  toggleBtn?.addEventListener('click', () => {
    const c = bodyEl.classList.toggle('collapsed');
    toggleBtn.textContent = c ? '+' : '–';
    toggleBtn.title       = c ? 'Expand' : 'Collapse';
  });

  // ── File picker ──────────────────────────────────────────────────────────────
  dropZone?.addEventListener('click', () => fileInput?.click());

  fileInput?.addEventListener('change', () => {
    if (fileInput.files[0]) _handleFile(fileInput.files[0]);
  });

  // ── Drag & drop ──────────────────────────────────────────────────────────────
  dropZone?.addEventListener('dragover', e => {
    e.preventDefault();
    dropZone.classList.add('drag-over');
  });
  dropZone?.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
  dropZone?.addEventListener('drop', e => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    if (e.dataTransfer.files[0]) _handleFile(e.dataTransfer.files[0]);
  });

  function _handleFile(file) {
    const isAudio = file.type.startsWith('audio/') ||
                    /\.(mp3|wav|ogg|m4a|aac|flac|opus)$/i.test(file.name);
    if (!isAudio) { _status('Not an audio file — try MP3, WAV, or OGG', 'err'); return; }

    loadedFile = file;
    if (dropLabel) dropLabel.textContent = file.name;
    _status(`Loaded: ${file.name}`, 'ok');
    if (generateBtn) generateBtn.disabled = false;
  }

  // ── Generate Similar Melody ───────────────────────────────────────────────────
  generateBtn?.addEventListener('click', async () => {
    if (!loadedFile) { _status('Drop an audio file first', 'err'); return; }

    // Must have an active DAW session (song generated)
    const tracksContainer = document.getElementById('tracks-container');
    if (tracksContainer && tracksContainer.hidden) {
      _status('Generate a song first, then import', 'err');
      return;
    }

    const bpm        = (typeof DAW_STATE !== 'undefined' && DAW_STATE.bpm)
                        ? DAW_STATE.bpm        : 120;
    const totalBeats = (typeof DAW_STATE !== 'undefined' && DAW_STATE.totalBeats)
                        ? DAW_STATE.totalBeats : 16;

    generateBtn.disabled = true;
    _progress(0, true);
    _status('Analysing audio…', '');

    try {
      const result = await MelodyExtractor.extractFromFile(
        loadedFile, bpm, totalBeats,
        pct => _progress(pct, true),
      );

      if (!result || !result.notes.length) {
        _status('No clear melody detected — try a file with a prominent lead line', 'err');
        _progress(0, false);
        return;
      }

      refreshMelodyTrack(result.notes);
      _progress(1, false);
      _status(
        `✓ ${result.notes.length} notes · ${result.key.name} · press ▶ to hear`,
        'ok',
      );
    } catch (e) {
      console.error('[ImportUI]', e);
      _status(`Error: ${e.message}`, 'err');
      _progress(0, false);
    } finally {
      generateBtn.disabled = false;
      setTimeout(() => _progress(0, false), 2000);
    }
  });

  // ── Helpers ──────────────────────────────────────────────────────────────────
  function _progress(pct, visible) {
    if (!progressEl) return;
    if (visible !== undefined) progressEl.style.display = visible ? 'block' : 'none';
    if (barEl) barEl.style.width = `${Math.round(Math.min(1, pct) * 100)}%`;
  }

  function _status(msg, cls) {
    if (!statusEl) return;
    statusEl.textContent = msg;
    statusEl.className   = `import-status${cls ? ' ' + cls : ''}`;
  }
})();
