(function () {
  "use strict";

  var rootEl = document.querySelector(".combined-activity");
  var config = {
    uploadUrl: rootEl ? rootEl.dataset.uploadUrl : "",
    processUrl: rootEl ? rootEl.dataset.processUrl : "",
    nextUrl: rootEl ? rootEl.dataset.nextUrl : "",
    sessionId: rootEl ? rootEl.dataset.sessionId : ""
  };

  // ---- Step data ----
  var steps = [
    { category: "Observe & Describe", tag: "Scene 1", prompt: "Observe the scene and describe everything you see in your own words.", image: "" },
    { category: "Read & Express", tag: "Scene 2", prompt: "What do you think is happening in the story? Explain your thoughts.", image: "" },
    { category: "Think & Reflect", tag: "Scene 3", prompt: "What do you think might happen next in this situation?", image: "" },
    { category: "Act & Grow", tag: "Scene 4", prompt: "If you were in this situation, what would you do and why?", image: "" }
  ];

  var framesData = document.getElementById("story-frames-data");
  if (framesData) {
    try {
      var frames = JSON.parse(framesData.textContent || "[]");
      for (var i = 0; i < steps.length && i < frames.length; i++) {
        steps[i].image = frames[i];
      }
    } catch (e) { /* keep placeholder images */ }
  }

  var STEP_SECONDS = 40;

  // ---- State ----
  var state = {
    currentView: "map",
    currentStep: 0,
    totalSteps: 4,
    totalXP: 0,
    completedSteps: {},
    isRecording: false,
    isPaused: false,
    recordingTimer: STEP_SECONDS,
    timerInterval: null,
    recordedSeconds: 0,
    totalRecordedSeconds: 0,
    stream: null,
    mediaRecorder: null,
    recordedChunks: [],
    finalBlob: null,
    pendingUploadCb: null,
    isUploading: false,
    lastCameraError: null,
    lastFailure: null
  };

  // ---- DOM refs ----
  var mapView = document.getElementById("view-map");
  var stepView = document.getElementById("view-step");
  var stepCounterText = document.getElementById("step-counter-text");
  var stepCategoryHeading = document.getElementById("step-category-heading");
  var stepCategorySubtitle = document.getElementById("step-category-subtitle");
  var sceneImage = document.getElementById("scene-image");
  var sceneTag = document.getElementById("scene-tag");
  var questionText = document.getElementById("question-text");
  var recordingTimerPill = document.getElementById("recording-timer-pill");
  var timerDisplay = document.getElementById("timer-display");
  var startOverlay = document.getElementById("start-overlay");
  var recordingStateActive = document.getElementById("recording-state-active");
  var btnStartRecording = document.getElementById("btn-start-recording");
  var cameraPreview = document.getElementById("camera-preview");
  var cameraPlaceholder = document.getElementById("camera-placeholder");
  var faceStatus = document.getElementById("face-status");
  var modalCompletion = document.getElementById("modal-completion");
  var modalBox = document.getElementById("modal-box");
  var modalXp = document.getElementById("modal-xp");
  var completionTitle = document.getElementById("completion-title");
  var xpToast = document.getElementById("xp-toast");
  var xpToastTitle = document.getElementById("xp-toast-title");
  var xpToastBody = document.getElementById("xp-toast-body");
  var uploadOverlay = document.getElementById("upload-overlay");
  var uploadProgressBar = document.getElementById("upload-progress-bar");
  var uploadProgressLabel = document.getElementById("upload-progress-label");
  var startBtnLabel = document.getElementById("start-btn-label");
  var modalFailure = document.getElementById("modal-failure");
  var modalFailureIcon = document.getElementById("failure-icon");
  var modalFailureTitle = document.getElementById("failure-title");
  var modalFailureMessage = document.getElementById("failure-message");
  var btnFailureRetry = document.getElementById("btn-failure-retry");
  var btnFailureClose = document.getElementById("btn-failure-close");
  var btnFailureBox = document.getElementById("failure-box");
  var cameraErrorHint = document.getElementById("camera-error-hint");

  // ---- Helpers ----
  function getCsrfToken() {
    var input = document.querySelector("[name=csrfmiddlewaretoken]");
    return input ? input.value : "";
  }

  function pad(n) { return n < 10 ? "0" + n : "" + n; }

  // ---- View Navigation ----
  function navigateTo(view) {
    state.currentView = view;
    if (view === "map") {
      mapView.classList.remove("hidden");
      stepView.classList.add("hidden");
      resetRecording();
      updateMapUI();
    } else {
      mapView.classList.add("hidden");
      stepView.classList.remove("hidden");
      renderStep();
    }
  }

  // ---- Map UI ----
  function updateMapUI() {
    for (var i = 1; i <= 4; i++) {
      var badge = document.getElementById("badge-status-" + i);
      var circle = document.getElementById("map-circle-" + i);
      var numBadge = document.getElementById("map-badge-number-" + i);

      if (state.completedSteps[i]) {
        badge.textContent = "Completed ✓";
        badge.className = "inline-block mt-1 text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800";
        circle.className = "w-36 h-36 sm:w-40 sm:h-40 rounded-full overflow-hidden border-4 border-white shadow-xl ring-4 ring-emerald-500 transition duration-300";
        numBadge.className = "absolute -top-1.5 right-1.5 w-9 h-9 bg-emerald-700 text-white font-black rounded-full flex items-center justify-center text-sm border-2 border-white shadow-md";
        numBadge.innerHTML = "✓";
      } else if (i === 1 || state.completedSteps[i - 1]) {
        badge.textContent = "Ready";
        badge.className = "inline-block mt-1 text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-blue-100 text-blue-800";
        circle.className = "w-36 h-36 sm:w-40 sm:h-40 rounded-full overflow-hidden border-4 border-white shadow-xl ring-4 ring-emerald-300 transition duration-300";
        numBadge.className = "absolute -top-1.5 right-1.5 w-9 h-9 bg-mindGreen text-white font-black rounded-full flex items-center justify-center text-sm border-2 border-white shadow-md";
        numBadge.innerHTML = i;
      } else {
        badge.textContent = "Locked";
        badge.className = "inline-block mt-1 text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-gray-100 text-gray-500";
        circle.className = "w-36 h-36 sm:w-40 sm:h-40 rounded-full overflow-hidden border-4 border-white shadow-sm ring-4 ring-gray-200 opacity-60 transition duration-300";
        numBadge.className = "absolute -top-1.5 right-1.5 w-9 h-9 bg-gray-400 text-white font-black rounded-full flex items-center justify-center text-sm border-2 border-white shadow-md";
        numBadge.innerHTML = i;
      }
    }

    var count = Object.keys(state.completedSteps).length;
    if (count === 4) { startBtnLabel.textContent = "Review Journey"; }
    else if (count > 0) { startBtnLabel.textContent = "Continue Journey"; }
    else { startBtnLabel.textContent = "Start Journey"; }
  }

  // ---- Step Rendering ----
  function renderStep() {
    var data = steps[state.currentStep];
    stepCounterText.textContent = "Step " + (state.currentStep + 1) + " of " + state.totalSteps;
    stepCategoryHeading.textContent = data.category;
    if (stepCategorySubtitle) stepCategorySubtitle.textContent = data.category;
    sceneTag.textContent = data.tag;
    sceneImage.src = data.image;
    questionText.textContent = data.prompt;

    for (var i = 1; i <= 4; i++) {
      var dot = document.getElementById("dot-" + i);
      var line = document.getElementById("line-" + i);
      if (state.completedSteps[i]) {
        dot.className = "w-9 h-9 rounded-full bg-mindGreen text-white text-sm font-bold flex items-center justify-center shadow-sm transition";
        dot.innerHTML = "✓";
      } else if (i === state.currentStep + 1) {
        dot.className = "w-9 h-9 rounded-full bg-mindGreen text-white text-sm font-bold flex items-center justify-center ring-2 ring-emerald-200 shadow-md transition";
        dot.innerHTML = i;
      } else {
        dot.className = "w-9 h-9 rounded-full bg-gray-100 text-gray-500 text-sm font-bold flex items-center justify-center border border-gray-200 transition";
        dot.innerHTML = i;
      }
      if (line) {
        line.className = "w-5 sm:w-8 h-[3px] rounded-full " + (state.completedSteps[i] ? "bg-mindGreen" : "bg-gray-300");
      }
    }

    resetRecording();
  }

  // ---- Toast ----
  function showToast(title, body) {
    xpToastTitle.textContent = title;
    xpToastBody.textContent = body;
    xpToast.classList.remove("translate-y-24", "opacity-0");
    xpToast.classList.add("translate-y-0", "opacity-100");
    setTimeout(function () {
      xpToast.classList.remove("translate-y-0", "opacity-100");
      xpToast.classList.add("translate-y-24", "opacity-0");
    }, 2400);
  }

  // ---- Camera error feedback ----
  function showCameraHint(show, reason) {
    if (!cameraErrorHint) return;
    if (show) {
      var text = reason === "denied"
        ? "Camera permission is off — allow it in your browser to record. Try again when ready."
        : reason === "no-device"
          ? "No camera detected on this device. You may still prepare your response."
          : reason === "busy"
            ? "Another app is using the camera. Close it and try again."
            : "Camera isn't available right now. Try again when ready.";
      cameraErrorHint.textContent = text;
      cameraErrorHint.classList.remove("hidden");
    } else {
      cameraErrorHint.classList.add("hidden");
      cameraErrorHint.textContent = "";
    }
  }

  function onCameraStartFailed() {
    var msg = CameraError.messageFor(state.lastCameraError || { name: "UnknownError" });
    showFailureModal("camera", msg.message, msg.title);
  }

  // ---- Camera ----
  function setFaceStatus(detected) {
    if (!faceStatus) return;
    if (detected) {
      faceStatus.className = "flex items-center text-emerald-800";
      faceStatus.innerHTML = '<svg class="w-4 h-4 mr-1 text-emerald-600" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2l2.4 4.9 5.4.8-3.9 3.8.9 5.4L12 14.8 7.2 16.9l.9-5.4L4.2 7.7l5.4-.8L12 2z"/></svg><span id="face-status-text">Face Detected</span>';
    } else {
      faceStatus.className = "flex items-center text-gray-600";
      faceStatus.innerHTML = '<svg class="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10 10-4.5 10-10S17.5 2 12 2zm3.5 13.5L11 11l.7-.7-4.5-4.5-1.4 1.4 4.5 4.5-.7.7 4.5 4.5 1.4-1.4z"/></svg><span id="face-status-text">Not detected</span>';
    }
  }

  function cleanupCamera() {
    if (state.stream) {
      state.stream.getTracks().forEach(function (t) { t.stop(); });
      state.stream = null;
    }
    if (cameraPreview) {
      cameraPreview.srcObject = null;
      cameraPreview.classList.add("hidden-feed");
    }
    if (cameraPlaceholder) cameraPlaceholder.style.display = "flex";
  }

  function ensureCamera() {
    if (state.stream) return Promise.resolve(state.stream);
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      state.lastCameraError = null;
      setFaceStatus(false);
      showCameraHint(true, CameraError.reasonFor(null, { mediaDevices: false }));
      return Promise.reject(new Error("Camera API not available"));
    }
    return navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 360 }, frameRate: { ideal: 15, max: 20 } },
      audio: true
    }).then(function (s) {
      state.stream = s;
      state.lastCameraError = null;
      if (cameraPreview) {
        cameraPreview.srcObject = s;
        cameraPreview.classList.remove("hidden-feed");
        cameraPreview.play && cameraPreview.play().catch(function () {});
      }
      if (cameraPlaceholder) cameraPlaceholder.style.display = "none";
      showCameraHint(false);
      setFaceStatus(true);
      return s;
    }).catch(function (err) {
      state.lastCameraError = err;
      if (typeof console !== "undefined" && console.warn) {
        console.warn("Camera unavailable:", err && err.name ? err.name : err);
      }
      setFaceStatus(false);
      showCameraHint(true, CameraError.reasonFor(err));
      return null;
    });
  }

  // ---- Recording UI States ----
  function showRecordingState(name) {
    if (name === "initial") {
      startOverlay.classList.remove("hidden");
      recordingStateActive.classList.add("hidden");
      sceneImage.classList.add("hidden");
    } else if (name === "active") {
      startOverlay.classList.add("hidden");
      recordingStateActive.classList.remove("hidden");
      sceneImage.classList.remove("hidden");
    }
  }

  function updateTimerDisplay() {
    var s = pad(state.recordingTimer);
    timerDisplay.textContent = "00:" + s;
  }

  function stopTimerUI() {
    if (state.timerInterval) { clearInterval(state.timerInterval); state.timerInterval = null; }
    document.querySelectorAll(".waveform-bar").forEach(function (bar) { bar.classList.remove("active"); });
  }

  // ---- Recording Logic ----
  // ONE continuous MediaRecorder spans all 4 steps. It pauses while the user
  // reads the next prompt and resumes on the next step's start, producing a
  // single webm file that needs no server-side concatenation.
  function createRecorder() {
    var mimeType = MediaRecorder.isTypeSupported("video/webm;codecs=vp8,opus")
      ? "video/webm;codecs=vp8,opus"
      : "video/webm";
    state.mediaRecorder = new MediaRecorder(state.stream, {
      mimeType: mimeType,
      videoBitsPerSecond: 450000,
      audioBitsPerSecond: 48000
    });
    state.recordedChunks = [];

    state.mediaRecorder.ondataavailable = function (e) {
      if (e.data && e.data.size > 0) state.recordedChunks.push(e.data);
    };

    state.mediaRecorder.onstop = function () {
      stopTimerUI();
      var blob = new Blob(state.recordedChunks, { type: "video/webm" });
      state.finalBlob = blob.size > 0 ? blob : null;
      if (state.pendingUploadCb) {
        var cb = state.pendingUploadCb;
        state.pendingUploadCb = null;
        cb();
      }
    };
  }

  function stepTimerTick() {
    state.recordingTimer--;
    state.recordedSeconds++;
    state.totalRecordedSeconds++;
    updateTimerDisplay();
    if (state.recordingTimer <= 0) {
      completeStepAuto();
    }
  }

  function beginRecording() {
    if (state.mediaRecorder && state.mediaRecorder.state === "recording") return;
    if (state.mediaRecorder && state.mediaRecorder.state === "paused") {
      state.mediaRecorder.resume();
      state.isRecording = true;
      state.recordingTimer = STEP_SECONDS;
      state.recordedSeconds = 0;
      showRecordingState("active");
      recordingTimerPill.classList.remove("hidden");
      updateTimerDisplay();
      document.querySelectorAll(".waveform-bar").forEach(function (bar) { bar.classList.add("active"); });
      state.timerInterval = setInterval(stepTimerTick, 1000);
      return;
    }

    if (!state.mediaRecorder) {
      createRecorder();
    }

    state.isRecording = true;
    state.recordingTimer = STEP_SECONDS;
    state.recordedSeconds = 0;
    state.mediaRecorder.start(1000);

    showRecordingState("active");
    recordingTimerPill.classList.remove("hidden");
    updateTimerDisplay();
    document.querySelectorAll(".waveform-bar").forEach(function (bar) { bar.classList.add("active"); });

    state.timerInterval = setInterval(stepTimerTick, 1000);
  }

  function startRecording() {
    ensureCamera().then(function (s) {
      if (!s) { onCameraStartFailed(); return; }
      beginRecording();
    });
  }

  // Auto-completes the current step when its 40s timer elapses: pauses the
  // shared recorder, unlocks the step, and advances (or submits on the last).
  function completeStepAuto() {
    stopTimerUI();
    state.isRecording = false;
    recordingTimerPill.classList.add("hidden");
    if (state.mediaRecorder && state.mediaRecorder.state === "recording") {
      try { state.mediaRecorder.pause(); } catch (e) { /* ignore */ }
    }
    state.completedSteps[state.currentStep + 1] = true;
    state.totalXP += 50;
    if (typeof confetti === "function") {
      confetti({ particleCount: 55, spread: 60, origin: { y: 0.75 } });
    }
    showToast("+50 XP Earned!", "Great observation & clarity!");
    if (state.currentStep >= state.totalSteps - 1) {
      cleanupCamera();
      setTimeout(function () { submitAll(); }, 600);
    } else {
      setTimeout(function () {
        state.currentStep++;
        renderStep();
      }, 600);
    }
  }

  // Final stop: ends the single recorder and produces the one combined blob.
  function finalizeRecording(done) {
    stopTimerUI();
    state.isRecording = false;
    recordingTimerPill.classList.add("hidden");
    state.pendingUploadCb = done || null;
    if (state.mediaRecorder && state.mediaRecorder.state !== "inactive") {
      try { state.mediaRecorder.stop(); } catch (e) { /* ignore */ }
    } else if (state.pendingUploadCb) {
      var cb = state.pendingUploadCb;
      state.pendingUploadCb = null;
      cb();
    }
  }

  function resetRecording() {
    stopTimerUI();
    state.isRecording = false;
    state.recordingTimer = STEP_SECONDS;
    state.recordedSeconds = 0;
    recordingTimerPill.classList.add("hidden");
    showRecordingState("initial");
  }

  // ---- Upload single combined video ----
  function showUploadProgress(pct, label) {
    uploadOverlay.classList.remove("hidden");
    uploadOverlay.classList.add("flex");
    var p = Math.max(0, Math.min(100, pct || 0));
    uploadProgressBar.style.width = p + "%";
    uploadProgressLabel.textContent = label || Math.round(p) + "%";
  }

  var FAILURE_CONFIG = {
    face: {
      title: "We couldn't see your face clearly",
      icon:
        '<svg class="w-9 h-9 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.5 20.118a7.5 7.5 0 0114.996 0A17.933 17.933 0 0112 21.75a17.933 17.933 0 01-7.5-1.632z" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"/></svg>'
    },
    audio: {
      title: "We couldn't hear you clearly",
      icon:
        '<svg class="w-9 h-9 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M12 18.5a6.5 6.5 0 006.5-6.5M12 18.5A6.5 6.5 0 015.5 12M12 18.5V22M9 22h6m-3-18a3 3 0 00-3 3v5a3 3 0 006 0V7a3 3 0 00-3-3z" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"/></svg>'
    },
    text: {
      title: "We couldn't read your response",
      icon:
        '<svg class="w-9 h-9 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M8 10h8m-8 4h5m-9-9a3 3 0 013-3h5l5 5v11a3 3 0 01-3 3H7a3 3 0 01-3-3V5z" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"/></svg>'
    },
    server: {
      title: "Something went wrong",
      icon:
        '<svg class="w-9 h-9 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M12 9v4m0 4h.01M10.3 3.7L1.9 18a2 2 0 001.7 3h16.8a2 2 0 001.7-3L13.7 3.7a2 2 0 00-3.4 0z" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"/></svg>'
    },
    camera: {
      title: "Camera isn't available",
      icon:
        '<svg class="w-9 h-9 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M15.75 10.5l4.72-4.72a.75.75 0 011.28.53v11.38a.75.75 0 01-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 002.25-2.25v-9a2.25 2.25 0 00-2.25-2.25h-9A2.25 2.25 0 002.25 7.5v9a2.25 2.25 0 002.25 2.25z" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"/></svg>'
    }
  };

  function showFailureModal(reason, message, titleOverride) {
    var cfg = FAILURE_CONFIG[reason] || FAILURE_CONFIG.server;
    state.lastFailure = reason;
    var title = document.getElementById("failure-title");
    var msg = document.getElementById("failure-message");
    if (modalFailureIcon) modalFailureIcon.innerHTML = cfg.icon;
    if (title) title.textContent = titleOverride || cfg.title;
    if (msg) msg.textContent = message;
    if (modalFailure) {
      modalFailure.classList.remove("hidden");
      modalFailure.classList.add("flex");
      setTimeout(function () {
        if (btnFailureBox) {
          btnFailureBox.classList.remove("scale-95");
          btnFailureBox.classList.add("scale-100");
        }
      }, 20);
    }
  }

  function hideFailureModal() {
    if (!modalFailure) return;
    modalFailure.classList.add("hidden");
    modalFailure.classList.remove("flex");
    if (btnFailureBox) {
      btnFailureBox.classList.add("scale-95");
      btnFailureBox.classList.remove("scale-100");
    }
  }

  function hideUploadOverlay() {
    uploadOverlay.classList.add("hidden");
    uploadOverlay.classList.remove("flex");
  }

  function retryUpload() {
    hideFailureModal();
    submitAll();
  }

  function retryCamera() {
    hideFailureModal();
    ensureCamera().then(function (s) {
      if (s) { beginRecording(); }
      else { onCameraStartFailed(); }
    });
  }

  function submitAll() {
    state.isUploading = true;
    showUploadProgress(0, "Preparing upload...");
    cleanupCamera();
    finalizeRecording(uploadFinalBlob);
  }

  function uploadFinalBlob() {
    var blob = state.finalBlob;
    if (!blob) {
      state.isUploading = false;
      hideUploadOverlay();
      showFailureModal(
        "server",
        "No recording was captured. Please try again."
      );
      return;
    }

    var formData = new FormData();
    formData.append("video", blob, "combined-activity.webm");
    formData.append("duration_seconds", String(Math.max(state.totalRecordedSeconds, 1)));
    formData.append("activity_id", "combined_observe_describe");
    formData.append("activity_title", "Combined Observe & Describe");
    formData.append("activity_prompt", steps.map(function (s) { return s.prompt; }).join(" "));

    var xhr = new XMLHttpRequest();
    xhr.open("POST", config.uploadUrl, true);
    xhr.setRequestHeader("X-CSRFToken", getCsrfToken());

    xhr.upload.onprogress = function (e) {
      if (e.lengthComputable) {
        var pct = Math.round((e.loaded / e.total) * 100);
        showUploadProgress(pct, pct < 100 ? "Uploading " + pct + "%" : "Processing " + pct + "%");
      }
    };

    xhr.onload = function () {
      var data = null;
      try { data = JSON.parse(xhr.responseText || "{}"); } catch (e) { data = {}; }
      if (xhr.status < 200 || xhr.status >= 300 || !data.ok) {
        state.isUploading = false;
        hideUploadOverlay();
        showFailureModal(
          "server",
          (data && data.error) || "The recording couldn't be uploaded. Please check your connection and try again."
        );
        return;
      }
      showUploadProgress(100, "Saving facial analysis...");

      var processData = new FormData();
      processData.append("capture_id", String(data.capture_id));

      var processRequest = new XMLHttpRequest();
      processRequest.open("POST", config.processUrl, true);
      processRequest.setRequestHeader("X-CSRFToken", getCsrfToken());
      processRequest.onload = function () {
        var processResult = null;
        try { processResult = JSON.parse(processRequest.responseText || "{}"); } catch (e) { processResult = {}; }

        if (processRequest.status < 200 || processRequest.status >= 300 || !processResult.ok) {
          state.isUploading = false;
          hideUploadOverlay();
          showFailureModal(
            "server",
            (processResult && processResult.error) || "The recording was saved, but analysis could not start."
          );
          return;
        }

        showUploadProgress(100, "Moving to next activity...");
        setTimeout(function () {
          state.isUploading = false;
          window.location.href = config.nextUrl;
        }, 300);
      };
      processRequest.onerror = function () {
        state.isUploading = false;
        hideUploadOverlay();
        showFailureModal("server", "The recording was saved, but analysis could not start.");
      };
      processRequest.send(processData);
    };

    xhr.onerror = function () {
      state.isUploading = false;
      hideUploadOverlay();
      showFailureModal(
        "server",
        "A network problem stopped the upload. Please check your connection and try again."
      );
    };

    xhr.ontimeout = function () {
      state.isUploading = false;
      hideUploadOverlay();
      showFailureModal(
        "server",
        "The upload took too long. Please check your connection and try again."
      );
    };

    xhr.timeout = 5 * 60 * 1000;
    xhr.send(formData);
  }

  // ---- Completion Modal ----
  function showCompletionModal() {
    modalCompletion.classList.remove("hidden");
    completionTitle.textContent = "Splendid Job!";
    modalXp.textContent = "+" + state.totalXP + " XP";
    setTimeout(function () {
      modalBox.classList.remove("scale-95");
      modalBox.classList.add("scale-100");
    }, 20);
    if (typeof confetti === "function") {
      confetti({ particleCount: 140, spread: 90, origin: { y: 0.55 } });
    }
  }

  function closeModalAndGoMap() {
    modalCompletion.classList.add("hidden");
    modalBox.classList.add("scale-95");
    modalBox.classList.remove("scale-100");
    navigateTo("map");
  }

  function restartFullJourney() {
    modalCompletion.classList.add("hidden");
    modalBox.classList.add("scale-95");
    modalBox.classList.remove("scale-100");
    state.completedSteps = {};
    state.totalXP = 0;
    state.currentStep = 0;
    navigateTo("step");
  }

  // ---- Public API ----
  window.MCA = {
    navigateTo: navigateTo,
    startJourney: function () {
      var nextStep = 0;
      for (var i = 1; i <= state.totalSteps; i++) {
        if (!state.completedSteps[i]) { nextStep = i - 1; break; }
      }
      state.currentStep = nextStep;
      navigateTo("step");
    },
    startAtStep: function (stepNum) {
      if (stepNum > 1 && !state.completedSteps[stepNum - 1] && !state.completedSteps[stepNum]) {
        showToast("Locked Step", "Please complete Step " + (stepNum - 1) + " first!");
        return;
      }
      state.currentStep = stepNum - 1;
      navigateTo("step");
    },
    togglePause: function () {
      state.isPaused = !state.isPaused;
      var label = document.getElementById("pause-btn-label");
      var btn = document.getElementById("pause-session-btn");
      if (state.isPaused) {
        state.isRecording = false;
        if (state.mediaRecorder && state.mediaRecorder.state === "recording") {
          try { state.mediaRecorder.pause(); } catch (e) { /* ignore */ }
        }
        if (state.timerInterval) { clearInterval(state.timerInterval); state.timerInterval = null; }
        btn.classList.add("bg-amber-600");
        label.textContent = "Resume Session";
        showToast("Session Paused", "Take a breath, resume whenever ready!");
      } else {
        state.isRecording = true;
        if (state.mediaRecorder && state.mediaRecorder.state === "paused") {
          try { state.mediaRecorder.resume(); } catch (e) { /* ignore */ }
          recordingTimerPill.classList.remove("hidden");
          document.querySelectorAll(".waveform-bar").forEach(function (bar) { bar.classList.add("active"); });
          if (!state.timerInterval) {
            state.timerInterval = setInterval(stepTimerTick, 1000);
          }
        }
        btn.classList.remove("bg-amber-600");
        label.textContent = "Pause Session";
      }
    },
    toggleGuide: function () {
      var content = document.getElementById("guide-content");
      var chevron = document.getElementById("guide-chevron");
      content.classList.toggle("hidden");
      chevron.classList.toggle("rotate-180");
    }
  };

  // ---- Wire Events ----
  btnStartRecording.addEventListener("click", function () {
    if (state.isRecording) return;
    if (state.stream) { beginRecording(); }
    else {
      ensureCamera().then(function (s) {
        if (s) beginRecording();
        else { setFaceStatus(false); onCameraStartFailed(); }
      });
    }
  });

  document.getElementById("btn-back-map").addEventListener("click", closeModalAndGoMap);
  document.getElementById("btn-restart-journey").addEventListener("click", restartFullJourney);

  btnFailureRetry.addEventListener("click", function () {
    if (state.lastFailure === "camera") { retryCamera(); }
    else { retryUpload(); }
  });

  btnFailureClose.addEventListener("click", function () {
    state.isUploading = false;
    hideFailureModal();
  });

  // ---- Init ----
  ensureCamera();
  updateMapUI();

  var guideContent = document.getElementById("guide-content");
  var guideChevron = document.getElementById("guide-chevron");
  if (guideContent && window.matchMedia && window.matchMedia("(min-width: 1024px)").matches) {
    if (!guideContent.classList.contains("hidden")) guideContent.classList.add("hidden");
    if (guideChevron) guideChevron.classList.add("rotate-180");
  }
})();
