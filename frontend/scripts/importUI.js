// ── Import UI (Feel-Based) ─────────────────────────────────────────────────────
// Audio file → extract tonal center + energy feel → call /api/loop/evolve
// with derived parameters → install new loop identity.
//
// Does NOT extract or import notes. Does NOT touch the scheduler directly.
// Output is a new loop identity, not a transcription.

(function () {
  const panel       = document.getElementById('import-panel');
  if (!panel) return;

  const dropZone    = document.getElementById('import-dropzone');
  const fileInput   = document.getElementById('import-file-input');
  const progressEl  = document.getElementById('import-progress');
  const barEl       = document.getElementById('import-progress-bar');
  const statusEl    = document.getElementById('import-status');
  const generateBtn = document.getElementById('btn-import-generate');
  const toggleBtn   = document.getElementById('btn-import-toggle');
  const bodyEl      = document.getElementById('import-body');
  const dropLabel   = dropZone?.querySelector('.import-drop-label');

  // Map MIDI pitch → root note string
  const MIDI_TO_ROOT = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'];

  let loadedFile = null;

  // ── Collapse ──────────────────────────────────────────────────────────────────
  toggleBtn?.addEventListener('click', () => {
    const c = bodyEl.classList.toggle('collapsed');
    toggleBtn.textContent = c ? '+' : '–';
    toggleBtn.title       = c ? 'Expand' : 'Collapse';
  });

  // ── File input ────────────────────────────────────────────────────────────────
  dropZone?.addEventListener('click', () => fileInput?.click());
  fileInput?.addEventListener('change', () => { if (fileInput.files[0]) _load(fileInput.files[0]); });

  dropZone?.addEventListener('dragover',  e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
  dropZone?.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
  dropZone?.addEventListener('drop', e => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    if (e.dataTransfer.files[0]) _load(e.dataTransfer.files[0]);
  });

  function _load(file) {
    const ok = file.type.startsWith('audio/') ||
               /\.(mp3|wav|ogg|m4a|aac|flac|opus)$/i.test(file.name);
    if (!ok) { _status('Not an audio file', 'err'); return; }
    loadedFile = file;
    if (dropLabel) dropLabel.textContent = file.name;
    _status(`Loaded: ${file.name}`, 'ok');
    if (generateBtn) generateBtn.disabled = false;
  }

  // ── Generate feel-matched loop ────────────────────────────────────────────────
  generateBtn?.addEventListener('click', async () => {
    if (!loadedFile) { _status('Drop an audio file first', 'err'); return; }

    generateBtn.disabled = true;
    _progress(0, true);
    _status('Analysing feel…');

    try {
      // Step 1: extract feel characteristics via MelodyExtractor
      // We reuse MelodyExtractor for tonal center detection and
      // rhythm density — we discard extracted notes entirely.
      const bpm        = parseInt(document.getElementById('ctrl-bpm')?.value ?? '140', 10);
      const totalBeats = 16; // dummy — we only care about key/feel, not notes

      const feel = await MelodyExtractor.extractFromFile(
        loadedFile, bpm, totalBeats,
        pct => _progress(pct * 0.7, true),
      );

      _progress(0.72, true);
      _status('Generating loop identity from feel…');

      // Step 2: map extracted characteristics to loop parameters
      // feel is { notes, key } — we use key.root and key.type but NOT the notes
      const root   = feel ? _midiToRoot(feel.key.root) : _guessRootFromControls();
      const genre  = document.getElementById('ctrl-genre')?.value ?? 'rage';
      const bars   = parseInt(document.getElementById('ctrl-bars')?.value ?? '4', 10);

      _progress(0.75, true);

      // Step 3: call /api/loop/evolve with feel-derived parameters
      const res = await fetch('/api/loop/evolve', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({
          genre,
          root,
          bpm,
          bars,
          seed: Math.floor(Math.random() * 99999),
        }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      _progress(1.0, true);

      // Step 4: install as new loop identity (feel preserved, notes regenerated)
      if (typeof _installLoop === 'function') {
        _installLoop(data);
        _status(`✓ Loop identity from feel · ${root} ${feel?.key.type ?? ''} · ${data.bpm} BPM`, 'ok');
      } else {
        _status('Generate a loop first (press EVOLVE), then import', 'err');
      }

    } catch (e) {
      console.error('[ImportUI]', e);
      _status(`Error: ${e.message}`, 'err');
    } finally {
      generateBtn.disabled = false;
      setTimeout(() => _progress(0, false), 1800);
    }
  });

  // ── Helpers ───────────────────────────────────────────────────────────────────
  function _midiToRoot(midiPitchClass) {
    return MIDI_TO_ROOT[((midiPitchClass % 12) + 12) % 12] ?? 'A';
  }

  function _guessRootFromControls() {
    return document.getElementById('ctrl-root')?.value ?? 'A';
  }

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
