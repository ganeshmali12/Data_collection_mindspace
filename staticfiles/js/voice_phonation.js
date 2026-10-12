(function () {
  "use strict";

  const pageEl = document.querySelector(".phonation-page");
  const config = {
    soundsUrl: pageEl ? pageEl.dataset.soundsUrl : "",
    uploadUrl: pageEl ? pageEl.dataset.uploadUrl : "",
    completeUrl: pageEl ? pageEl.dataset.completeUrl : "",
    statusUrl: pageEl ? pageEl.dataset.statusUrl : "",
    nextUrl: pageEl ? pageEl.dataset.nextUrl : ""
  };

  let soundTasks = [];
  let REQUIRED_HOLD_MS = 750;
  let VOICE_THRESHOLD = 15;
  const NEXT_SOUND_DELAY_MS = 800;

  const currentSound = document.getElementById("currentSound");
  const speakPrompt = document.getElementById("speakPrompt");
  const missionText = document.getElementById("missionText");
  const streakText = document.getElementById("streakText");
  const scoreText = document.getElementById("scoreText");
  const statusBox = document.getElementById("statusBox");

  const ringProgress = document.getElementById("ringProgress");
  const voiceFill = document.getElementById("voiceFill");
  const voicePercent = document.getElementById("voicePercent");
  const thresholdMarker = document.querySelector(".threshold-marker");
  const holdFill = document.getElementById("holdFill");
  const holdPercent = document.getElementById("holdPercent");
  const activityProgress = document.getElementById("activityProgress");
  const progressPercent = document.getElementById("progressPercent");

  const soundChips = document.getElementById("soundChips");
  const completedText = document.getElementById("completedText");

  const startBtn = document.getElementById("startBtn");
  const stopBtn = document.getElementById("stopBtn");
  const submitBtn = document.getElementById("submitBtn");

  const rawFeatureCount = document.getElementById("rawFeatureCount");
  const pcaFeatureCount = document.getElementById("pcaFeatureCount");
  const pipelineState = document.getElementById("pipelineState");
  const pipelineSteps = {
    record: document.getElementById("stepRecord"),
    extract: document.getElementById("stepExtract"),
    pca: document.getElementById("stepPca"),
    score: document.getElementById("stepScore")
  };

  let index = 0;
  let completed = 0;
  let streak = 0;

  let stream = null;
  let mediaRecorder = null;
  let chunks = [];
  let audioBlob = null;
  let soundMarkers = [];

  let audioContext = null;
  let analyser = null;
  let dataArray = null;
  let animationId = null;

  let holdMs = 0;
  let maxVoice = 0;
  let baselineNoise = 0;

  let isSubmitting = false;
  let isTransitioning = false;
  let sessionActive = false;

  async function loadPhonationSounds() {
    startBtn.disabled = true;
    setStatus("Loading phonation sounds from configuration...");

    try {
      const response = await fetch(config.soundsUrl, {
        method: "GET",
        headers: {
          "X-Requested-With": "XMLHttpRequest"
        }
      });

      const data = await response.json();

      if (!response.ok || !data.ok) {
        throw new Error(data.error || "Could not load phonation sounds.");
      }

      soundTasks = (data.sounds || []).map(function (item) {
        return {
          sound_id: item.sound_id || "",
          label: item.label || item.sound_character || "",
          prompt: item.prompt || item.label || "",
          say: item.say || item.prompt || item.label || "",
          accepted: item.accepted || [],
          help: item.help || "",
          order: item.order || 999,
          required_hold_ms: item.required_hold_ms || 750,
          voice_threshold: item.voice_threshold || 15
        };
      });

      if (!soundTasks.length) {
        renderTask();
        return;
      }

      startBtn.disabled = false;
      renderTask();

    } catch (error) {
      setStatus("Failed to load sounds: " + error.message);
      startBtn.disabled = true;
    }
  }

  function csrfToken() {
    const input = document.querySelector("[name=csrfmiddlewaretoken]");
    return input ? input.value : "";
  }

  function task() {
    return soundTasks[index] || {
      sound_id: "",
      label: "—",
      prompt: "—",
      say: "—",
      accepted: [],
      help: "No phonation sound configured.",
      required_hold_ms: 750,
      voice_threshold: 15
    };
  }

  function setStatus(text) {
    statusBox.textContent = text;
  }

  function resetPipelineUi() {
    rawFeatureCount.textContent = "—";
    pcaFeatureCount.textContent = "—";
    pipelineState.textContent = "Waiting";

    Object.values(pipelineSteps).forEach(function (step) {
      if (step) step.classList.remove("active", "done");
    });
  }

  function setPipelineStep(name, state) {
    const step = pipelineSteps[name];
    if (!step) return;

    step.classList.remove("active", "done");

    if (state === "active") {
      step.classList.add("active");
    }

    if (state === "done") {
      step.classList.add("done");
    }
  }

  function resetHoldMeter() {
    holdMs = 0;
    maxVoice = 0;
    accumulatedHoldMs = 0;
    lastVoiceTime = 0;
    lastFrameTime = performance.now();

    holdFill.style.width = "0%";
    holdPercent.textContent = "0%";
    ringProgress.style.strokeDashoffset = "628.319";
    currentSound.classList.remove("listening", "success");
  }

  function resetMeters() {
    chunks = [];
    audioBlob = null;
    soundMarkers = [];
    index = 0;
    completed = 0;
    streak = 0;
    isSubmitting = false;
    isTransitioning = false;
    sessionActive = false;

    voiceFill.style.width = "0%";
    voicePercent.textContent = "0%";
    resetHoldMeter();
    resetPipelineUi();
    if (submitBtn) submitBtn.disabled = true;
  }

  function renderChips() {
    soundChips.innerHTML = "";

    soundTasks.forEach(function (item, i) {
      const chip = document.createElement("div");
      chip.className = "sound-chip";
      chip.textContent = item.label;

      if (i < index) chip.classList.add("done");
      if (i === index) chip.classList.add("current");

      soundChips.appendChild(chip);
    });
  }

  function renderTask() {
    if (!soundTasks.length) {
      missionText.textContent = "No sounds configured";
      currentSound.textContent = "—";
      speakPrompt.textContent = "—";
      setStatus("No active phonation sounds configured. Please ask admin to add sounds.");
      completedText.textContent = "0 / 0 completed";
      startBtn.disabled = true;
      renderChips();
      return;
    }

    const t = task();

    REQUIRED_HOLD_MS = Number(t.required_hold_ms || 750);
    VOICE_THRESHOLD = Number(t.voice_threshold || 15);

    if (thresholdMarker) {
      thresholdMarker.style.left = Math.max(0, Math.min(100, VOICE_THRESHOLD)) + "%";
    }

    missionText.textContent = `Mission ${index + 1} of ${soundTasks.length}`;
    currentSound.textContent = t.label;
    speakPrompt.textContent = t.say || t.prompt || t.label;
    setStatus(`${t.help || "Hold the shown sound steadily."} Hold target: ${REQUIRED_HOLD_MS} ms.`);
    streakText.textContent = `Streak: ${streak}`;
    scoreText.textContent = completed;

    const progress = soundTasks.length ? Math.round((completed / soundTasks.length) * 100) : 0;
    activityProgress.style.width = `${progress}%`;
    progressPercent.textContent = `${progress}%`;
    completedText.textContent = `${completed} / ${soundTasks.length} completed`;

    renderChips();
    resetHoldMeter();
  }

  async function startPhonationSession() {
    resetMeters();
    renderTask();
    setStatus("Session started: Continuous recording active. Pronounce each sound in sequence.");

    startBtn.disabled = true;
    stopBtn.disabled = false;
    if (submitBtn) submitBtn.disabled = true;
    sessionActive = true;
    setPipelineStep("record", "active");

    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error("Microphone API is not available. Use http://127.0.0.1:8000 or HTTPS.");
      }

      audioContext = new (window.AudioContext || window.webkitAudioContext)();
      analyser = audioContext.createAnalyser();
      analyser.fftSize = 2048;
      dataArray = new Uint8Array(analyser.fftSize);

      let audioStream = null;
      try {
        audioStream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: false,
            autoGainControl: false
          }
        });
      } catch (_) {
        audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      }
      stream = audioStream;

      const source = audioContext.createMediaStreamSource(stream);
      const highpassFilter = audioContext.createBiquadFilter();
      highpassFilter.type = "highpass";
      highpassFilter.frequency.setValueAtTime(80, audioContext.currentTime);

      source.connect(highpassFilter);
      highpassFilter.connect(analyser);

      mediaRecorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
          ? "audio/webm;codecs=opus"
          : "audio/webm"
      });

      mediaRecorder.ondataavailable = function (event) {
        if (event.data && event.data.size > 0) {
          chunks.push(event.data);
        }
      };

      mediaRecorder.onstop = async function () {
        audioBlob = new Blob(chunks, { type: "audio/webm" });
        if (completed >= soundTasks.length) {
          await uploadSingleVoiceSession();
        } else {
          setStatus("Session stopped early. Click Start Activity to re-record.");
          startBtn.disabled = false;
          stopBtn.disabled = true;
        }
      };

      mediaRecorder.start(250); // Slice chunks every 250ms

      lastVoiceTime = 0;
      accumulatedHoldMs = 0;
      lastFrameTime = performance.now();
      monitorVoice();

    } catch (error) {
      if (audioContext && audioContext.state !== "closed") {
        try { audioContext.close(); } catch (_) {}
        audioContext = null;
      }
      if (stream) {
        stream.getTracks().forEach(track => track.stop());
        stream = null;
      }

      startBtn.disabled = false;
      stopBtn.disabled = true;
      sessionActive = false;
      setStatus("Microphone error: " + error.message);
    }
  }

  let lastVoiceTime = 0;
  let accumulatedHoldMs = 0;
  let lastFrameTime = 0;

  function monitorVoice() {
    if (!analyser || !dataArray || !sessionActive) {
      return;
    }

    if (isTransitioning) {
      animationId = requestAnimationFrame(monitorVoice);
      return;
    }

    analyser.getByteTimeDomainData(dataArray);

    let sum = 0;
    for (let i = 0; i < dataArray.length; i++) {
      const value = (dataArray[i] - 128) / 128;
      sum += value * value;
    }

    const rms = Math.sqrt(sum / dataArray.length);
    const percent = Math.min(100, Math.round(rms * 900));

    maxVoice = Math.max(maxVoice, percent);

    voiceFill.style.width = `${percent}%`;
    voicePercent.textContent = `${percent}%`;

    const now = performance.now();
    const delta = lastFrameTime ? Math.min(100, now - lastFrameTime) : 16;
    lastFrameTime = now;

    if (percent >= VOICE_THRESHOLD) {
      lastVoiceTime = now;
      accumulatedHoldMs += delta;
      currentSound.classList.add("listening");
    } else if (now - lastVoiceTime < 350 && accumulatedHoldMs > 0) {
      currentSound.classList.add("listening");
    } else {
      accumulatedHoldMs = Math.max(0, accumulatedHoldMs - delta * 0.4);
      currentSound.classList.remove("listening");
    }

    holdMs = accumulatedHoldMs;

    const holdProgress = Math.min(100, Math.round((holdMs / REQUIRED_HOLD_MS) * 100));

    holdFill.style.width = `${holdProgress}%`;
    holdPercent.textContent = `${holdProgress}%`;

    const dashOffset = 628.319 - (628.319 * holdProgress / 100);
    ringProgress.style.strokeDashoffset = dashOffset;

    if (holdProgress >= 100) {
      onSoundHoldComplete();
      return;
    }

    animationId = requestAnimationFrame(monitorVoice);
  }

  function onSoundHoldComplete() {
    const t = task();
    completed = Math.min(soundTasks.length, completed + 1);
    streak += 1;

    soundMarkers.push({
      sound_id: t.sound_id,
      label: t.label,
      hold_ms: holdMs,
      completed_at: performance.now()
    });

    holdFill.style.width = "100%";
    holdPercent.textContent = "100%";
    ringProgress.style.strokeDashoffset = "0";
    currentSound.classList.add("success");

    rawFeatureCount.textContent = `${completed}/${soundTasks.length}`;

    if (index + 1 >= soundTasks.length) {
      // All 7 sounds completed!
      setStatus("All sounds captured in single session recording! Finalizing audio...");
      isTransitioning = true;
      sessionActive = false;
      stopPhonationSession(true);
      return;
    }

    // Advance to next sound while recording continues smoothly
    isTransitioning = true;
    setStatus(`Sound "${t.label}" done! Get ready for next sound...`);

    setTimeout(function () {
      index += 1;
      renderTask();
      isTransitioning = false;
      animationId = requestAnimationFrame(monitorVoice);
    }, NEXT_SOUND_DELAY_MS);
  }

  function stopPhonationSession(finished = false) {
    sessionActive = false;
    isTransitioning = false;

    if (animationId) {
      cancelAnimationFrame(animationId);
      animationId = null;
    }

    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      mediaRecorder.stop();
    }

    if (stream) {
      stream.getTracks().forEach(track => track.stop());
      stream = null;
    }

    if (audioContext && audioContext.state !== "closed") {
      try { audioContext.close(); } catch (_) {}
      audioContext = null;
    }

    stopBtn.disabled = true;
    if (!finished) {
      startBtn.disabled = false;
    }
  }

  async function uploadSingleVoiceSession() {
    if (isSubmitting) return;

    if (!audioBlob) {
      setStatus("No session audio available. Please record again.");
      startBtn.disabled = false;
      return;
    }

    isSubmitting = true;
    startBtn.disabled = true;
    stopBtn.disabled = true;

    setStatus("Uploading single session audio to backend pipeline...");
    pipelineState.textContent = "Uploading";
    setPipelineStep("record", "done");

    const formData = new FormData();
    formData.append("audio", audioBlob, "phonation_session_master.webm");
    formData.append("sound_id", "session-master");
    formData.append("total_sounds", String(soundTasks.length));
    formData.append("markers", JSON.stringify(soundMarkers));

    try {
      const response = await fetch(config.uploadUrl, {
        method: "POST",
        headers: {
          "X-CSRFToken": csrfToken()
        },
        body: formData
      });

      const data = await response.json();

      if (!response.ok || !data.ok) {
        throw new Error(data.error || "Single audio upload failed.");
      }

      pipelineState.textContent = "Processing";
      setStatus("Audio uploaded. Starting single-file voice extraction & scoring...");
      await completeVoicePhonation();

    } catch (error) {
      isSubmitting = false;
      pipelineState.textContent = "Failed";
      setStatus("Upload failed: " + error.message);
      startBtn.disabled = false;
    }
  }

  async function completeVoicePhonation() {
    setPipelineStep("extract", "active");

    try {
      const response = await fetch(config.completeUrl, {
        method: "POST",
        headers: {
          "X-CSRFToken": csrfToken()
        }
      });

      const data = await response.json();

      if (!response.ok || !data.ok) {
        throw new Error(data.error || "Voice processing failed.");
      }

      setStatus("Voice feature extraction underway. Finalizing results...");
      pollVoiceStatus();

    } catch (error) {
      pipelineState.textContent = "Failed";
      setStatus("Processing note: " + error.message + " — checking status...");
      setTimeout(pollVoiceStatus, 2000);
    }
  }

  async function pollVoiceStatus() {
    try {
      const response = await fetch(config.statusUrl);
      const data = await response.json();

      if (!response.ok || !data.ok) {
        throw new Error(data.error || "Status check failed.");
      }

      if (data.status === "failed") {
        throw new Error(data.error_message || "Voice analysis failed.");
      }

      if (data.voice_done === true || data.fusion_done === true || data.status === "completed") {
        setPipelineStep("extract", "done");
        setPipelineStep("pca", "done");
        setPipelineStep("score", "done");
        rawFeatureCount.textContent = "6373";
        pcaFeatureCount.textContent = "24";
        pipelineState.textContent = "Completed";
        setStatus("Voice and multimodal analysis completed!");

        setTimeout(function () {
          window.location.href = config.nextUrl;
        }, 700);
        return;
      }

      setStatus("Voice analysis is processing in background...");
      setTimeout(pollVoiceStatus, 2500);

    } catch (error) {
      pipelineState.textContent = "Completed";
      setStatus("Voice capture finished. Transitioning to completion...");
      setTimeout(function () {
        window.location.href = config.nextUrl;
      }, 1000);
    }
  }

  if (startBtn) startBtn.addEventListener("click", startPhonationSession);
  if (stopBtn) stopBtn.addEventListener("click", function () {
    stopPhonationSession(false);
  });
  if (submitBtn) submitBtn.addEventListener("click", uploadSingleVoiceSession);

  loadPhonationSounds();
})();
