/* Fishermen Pants — The Mirror (experiment).
 *
 * 4-step flow: setup -> capture -> process -> result, with an escape back to
 * the shop from every step. Inference runs in-browser (see mirror-ml.js):
 * MediaPipe WASM person segmentation + canvas garment compositing. A placard
 * stub is kept as the fallback when the model can't load.
 *
 * Camera frames never leave the device in this version.
 */
(function () {
  const app = document.getElementById("mirror-app");
  if (!app) return;

  const steps = Array.from(document.querySelectorAll(".mirror-step"));
  const indicator = Array.from(document.querySelectorAll("#mirror-steps li"));
  const ORDER = ["setup", "capture", "process", "result"];

  let current = "setup";
  let stream = null;
  let captured = null; // { dataURL, w, h }
  let cancelled = false;

  // ---------------------------------------------------------------- steps
  function go(step) {
    current = step;
    steps.forEach(s => { s.hidden = s.dataset.step !== step; });
    indicator.forEach(li => {
      li.classList.toggle("is-active", li.dataset.step === step);
      const seen = ORDER.indexOf(li.dataset.step) < ORDER.indexOf(step);
      li.classList.toggle("is-done", seen);
    });
    // Stop the camera as soon as we're past capture: no reason to keep it live.
    if (step !== "capture") stopCamera();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  // ---------------------------------------------------------------- camera
  function cameraSupported() {
    return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
  }

  function stopCamera() {
    if (stream) {
      stream.getTracks().forEach(t => t.stop());
      stream = null;
    }
  }

  function waitForFrame(video, timeoutMs) {
    if (video.videoWidth > 0 && video.videoHeight > 0) return Promise.resolve(true);
    return new Promise(resolve => {
      const started = Date.now();
      const check = () => {
        if (video.videoWidth > 0 && video.videoHeight > 0) return resolve(true);
        if (Date.now() - started > timeoutMs) return resolve(false);
        requestAnimationFrame(check);
      };
      // 'loadedmetadata' fires as soon as dimensions are known
      video.addEventListener("loadedmetadata", () => resolve(video.videoWidth > 0), { once: true });
      check();
    });
  }

  async function startCamera() {
    const note = document.getElementById("mirror-capture-note");
    if (!cameraSupported()) {
      note.textContent = "This browser can't access a camera. You can still browse the pieces on the shop.";
      return false;
    }
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 960 } },
        audio: false
      });
      const video = document.getElementById("mirror-video");
      video.srcObject = stream;
      await video.play().catch(() => {});

      // A stream can start before the first frame arrives (videoWidth === 0).
      // Advancing then would leave the user on a dead step, so wait for real
      // dimensions — but never longer than a few seconds.
      const ready = await waitForFrame(video, 6000);
      if (!ready) {
        note.textContent =
          "The camera opened but isn't sending a picture. Check that no other " +
          "app is using it, then try again.";
        stopCamera();
        return false;
      }
      note.textContent = "";
      return true;
    } catch (err) {
      const denied = err && (err.name === "NotAllowedError" || err.name === "SecurityError");
      note.textContent = denied
        ? "Camera access was blocked. Allow it in your browser's address-bar settings and try again — nothing is uploaded."
        : "We couldn't start the camera. Close other apps using it, then try again.";
      return false;
    }
  }

  // ---------------------------------------------------------------- capture
  function captureFrame() {
    const video = document.getElementById("mirror-video");
    const vw = video.videoWidth;
    const vh = video.videoHeight;
    if (!vw || !vh) return null;

    // Cap the long edge: a phone's full-resolution frame is wasted bandwidth
    // and slower to process, and 1280 is plenty for a try-on preview.
    const MAX = 1280;
    const scale = Math.min(1, MAX / Math.max(vw, vh));
    const w = Math.round(vw * scale);
    const h = Math.round(vh * scale);

    const c = document.createElement("canvas");
    c.width = w;
    c.height = h;
    const ctx = c.getContext("2d");
    // Mirror the preview horizontally so the capture matches what the user saw.
    ctx.translate(w, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(video, 0, 0, w, h);
    return { dataURL: c.toDataURL("image/jpeg", 0.9), w, h };
  }

  function runCountdown(done) {
    const el = document.getElementById("mirror-countdown");
    const flash = document.getElementById("mirror-flash");
    let n = 3;
    el.hidden = false;
    el.textContent = String(n);
    const tick = setInterval(() => {
      n -= 1;
      if (n > 0) {
        el.textContent = String(n);
        return;
      }
      clearInterval(tick);
      el.hidden = true;
      flash.hidden = false;
      setTimeout(() => { flash.hidden = true; done(); }, 90);
    }, 800);
  }

  // ---------------------------------------------------------------- process
  function pieceByHandle(handle) {
    return (window.FP_PIECES || []).find(x => x.handle === handle);
  }

  function pieceImage(handle) {
    const p = (window.FP_PIECES || []).find(x => x.handle === handle);
    return p ? p.img : "";
  }

  function pieceLabel(handle) {
    const p = (window.FP_PIECES || []).find(x => x.handle === handle);
    return p ? p.label : "this piece";
  }

  async function process() {
    cancelled = false;
    const bar = document.getElementById("mirror-progress-bar");
    const note = document.getElementById("mirror-process-note");
    const canvas = document.getElementById("mirror-process-canvas");

    // Show the still frame while working.
    const ctx = canvas.getContext("2d");
    const frameImg = new Image();
    frameImg.onload = () => {
      canvas.width = frameImg.width;
      canvas.height = frameImg.height;
      ctx.drawImage(frameImg, 0, 0);
    };
    frameImg.src = captured.dataURL;

    const handle = document.querySelector('input[name="piece"]:checked').value;
    const piece = pieceByHandle(handle) || { img: "", region: [0.3, 1.0] };

    // Stage 1: make sure the on-device model is loaded (first time only —
    // after that this is instant and the bar barely moves).
    note.textContent = "Loading the on-device model…";
    bar.style.width = "8%";
    const mlState = await window.FPMirrorML.prewarm();
    if (cancelled) return;

    // Stage 2: segment the person, composite the garment.
    note.textContent = mlState === "ready"
      ? "Cutting you out and placing the piece…"
      : "Preparing your preview…";
    bar.style.width = "60%";
    const out = await window.FPMirrorML.applyPiece(captured, piece);
    if (cancelled) return;

    bar.style.width = "100%";
    note.textContent = "Done.";
    showResult(out, handle, out.mode);
  }

  function showResult(out, piece, mode) {
    document.getElementById("mirror-result-img").src = out.dataUrl;
    document.getElementById("mirror-result-caption").textContent = pieceLabel(piece);
    document.getElementById("mirror-result-badge").textContent =
      mode === "stub" ? "Simplified preview — model unavailable" : "Preview — not a photograph";
    document.getElementById("mirror-result-text").textContent =
      "This is a rough preview, not a photo. Colours and drape will differ in person — " +
      "the pieces are handmade in small batches, so no two are identical.";

    const p = (window.FP_PIECES || []).find(x => x.handle === piece);
    if (p) document.getElementById("mirror-result-shop").href = (app.dataset.base || "/") + p.href;

    document.getElementById("mirror-save").onclick = () => {
      const a = document.createElement("a");
      a.href = out.dataUrl;
      a.download = "gaya-mirror-preview.jpg";
      a.click();
    };
    go("result");
  }

  // ---------------------------------------------------------------- wiring
  document.getElementById("mirror-start").addEventListener("click", async () => {
    const ok = await startCamera();
    if (!ok) return;
    go("capture");
  });

  document.getElementById("mirror-shoot").addEventListener("click", () => {
    const video = document.getElementById("mirror-video");
    if (!video.videoWidth) {
      document.getElementById("mirror-capture-note").textContent =
        "The camera isn't ready yet — give it a second, then press Capture.";
      return;
    }
    runCountdown(() => {
      captured = captureFrame();
      if (!captured) {
        document.getElementById("mirror-capture-note").textContent =
          "The camera didn't produce a frame. Give it a second and try again.";
        return;
      }
      go("process");
      process();
    });
  });

  document.getElementById("mirror-cancel").addEventListener("click", () => {
    cancelled = true;
    go("capture");
    startCamera();
  });

  document.getElementById("mirror-again").addEventListener("click", async () => {
    const ok = await startCamera();
    if (ok) go("capture");
    else go("setup");
  });

  // Escape stops the camera too — leaving the page must not keep it live.
  document.querySelectorAll(".mirror-escape").forEach(a => {
    a.addEventListener("click", stopCamera);
  });
  window.addEventListener("pagehide", stopCamera);

  // Device hint on the setup step.
  const devNote = document.getElementById("mirror-device-note");
  if (!cameraSupported()) {
    devNote.hidden = false;
    devNote.textContent = "This browser can't use a camera, so the mirror won't work here. The shop works fine.";
    document.getElementById("mirror-start").disabled = true;
  } else if (navigator.hardwareConcurrency && navigator.hardwareConcurrency <= 4) {
    devNote.hidden = false;
    devNote.textContent = "Your device is on the slower side — the first preview takes a few extra seconds while the model loads.";
  }
})();
