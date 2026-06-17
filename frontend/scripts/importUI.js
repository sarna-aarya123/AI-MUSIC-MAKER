// ── Import UI — 2-State Feel + A/B Preview Panel ──────────────────────────────
// State A (drop):   dropzone visible
// State B (loaded): feel card + reference player + optional generated player
//
// Reference audio   → HTMLAudioElement (Object URL)
// Generated loop    → LoopTransport (loop_studio.js) + phase animation

(function () {
  const panel = document.getElementById('import-panel');
  if (!panel) return;

  // ── Element refs ─────────────────────────────────────────────────────────────
  const toggleBtn      = document.getElementById('btn-import-toggle');
  const bodyEl         = document.getElementById('import-body');

  // State A
  const stateDrop      = document.getElementById('import-state-drop');
  const dropZone       = document.getElementById('import-dropzone');
  const fileInput      = document.getElementById('import-file-input');

  // State B
  const stateLoaded    = document.getElementById('import-state-loaded');
  const fileNameEl     = document.getElementById('import-file-name');
  const btnClear       = document.getElementById('btn-clear-file');
  const feelRoot       = document.getElementById('feel-root');
  const feelMood       = document.getElementById('feel-mood');
  const feelEnergy     = document.getElementById('feel-energy');

  // Reference player
  const audioRef       = document.getElementById('import-audio-ref');
  const btnRefPlay     = document.getElementById('btn-ref-play');
  const refFill        = document.getElementById('ref-progress-fill');
  const refTime        = document.getElementById('ref-time-display');

  // Generated player
  const genSection     = document.getElementById('gen-player-section');
  const btnLoopPlay    = document.getElementById('btn-loop-play');
  const loopFill       = document.getElementById('loop-phase-fill');
  const genDetail      = document.getElementById('import-gen-detail');

  // Actions
  const btnPlayBoth    = document.getElementById('btn-play-both');
  const btnGenerate    = document.getElementById('btn-import-generate');
  const btnGenAgain    = document.getElementById('btn-gen-again');

  // Shared
  const progressEl     = document.getElementById('import-progress');
  const progressBar    = document.getElementById('import-progress-bar');
  const statusEl       = document.getElementById('import-status');

  const MIDI_ROOTS = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'];

  let _file      = null;
  let _fileURL   = null;
  let _feel      = null;
  let _refPlaying  = false;
  let _loopPlaying = false;
  let _loopRafId   = null;
  let _generated   = false;

  // ── Collapse toggle ───────────────────────────────────────────────────────────
  toggleBtn?.addEventListener('click', () => {
    const collapsed = bodyEl.classList.toggle('collapsed');
    toggleBtn.textContent = collapsed ? '+' : '–';
    toggleBtn.title       = collapsed ? 'Expand' : 'Collapse';
  });

  // ── State A: drop / file select ───────────────────────────────────────────────
  dropZone?.addEventListener('click', () => fileInput?.click());
  fileInput?.addEventListener('change', () => { if (fileInput.files[0]) _loadFile(fileInput.files[0]); });
  dropZone?.addEventListener('dragover',  e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
  dropZone?.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
  dropZone?.addEventListener('drop', e => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    if (e.dataTransfer.files[0]) _loadFile(e.dataTransfer.files[0]);
  });

  function _loadFile(file) {
    const ok = file.type.startsWith('audio/') ||
               /\.(mp3|wav|ogg|m4a|aac|flac|opus)$/i.test(file.name);
    if (!ok) { _status('Not an audio file', 'err'); return; }

    _file = file;
    if (_fileURL) URL.revokeObjectURL(_fileURL);
    _fileURL = URL.createObjectURL(file);

    // Wire audio element
    if (audioRef) {
      audioRef.src = _fileURL;
      audioRef.load();
    }
    if (fileNameEl) fileNameEl.textContent = file.name;

    // Show loaded state, hide generated section until needed
    _setState('loaded');
    _resetGenSection();
    _status('Analysing feel…');
    _extractFeel(file);
  }

  btnClear?.addEventListener('click', () => {
    _stopRef();
    _stopLoop();
    _file = null;
    if (_fileURL) { URL.revokeObjectURL(_fileURL); _fileURL = null; }
    _feel = null;
    _generated = false;
    if (fileInput) fileInput.value = '';
    _setState('drop');
    _status('');
  });

  // ── Feel extraction ───────────────────────────────────────────────────────────
  async function _extractFeel(file) {
    const bpm = parseInt(document.getElementById('ctrl-bpm')?.value ?? '140', 10);
    _progress(0, true);
    if (btnRefPlay)  btnRefPlay.disabled  = true;
    if (btnGenerate) btnGenerate.disabled = true;

    try {
      const result = await MelodyExtractor.extractFromFile(
        file, bpm, 16,
        pct => _progress(pct, true),
      );
      _progress(1, true);

      const root   = result ? _midiToRoot(result.key.root) : _controlRoot();
      const mood   = result?.key?.type ?? 'minor';
      const energy = result ? _inferEnergy(result.notes) : 'medium';

      _feel = { root, mood, energy, key: result?.key ?? { root: 69, type: 'minor' } };

      if (feelRoot)   feelRoot.textContent   = root;
      if (feelMood)   feelMood.textContent   = mood;
      if (feelEnergy) feelEnergy.textContent = energy;

      if (btnRefPlay)  btnRefPlay.disabled  = false;
      if (btnGenerate) btnGenerate.disabled = false;
      _status(
        result ? 'Feel extracted — ready to generate' : 'Could not detect key — using defaults',
        result ? 'ok' : 'warn',
      );
    } catch (e) {
      console.error('[ImportUI]', e);
      _feel = { root: _controlRoot(), mood: 'minor', energy: 'medium',
                key: { root: 69, type: 'minor' } };
      if (btnRefPlay)  btnRefPlay.disabled  = false;
      if (btnGenerate) btnGenerate.disabled = false;
      _status(`Analysis error: ${e.message}`, 'err');
    } finally {
      setTimeout(() => _progress(0, false), 900);
    }
  }

  function _inferEnergy(notes) {
    if (!notes?.length) return 'medium';
    const avgVel = notes.reduce((s, n) => s + (n.velocity ?? 80), 0) / notes.length;
    if (avgVel > 92 && notes.length > 8) return 'high';
    if (avgVel < 68 || notes.length < 4) return 'low';
    return 'medium';
  }

  // ── Reference audio player ────────────────────────────────────────────────────
  btnRefPlay?.addEventListener('click', _toggleRef);

  function _toggleRef() {
    if (!audioRef || !_fileURL) return;
    if (_refPlaying) {
      _stopRef();
    } else {
      audioRef.play().catch(() => {});
      _refPlaying = true;
      if (btnRefPlay) btnRefPlay.textContent = '■';
      if (btnPlayBoth) btnPlayBoth.textContent = _loopPlaying ? '■ Both' : '▶ Both';
    }
  }

  function _stopRef() {
    if (audioRef) audioRef.pause();
    _refPlaying = false;
    if (btnRefPlay) btnRefPlay.textContent = '▶';
  }

  // Progress bar + time counter driven by audio events
  if (audioRef) {
    audioRef.addEventListener('timeupdate', () => {
      const dur = audioRef.duration || 1;
      const pct = (audioRef.currentTime / dur) * 100;
      if (refFill) refFill.style.width = `${pct}%`;
      if (refTime) refTime.textContent = _formatTime(audioRef.currentTime);
    });
    audioRef.addEventListener('ended', () => {
      _refPlaying = false;
      if (btnRefPlay) btnRefPlay.textContent = '▶';
      if (refFill) refFill.style.width = '0%';
      if (refTime) refTime.textContent = '0:00';
    });
    audioRef.addEventListener('pause', () => {
      if (btnRefPlay && _refPlaying) { /* intentional pause — don't reset button */ }
    });
  }

  // Click on reference track bar to seek
  refFill?.parentElement?.addEventListener('click', e => {
    if (!audioRef || !_fileURL) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const pct  = (e.clientX - rect.left) / rect.width;
    audioRef.currentTime = pct * (audioRef.duration || 0);
  });

  // ── Generated loop player ─────────────────────────────────────────────────────
  btnLoopPlay?.addEventListener('click', _toggleLoop);

  async function _toggleLoop() {
    if (!_generated || !window.LoopTransport?.hasLoop()) return;
    if (_loopPlaying) {
      _stopLoop();
    } else {
      await window.LoopTransport.start();
      _loopPlaying = true;
      if (btnLoopPlay) btnLoopPlay.textContent = '■';
      _startLoopAnim();
    }
  }

  function _stopLoop() {
    if (_loopPlaying && window.LoopTransport?.isPlaying()) {
      window.LoopTransport.stop();
    }
    _loopPlaying = false;
    if (btnLoopPlay) btnLoopPlay.textContent = '▶';
    _stopLoopAnim();
  }

  function _startLoopAnim() {
    function step() {
      if (!window.LoopTransport?.isPlaying()) {
        _loopPlaying = false;
        if (btnLoopPlay) btnLoopPlay.textContent = '▶';
        return;
      }
      const phase = window.LoopTransport.getPhase();
      if (loopFill) loopFill.style.width = `${phase * 100}%`;
      _loopRafId = requestAnimationFrame(step);
    }
    _loopRafId = requestAnimationFrame(step);
  }

  function _stopLoopAnim() {
    if (_loopRafId) { cancelAnimationFrame(_loopRafId); _loopRafId = null; }
    if (loopFill) loopFill.style.width = '0%';
  }

  // ── Play Both ─────────────────────────────────────────────────────────────────
  btnPlayBoth?.addEventListener('click', async () => {
    // If either is playing, stop both
    if (_refPlaying || _loopPlaying) {
      _stopRef();
      _stopLoop();
      if (btnPlayBoth) btnPlayBoth.textContent = '▶ Both';
      return;
    }
    // Start both from the top
    if (audioRef && _fileURL) {
      audioRef.currentTime = 0;
      audioRef.play().catch(() => {});
      _refPlaying = true;
      if (btnRefPlay) btnRefPlay.textContent = '■';
    }
    if (_generated && window.LoopTransport?.hasLoop()) {
      await window.LoopTransport.start();
      _loopPlaying = true;
      if (btnLoopPlay) btnLoopPlay.textContent = '■';
      _startLoopAnim();
    }
    if (btnPlayBoth) btnPlayBoth.textContent = '■ Both';
    // Stop "both" state when ref audio ends
    if (audioRef) {
      audioRef.addEventListener('ended', () => {
        if (btnPlayBoth) btnPlayBoth.textContent = '▶ Both';
      }, { once: true });
    }
  });

  // ── Generate ──────────────────────────────────────────────────────────────────
  btnGenerate?.addEventListener('click', _doGenerate);
  btnGenAgain?.addEventListener('click', _doGenerate);

  async function _doGenerate() {
    if (!_file) return;
    _stopLoop();
    if (btnGenerate) btnGenerate.disabled = true;
    if (btnGenAgain) btnGenAgain.disabled = true;
    _progress(0.4, true);
    _status('Generating interpretation…');

    const genre = document.getElementById('ctrl-genre')?.value ?? 'rage';
    const bars  = parseInt(document.getElementById('ctrl-bars')?.value ?? '4', 10);
    const bpm   = parseInt(document.getElementById('ctrl-bpm')?.value ?? '140', 10);
    const root  = _feel?.root ?? _controlRoot();
    const desc  = document.getElementById('input-describe')?.value?.trim() ?? '';
    const lead  = document.getElementById('ctrl-lead-inst')?.value ?? '';

    try {
      const res = await fetch('/api/loop/evolve', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          genre, root, bpm, bars,
          seed:            Math.floor(Math.random() * 99999),
          description:     desc || undefined,
          lead_instrument: lead || undefined,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      _progress(1.0, true);

      // Install in main engine
      if (typeof window._installLoop === 'function') {
        window._installLoop(data);
      }

      _generated = true;
      _showGenSection(data);
      _status('');

    } catch (e) {
      console.error('[ImportUI]', e);
      _status(`Error: ${e.message}`, 'err');
    } finally {
      if (btnGenerate) btnGenerate.disabled = false;
      if (btnGenAgain) btnGenAgain.disabled = false;
      setTimeout(() => _progress(0, false), 700);
    }
  }

  function _showGenSection(data) {
    if (genSection) genSection.hidden = false;
    if (btnPlayBoth) btnPlayBoth.hidden = false;
    if (btnGenAgain) btnGenAgain.hidden = false;

    // Fill detail line
    const scaleName = {
      rage: 'minor pent', pluggnb: 'nat. minor',
      dark_trap: 'phrygian', cloud: 'major pent',
    }[data.genre] ?? '';
    const instLabel = data.lead_instrument
      ? ` · ${data.lead_instrument.replace('_', ' ')}` : '';
    if (genDetail) {
      genDetail.innerHTML =
        `<span class="cmp-root">${data.root}</span>` +
        `<span class="cmp-label">${scaleName}${instLabel}</span>` +
        `<span class="cmp-label">${data.bpm} BPM · ${data.loop_length / 4}-bar</span>`;
    }
  }

  function _resetGenSection() {
    _generated = false;
    _stopLoop();
    if (genSection) genSection.hidden = true;
    if (btnPlayBoth) btnPlayBoth.hidden = true;
    if (btnGenAgain) btnGenAgain.hidden = true;
    if (genDetail) genDetail.innerHTML = '';
  }

  // ── State helpers ─────────────────────────────────────────────────────────────
  function _setState(state) {
    if (stateDrop)   stateDrop.hidden   = (state !== 'drop');
    if (stateLoaded) stateLoaded.hidden = (state !== 'loaded');
  }

  function _midiToRoot(pc) {
    return MIDI_ROOTS[((pc % 12) + 12) % 12] ?? 'A';
  }

  function _controlRoot() {
    return document.getElementById('ctrl-root')?.value ?? 'A';
  }

  function _formatTime(sec) {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  }

  function _progress(pct, visible) {
    if (!progressEl) return;
    if (visible !== undefined) progressEl.style.display = visible ? 'block' : 'none';
    if (progressBar) progressBar.style.width = `${Math.round(Math.min(1, pct) * 100)}%`;
  }

  function _status(msg, cls) {
    if (!statusEl) return;
    statusEl.textContent = msg;
    statusEl.className   = `import-status${cls ? ' ' + cls : ''}`;
  }
})();
