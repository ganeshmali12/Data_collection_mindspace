(function () {
  "use strict";

  // Maps browser DOMException names from navigator.mediaDevices.getUserMedia()
  // to stable, user-facing failure reasons. Exposed as window.CameraError so the
  // mapping can be unit-tested (node --test) without a DOM.
  window.CameraError = {
    reasonFor: function (err, opts) {
      opts = opts || {};
      if (opts && opts.mediaDevices === false) return "unsupported";
      var name = "" + ((err && (err.name || err.code)) || "");
      if (name === "NotAllowedError" || name === "PermissionDeniedError") return "denied";
      if (name === "NotFoundError" || name === "DevicesNotFoundError" || name === "OverconstrainedError") return "no-device";
      if (name === "NotReadableError" || name === "TrackStartError" || name === "AbortError") return "busy";
      if (name === "SecurityError" || name === "TypeError") return "insecure";
      return "unknown";
    },

    messageFor: function (err, opts) {
      opts = opts || {};
      var reason = this.reasonFor(err, opts);
      var table = {
        unsupported: {
          title: "Camera not supported here",
          message: "Your browser or this connection can't access the camera. Use a supported browser over HTTPS or 127.0.0.1, or open your camera app and try again."
        },
        denied: {
          title: "Camera permission is off",
          message: "We couldn't get camera access. Please allow the camera for this site in your browser settings, then click Try Again."
        },
        "no-device": {
          title: "No camera detected",
          message: "No camera was found on this device. Connect a camera or check your device settings, then click Try Again."
        },
        busy: {
          title: "Camera is in use",
          message: "Another application is using the camera. Close that app, then click Try Again."
        },
        insecure: {
          title: "Camera needs a secure connection",
          message: "Camera access requires HTTPS (or http://127.0.0.1/locally). Open this page securely, then click Try Again."
        },
        unknown: {
          title: "Camera isn't available",
          message: "The camera couldn't be started right now. Check your camera and browser settings, then click Try Again."
        }
      };
      return table[reason] || table.unknown;
    }
  };
})();