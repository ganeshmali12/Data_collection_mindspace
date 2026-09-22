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
  let REQUIRED_HOLD_MS = 1500;
  let VOICE_THRESHOLD = 32;
  const AUTO_SUBMIT_AFTER_HOLD = true;
  const AUTO_CONTINUE_NEXT_SOUND = true;
  const NEXT_SOUND_DELAY_MS = 900;

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

  let audioContext = null;
  let analyser = null;
  let dataArray = null;
  let animationId = null;

  let holdStart = null;
  let holdMs = 0;
  let maxVoice = 0;
  let baselineNoise = 0;

  let holdCompleted = false;
  let autoSubmitPending = false;
  let isSubmitting = false;


  async function loadPhonationSounds() {
    startBtn.disabled = true;
    setStatus("Loading phonation sounds from admin configuration...");

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
          required_hold_ms: item.required_hold_ms || 1500,
          voice_threshold: item.voice_threshold || 32
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
      required_hold_ms: 1500,
      voice_threshold: 32
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
      step.classList.remove("active", "done");
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

  function resetMeters() {
    holdStart = null;
    holdMs = 0;
    maxVoice = 0;
    audioBlob = null;
    chunks = [];

    holdCompleted = false;
    autoSubmitPending = false;
    isSubmitting = false;

    voiceFill.style.width = "0%";
    voicePercent.textContent = "0%";
    holdFill.style.width = "0%";
    holdPercent.textContent = "0%";
    ringProgress.style.strokeDashoffset = "628.319";

    currentSound.classList.remove("listening", "success");
    resetPipelineUi();
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
      resetMeters();
      return;
    }

    const t = task();

    REQUIRED_HOLD_MS = Number(t.required_hold_ms || 1500);
    VOICE_THRESHOLD = Number(t.voice_threshold || 32);

    if (thresholdMarker) {
      thresholdMarker.style.left = Math.max(0, Math.min(100, VOICE_THRESHOLD)) + "%";
    }

    missionText.textContent = `Mission ${index + 1} of ${soundTasks.length}`;
    currentSound.textContent = t.label;
    speakPrompt.textContent = t.say || t.prompt || t.label;
    setStatus(`${t.help || "Press Start Activity once. Manovedh will capture sounds automatically."} Voice threshold: ${VOICE_THRESHOLD}%, hold: ${REQUIRED_HOLD_MS} ms.`);
    streakText.textContent = `Streak: ${streak}`;
    scoreText.textContent = completed;

    const progress = soundTasks.length ? Math.round((completed / soundTasks.length) * 100) : 0;
    activityProgress.style.width = `${progress}%`;
    progressPercent.textContent = `${progress}%`;
    completedText.textContent = `${completed} / ${soundTasks.length} completed`;

    renderChips();
    resetMeters();
  }

  async function startSound() {
    resetMeters();
    setStatus("Listening... hold the shown vocal sound until the circle completes.");

    startBtn.disabled = true;
    stopBtn.disabled = false;
    submitBtn.disabled = true;

    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error("Microphone API is not available. Use http://127.0.0.1:8000 or HTTPS.");
      }

      // Create AudioContext BEFORE awaiting getUserMedia so it stays
      // within the user gesture. Chrome suspends AudioContexts created
      // after an await, causing getByteTimeDomainData to return silence.
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
      analyser = audioContext.createAnalyser();
      analyser.fftSize = 2048;
      dataArray = new Uint8Array(analyser.fftSize);

      stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      const source = audioContext.createMediaStreamSource(stream);
      source.connect(analyser);

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

      mediaRecorder.onstop = function () {
        audioBlob = new Blob(chunks, { type: "audio/webm" });

        if (holdMs >= REQUIRED_HOLD_MS) {
          submitBtn.disabled = false;
          currentSound.classList.add("success");

          if (autoSubmitPending && AUTO_SUBMIT_AFTER_HOLD) {
            setStatus("Uploading to backend pipeline...");
            setTimeout(function () {
              submitSound();
            }, 300);
          } else {
            setStatus("Sound recorded. Submit for backend pipeline.");
          }
        } else {
          submitBtn.disabled = true;
          startBtn.disabled = false;
          setStatus("Hold time too short. Try again.");
        }
      };

      mediaRecorder.start();

      monitorVoice();

    } catch (error) {
      // Clean up AudioContext if getUserMedia or setup failed
      if (audioContext && audioContext.state !== "closed") {
        try { audioContext.close(); } catch (_) {}
        audioContext = null;
        analyser = null;
        dataArray = null;
      }
      if (stream) {
        stream.getTracks().forEach(track => track.stop());
        stream = null;
      }

      startBtn.disabled = false;
      stopBtn.disabled = true;
      setStatus("Microphone permission failed: " + error.message);
    }
  }

  function monitorVoice() {
    if (!analyser || !dataArray || holdCompleted) {
      return;
    }

    analyser.getByteTimeDomainData(dataArray);

    let sum = 0;

    for (let i = 0; i < dataArray.length; i++) {
      const value = (dataArray[i] - 128) / 128;
      sum += value * value;
    }

    const rms = Math.sqrt(sum / dataArray.length);
    const percent = Math.min(100, Math.round(rms * 450));

    maxVoice = Math.max(maxVoice, percent);

    voiceFill.style.width = `${percent}%`;
    voicePercent.textContent = `${percent}%`;

    if (percent >= VOICE_THRESHOLD) {
      if (!holdStart) {
        holdStart = Date.now();
      }

      holdMs = Date.now() - holdStart;
      currentSound.classList.add("listening");
    } else {
      holdStart = null;
      currentSound.classList.remove("listening");
    }

    const holdProgress = Math.min(100, Math.round((holdMs / REQUIRED_HOLD_MS) * 100));

    holdFill.style.width = `${holdProgress}%`;
    holdPercent.textContent = `${holdProgress}%`;

    const dashOffset = 628.319 - (628.319 * holdProgress / 100);
    ringProgress.style.strokeDashoffset = dashOffset;

    if (holdProgress >= 100) {
      holdCompleted = true;
      autoSubmitPending = true;

      holdFill.style.width = "100%";
      holdPercent.textContent = "100%";
      ringProgress.style.strokeDashoffset = "0";
      currentSound.classList.add("success");

      setStatus(`Good hold completed at ${VOICE_THRESHOLD}% for ${REQUIRED_HOLD_MS} ms. Auto-submitting...`);

      stopSound(true);
      return;
    }

    animationId = requestAnimationFrame(monitorVoice);
  }

  function stopSound(autoSubmit = false) {
    try {
      if (animationId) {
        cancelAnimationFrame(animationId);
        animationId = null;
      }

      if (mediaRecorder && mediaRecorder.state !== "inactive") {
        autoSubmitPending = autoSubmit;
        mediaRecorder.stop();
      }

      if (stream) {
        stream.getTracks().forEach(track => track.stop());
        stream = null;
      }

      if (audioContext && audioContext.state !== "closed") {
        audioContext.close();
        audioContext = null;
      }
    } catch (error) {
      setStatus("Stop failed: " + error.message);
    }

    stopBtn.disabled = true;

    if (!autoSubmit) {
      startBtn.disabled = false;
    }
  }

  async function submitSound() {
    if (isSubmitting) return;

    if (!audioBlob) {
      setStatus("No audio found. Record again.");
      startBtn.disabled = false;
      return;
    }

    isSubmitting = true;
    submitBtn.disabled = true;
    startBtn.disabled = true;
    stopBtn.disabled = true;

    setStatus("Saving this sound...");
    pipelineState.textContent = "Saving";
    setPipelineStep("record", "done");

    const t = task();

    const formData = new FormData();
    formData.append("audio", audioBlob, `phonation-${index + 1}-${t.prompt || t.label}.webm`);
    formData.append("sound_id", t.sound_id || "");
    formData.append("expected_label", t.label);
    formData.append("expected_prompt", t.prompt);
    formData.append("accepted_values", JSON.stringify(t.accepted || []));
    formData.append("volume_score", String(maxVoice));
    formData.append("hold_ms", String(holdMs));
    formData.append("baseline_noise_level", String(baselineNoise));

    try {
      const response = await fetch(config.uploadUrl, {
        method: "POST",
        headers: {
          "X-CSRFToken": csrfToken()
        },
        body: formData
      });

      const data = await response.json();

      if (!response.ok || !data.ok || data.passed === false) {
        throw new Error(data.reason || data.error || "Sound save failed.");
      }

      rawFeatureCount.textContent = `${data.completed_sound_count || completed + 1}/${soundTasks.length}`;
      pcaFeatureCount.textContent = "Pending";
      pipelineState.textContent = "Saved";

      completed += 1;
      streak += 1;
      index += 1;
      isSubmitting = false;
      autoSubmitPending = false;
      holdCompleted = false;

      const progress = Math.round((completed / soundTasks.length) * 100);
      activityProgress.style.width = `${progress}%`;
      progressPercent.textContent = `${progress}%`;
      completedText.textContent = `${completed} / ${soundTasks.length} completed`;

      if (index >= soundTasks.length) {
        setStatus("All configured sounds saved. Combining audio and running voice analysis...");
        isSubmitting = false;
        autoSubmitPending = false;
        holdCompleted = false;
        await completeVoicePhonation();
        return;
      }

      setStatus(`Sound ${completed} saved. Loading sound ${index + 1}...`);
      renderTask();

      if (AUTO_CONTINUE_NEXT_SOUND) {
        startBtn.disabled = true;
        stopBtn.disabled = true;
        submitBtn.disabled = true;

        window.setTimeout(function () {
          if (index < soundTasks.length) {
            startSound();
          }
        }, NEXT_SOUND_DELAY_MS);
      } else {
        startBtn.disabled = false;
      }

    } catch (error) {
      streak = 0;
      isSubmitting = false;
      autoSubmitPending = false;
      holdCompleted = false;

      pipelineState.textContent = "Failed";
      setStatus("Backend failed: " + error.message);

      startBtn.disabled = false;
      stopBtn.disabled = true;
      submitBtn.disabled = true;
    }
  }

  async function completeVoicePhonation() {
    startBtn.disabled = true;
    stopBtn.disabled = true;
    submitBtn.disabled = true;

    pipelineState.textContent = "Combining";
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
        throw new Error(data.error || "Voice completion failed.");
      }

      setStatus("Combined voice processing started. Please wait...");
      pollVoiceStatus();

    } catch (error) {
      pipelineState.textContent = "Failed";
      setStatus("Backend failed: " + error.message);
      startBtn.disabled = false;
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
        throw new Error(data.error_message || "Voice analysis failed. Check qcluster logs.");
      }

      if (data.voice_done === true) {
        setPipelineStep("extract", "done");
        setPipelineStep("pca", "done");
        setPipelineStep("score", "done");
        rawFeatureCount.textContent = "6373";
        pcaFeatureCount.textContent = "24";
        pipelineState.textContent = "Completed";
        setStatus("Voice and multimodal analysis completed.");

        setTimeout(function () {
          window.location.href = config.nextUrl;
        }, 700);
        return;
      }

      setStatus("Voice analysis is processing in background...");
      setTimeout(pollVoiceStatus, 3000);

    } catch (error) {
      pipelineState.textContent = "Failed";
      setStatus("Backend failed: " + error.message);
      startBtn.disabled = false;
    }
  }

  if (startBtn) startBtn.addEventListener("click", startSound);
  if (stopBtn) stopBtn.addEventListener("click", function () {
    stopSound(false);
  });
  if (submitBtn) submitBtn.addEventListener("click", submitSound);

  loadPhonationSounds();
})();
