/**
 * Ops Voice Co-Pilot — client.
 * WebSocket /ws/live/voice: PCM 16 kHz in, 24 kHz out; JSON for transcript and image.
 * Optional session memory: persist conversation and referenced screen across reloads.
 * When UI is loaded from another host (e.g. static site), an optional config.json can provide gateway_ws_base so Connect (Voice) works.
 */
(function () {
  const VOICE_IN_RATE = 16000;
  const VOICE_OUT_RATE = 24000;
  function getWsVoiceUrl() {
    if (window.GATEWAY_WS_BASE) return window.GATEWAY_WS_BASE + '/ws/live/voice';
    return (location.protocol === 'https:' ? 'wss:' : 'ws:') + '//' + location.host + '/ws/live/voice';
  }

  const SESSION_STORAGE_KEY = 'opsvoice_session';
  const SESSION_MEMORY_ENABLED_KEY = 'opsvoice_session_memory_enabled';
  const MAX_TRANSCRIPT_ENTRIES = 50;
  const MAX_IMAGE_B64_BYTES = 1500000; // ~1.5MB to stay under localStorage limits

  let voiceWs = null;
  let voiceMicStream = null;
  let voiceCaptureContext = null;
  let voiceCaptureNode = null;
  let voicePlaybackContext = null;
  let voiceNextPlayTime = 0;
  let currentImageData = null;

  let sessionTranscript = []; // in-memory transcript for persistence

  const previewArea = document.getElementById('preview-area');
  const previewPlaceholder = document.getElementById('preview-placeholder');
  const previewImg = document.getElementById('preview-img');
  const fileInput = document.getElementById('file-input');
  const btnPaste = document.getElementById('btn-paste');
  const btnSendImage = document.getElementById('btn-send-image');
  const btnVoiceConnect = document.getElementById('btn-voice-connect');
  const btnVoiceMic = document.getElementById('btn-voice-mic');
  const voiceStatus = document.getElementById('voice-status');
  const voiceTranscript = document.getElementById('voice-transcript');
  const sessionMemoryToggle = document.getElementById('session-memory-toggle');

  const debugPanel = document.getElementById('debug-panel');
  const debugWsUrl = document.getElementById('debug-ws-url');
  const debugState = document.getElementById('debug-state');
  const debugLastError = document.getElementById('debug-last-error');
  let lastError = '';
  let sessionState = 'disconnected'; // connecting | connected | disconnected

  if (new URLSearchParams(location.search).get('debug') === '1' && debugPanel) {
    debugPanel.classList.remove('hidden');
  }

  function updateDebugPanel() {
    if (!debugPanel || debugPanel.classList.contains('hidden')) return;
    if (debugWsUrl) debugWsUrl.textContent = getWsVoiceUrl();
    if (debugState) debugState.textContent = sessionState;
    if (debugLastError) debugLastError.textContent = lastError || '—';
  }

  // Gateway WebSocket base: ?gateway=... or localStorage or config.json (GCS)
  (function () {
    var params = new URLSearchParams(location.search);
    var q = params.get('gateway');
    if (q) {
      var base = q.replace(/^https:\/\//i, 'wss://').replace(/^http:\/\//i, 'ws://').replace(/\/+$/, '');
      window.GATEWAY_WS_BASE = base;
      try { localStorage.setItem('opsvoice_gateway_url', q); } catch (_) {}
      return;
    }
    try {
      var saved = localStorage.getItem('opsvoice_gateway_url');
      if (saved) {
        var base = saved.replace(/^https:\/\//i, 'wss://').replace(/^http:\/\//i, 'ws://').replace(/\/+$/, '');
        window.GATEWAY_WS_BASE = base;
        return;
      }
    } catch (_) {}
    fetch('config.json').then(function (r) { return r.json(); }).then(function (c) {
      if (c && c.gateway_ws_base) window.GATEWAY_WS_BASE = c.gateway_ws_base;
      if (typeof updateDebugPanel === 'function') updateDebugPanel();
    }).catch(function () {});
  })();
  if (debugPanel && !debugPanel.classList.contains('hidden')) updateDebugPanel();

  function isSessionMemoryEnabled() {
    return sessionMemoryToggle && sessionMemoryToggle.checked;
  }

  function loadSessionFromStorage() {
    try {
      const raw = localStorage.getItem(SESSION_STORAGE_KEY);
      if (!raw) return null;
      return JSON.parse(raw);
    } catch (_) {
      return null;
    }
  }

  function saveSessionToStorage() {
    if (!isSessionMemoryEnabled()) return;
    try {
      const payload = {
        transcript: sessionTranscript.slice(-MAX_TRANSCRIPT_ENTRIES),
        image: null,
      };
      if (currentImageData && currentImageData.data) {
        const b64Len = currentImageData.data.length;
        if (b64Len <= MAX_IMAGE_B64_BYTES) {
          payload.image = { data: currentImageData.data, mime_type: currentImageData.mime_type || 'image/jpeg' };
        }
      }
      localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(payload));
    } catch (_) {}
  }

  function restoreSession() {
    if (!isSessionMemoryEnabled()) return;
    const session = loadSessionFromStorage();
    if (!session) return;
    // Restore transcript (may be empty for follow-up-after-reload)
    sessionTranscript = Array.isArray(session.transcript) ? session.transcript : [];
    for (let i = 0; i < sessionTranscript.length; i++) {
      const e = sessionTranscript[i];
      appendTranscriptDOM(e.type, e.text);
    }
    // Restore referenced screen so follow-up questions can use it across reloads
    if (session.image && session.image.data) {
      currentImageData = { data: session.image.data, mime_type: session.image.mime_type || 'image/jpeg' };
      const dataUrl = 'data:' + (session.image.mime_type || 'image/jpeg') + ';base64,' + session.image.data;
      previewImg.src = dataUrl;
      previewImg.classList.remove('hidden');
      previewPlaceholder.classList.add('hidden');
      btnSendImage.disabled = false;
      showSessionRestoredHint();
    }
    voiceTranscript.scrollTop = voiceTranscript.scrollHeight;
  }

  function showSessionRestoredHint() {
    const hint = document.getElementById('session-restored-hint');
    if (!hint) return;
    hint.classList.remove('hidden');
    setTimeout(function () { hint.classList.add('hidden'); }, 6000);
  }

  function appendTranscriptDOM(type, text) {
    const div = document.createElement('div');
    div.className = 'transcript-msg ' + type;
    const label = type === 'user' ? 'You: ' : type === 'error' ? 'Error: ' : 'Co-pilot: ';
    div.textContent = label + text;
    voiceTranscript.appendChild(div);
    voiceTranscript.scrollTop = voiceTranscript.scrollHeight;
  }

  function appendTranscript(type, text) {
    appendTranscriptDOM(type, text);
    if (isSessionMemoryEnabled()) {
      sessionTranscript.push({ type: type, text: text });
      saveSessionToStorage();
    }
  }

  function setPreviewFromBlob(blob) {
    if (!blob) return;
    const url = URL.createObjectURL(blob);
    previewImg.src = url;
    previewImg.classList.remove('hidden');
    previewPlaceholder.classList.add('hidden');
    const reader = new FileReader();
    reader.onload = function () {
      const b64 = reader.result.split(',')[1] || '';
      currentImageData = { data: b64, mime_type: 'image/jpeg' };
      btnSendImage.disabled = false;
      if (isSessionMemoryEnabled()) saveSessionToStorage();
    };
    reader.readAsDataURL(blob);
  }

  fileInput.addEventListener('change', function () {
    const f = fileInput.files && fileInput.files[0];
    if (f && f.type.startsWith('image/')) setPreviewFromBlob(f);
    fileInput.value = '';
  });

  btnPaste.addEventListener('click', async function () {
    try {
      const clipboard = await navigator.clipboard.read();
      for (const item of clipboard) {
        const blob = await item.getType('image/png') || await item.getType('image/jpeg');
        if (blob) {
          setPreviewFromBlob(blob);
          return;
        }
      }
      alert('No image in clipboard. Copy an image first.');
    } catch (e) {
      alert('Clipboard access failed: ' + e.message);
    }
  });

  const proactiveAlertsToggle = document.getElementById('proactive-alerts-toggle');
  btnSendImage.addEventListener('click', function () {
    if (!currentImageData || !voiceWs || voiceWs.readyState !== WebSocket.OPEN) {
      if (!voiceWs || voiceWs.readyState !== WebSocket.OPEN) alert('Connect (Voice) first, then send image.');
      return;
    }
    const proactive = proactiveAlertsToggle && proactiveAlertsToggle.checked;
    voiceWs.send(JSON.stringify({
      type: 'image',
      data: currentImageData.data,
      mime_type: currentImageData.mime_type,
      proactive: proactive,
    }));
    if (!proactive) {
      appendTranscript('agent', '(Image received. You can ask: "Why did this break?" or "What\'s this spike?")');
    }
    saveSessionToStorage();
  });

  btnVoiceConnect.addEventListener('click', function () {
    if (voiceWs && voiceWs.readyState === WebSocket.OPEN) {
      voiceWs.close();
      return;
    }
    sessionState = 'connecting';
    voiceStatus.textContent = 'Connecting…';
    voiceStatus.classList.remove('connected');
    updateDebugPanel();
    voiceWs = new WebSocket(getWsVoiceUrl());
    voiceWs.binaryType = 'arraybuffer';
    voiceWs.onopen = function () {
      sessionState = 'connected';
      lastError = '';
      voiceStatus.textContent = 'Connected';
      voiceStatus.classList.add('connected');
      updateDebugPanel();
      btnVoiceConnect.textContent = 'Disconnect (Voice)';
      btnVoiceMic.disabled = false;
      // Re-send referenced screen so follow-up questions after reload are grounded in the same context
      if (currentImageData && currentImageData.data) {
        try {
          voiceWs.send(JSON.stringify({
            type: 'image',
            data: currentImageData.data,
            mime_type: currentImageData.mime_type || 'image/jpeg',
            proactive: false,
          }));
        } catch (_) {}
      }
    };
    voiceWs.onerror = function () {
      sessionState = 'disconnected';
      lastError = 'WebSocket failed. Use the Gateway URL from Terraform (gateway_url) or add ?gateway=https://YOUR_GATEWAY_URL';
      voiceStatus.textContent = 'Disconnected';
      appendTranscript('error', lastError);
      updateDebugPanel();
    };
    voiceWs.onclose = function () {
      sessionState = 'disconnected';
      voiceStatus.textContent = 'Disconnected';
      updateDebugPanel();
      voiceStatus.classList.remove('connected');
      btnVoiceConnect.textContent = 'Connect (Voice)';
      btnVoiceMic.disabled = true;
      btnVoiceMic.textContent = 'Start mic';
      if (voiceMicStream) {
        voiceMicStream.getTracks().forEach(function (t) { t.stop(); });
        voiceMicStream = null;
      }
      voiceWs = null;
    };
    voiceWs.onmessage = function (ev) {
      if (ev.data instanceof ArrayBuffer) {
        const samples = new Int16Array(ev.data);
        if (!voicePlaybackContext) voicePlaybackContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: VOICE_OUT_RATE });
        const ctx = voicePlaybackContext;
        const buffer = ctx.createBuffer(1, samples.length, VOICE_OUT_RATE);
        const channel = buffer.getChannelData(0);
        for (let i = 0; i < samples.length; i++) channel[i] = samples[i] / 32768;
        const source = ctx.createBufferSource();
        source.buffer = buffer;
        source.connect(ctx.destination);
        if (voiceNextPlayTime < ctx.currentTime) voiceNextPlayTime = ctx.currentTime;
        source.start(voiceNextPlayTime);
        voiceNextPlayTime += buffer.duration;
      } else {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === 'user' && msg.text) appendTranscript('user', msg.text);
          else if (msg.type === 'gemini' && msg.text) appendTranscript('agent', msg.text);
          else if (msg.type === 'error') {
            lastError = msg.error || msg.message || 'Error';
            appendTranscript('error', lastError);
            updateDebugPanel();
          }
        } catch (_) {}
      }
    };
  });

  if (sessionMemoryToggle) {
    try {
      const enabled = localStorage.getItem(SESSION_MEMORY_ENABLED_KEY);
      sessionMemoryToggle.checked = enabled === 'true';
    } catch (_) {}
    sessionMemoryToggle.addEventListener('change', function () {
      try {
        localStorage.setItem(SESSION_MEMORY_ENABLED_KEY, sessionMemoryToggle.checked ? 'true' : 'false');
        if (!sessionMemoryToggle.checked) {
          localStorage.removeItem(SESSION_STORAGE_KEY);
          sessionTranscript = [];
        } else {
          saveSessionToStorage();
        }
      } catch (_) {}
    });
  }

  restoreSession();

  btnVoiceMic.addEventListener('click', async function () {
    if (voiceMicStream) {
      voiceMicStream.getTracks().forEach(function (t) { t.stop(); });
      voiceMicStream = null;
      if (voiceCaptureNode) try { voiceCaptureNode.disconnect(); } catch (_) {}
      btnVoiceMic.textContent = 'Start mic';
      return;
    }
    if (!voiceWs || voiceWs.readyState !== WebSocket.OPEN) {
      alert('Connect (Voice) first');
      return;
    }
    try {
      voiceMicStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const sampleRate = 48000;
      voiceCaptureContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: sampleRate });
      const source = voiceCaptureContext.createMediaStreamSource(voiceMicStream);
      const bufferSize = 4096;
      voiceCaptureNode = voiceCaptureContext.createScriptProcessor(bufferSize, 1, 1);
      voiceCaptureNode.onaudioprocess = function (e) {
        if (!voiceWs || voiceWs.readyState !== WebSocket.OPEN) return;
        const input = e.inputBuffer.getChannelData(0);
        const ratio = voiceCaptureContext.sampleRate / VOICE_IN_RATE;
        const outLen = Math.floor(input.length / ratio);
        const out = new Int16Array(outLen);
        for (let i = 0; i < outLen; i++) {
          const v = input[Math.floor(i * ratio)] * 32767;
          out[i] = Math.max(-32768, Math.min(32767, v));
        }
        voiceWs.send(out.buffer);
      };
      source.connect(voiceCaptureNode);
      voiceCaptureNode.connect(voiceCaptureContext.destination);
      btnVoiceMic.textContent = 'Stop mic';
    } catch (err) {
      alert('Microphone error: ' + err.message);
    }
  });
})();
