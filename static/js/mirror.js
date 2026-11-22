/* Fishermen Pants — The Mirror (experiment).
 *
 * 4-step flow: setup -> capture -> process -> result, with an escape back to
 * the shop from every step. Inference is STUBBED for now: `applyPiece()` draws
 * the garment thumbnail over the captured frame so the flow, timing and UI can
 * be validated before any model work lands. Swap that one function for the real
 * call (local GPU endpoint or in-browser WASM) when org-o39g picks a winner.
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
  function applyPiece(frame, pieceHandle) {
    /* STUB: draws the captured frame, then composites the garment thumbnail
       over it to prove the flow end-to-end. Replace with the real inference
       call once a model is chosen (see beads org-o39g / org-t29s). */
    return new Promise(resolve => {
      const img = new Image();
      img.onload = () => {
        const c = document.createElement("canvas");
        c.width = frame.w;
        c.height = frame.h;
        const ctx = c.getContext("2d");

        const base = new Image();
        base.onload = () => {
          ctx.drawImage(base, 0, 0);

          // Garment placard, bottom-right, sized to the frame.
          const gw = Math.round(frame.w * 0.30);
          const gh = Math.round(gw * (img.height / img.width));
          const x = frame.w - gw - Math.round(frame.w * 0.04);
          const y = frame.h - gh - Math.round(frame.w * 0.04);

          ctx.globalAlpha = 0.94;
          ctx.fillStyle = "#ffffff";
          ctx.fillRect(x - 8, y - 8, gw + 16, gh + 16);
          ctx.drawImage(img, x, y, gw, gh);
          ctx.globalAlpha = 1;

          resolve(c.toDataURL("image/jpeg", 0.92));
        };
        base.src = frame.dataURL;
      };
      img.src = pieceImage(pieceHandle);
    });
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

    // Show the still frame while "working".
    const ctx = canvas.getContext("2d");
    const frameImg = new Image();
    frameImg.onload = () => {
      canvas.width = frameImg.width;
      canvas.height = frameImg.height;
      ctx.drawImage(frameImg, 0, 0);
    };
    frameImg.src = captured.dataURL;

    const piece = document.querySelector('input[name="piece"]:checked').value;
    const quality = document.querySelector('input[name="quality"]:checked').value;
    const expected = quality === "best" ? 9000 : 3800;

    note.textContent = quality === "best" ? "Rendering in high detail…" : "Rendering a quick preview…";
    bar.style.width = "6%";

    // Simulated progress; the real implementation should report actual steps.
    const started = Date.now();
    const timer = setInterval(() => {
      const pct = Math.min(92, 6 + ((Date.now() - started) / expected) * 86);
      bar.style.width = pct.toFixed(1) + "%";
    }, 160);

    const result = await applyPiece(captured, piece);
    const elapsed = Date.now() - started;
    clearInterval(timer);
    if (cancelled) return;

    // Leave the bar visible for a beat if we finished very fast.
    if (elapsed < expected) await new Promise(r => setTimeout(r, expected - elapsed));
    if (cancelled) return;

    bar.style.width = "100%";
    note.textContent = "Done.";
    showResult(result, piece);
  }

  function showResult(dataURL, piece) {
    document.getElementById("mirror-result-img").src = dataURL;
    document.getElementById("mirror-result-caption").textContent = pieceLabel(piece);
    document.getElementById("mirror-result-badge").textContent = "Preview — not a photograph";
    document.getElementById("mirror-result-text").textContent =
      "This is a rough preview, not a photo. Colours and drape will differ in person — " +
      "the pieces are handmade in small batches, so no two are identical.";

    const p = (window.FP_PIECES || []).find(x => x.handle === piece);
    if (p) document.getElementById("mirror-result-shop").href = (app.dataset.base || "/") + p.href;

    document.getElementById("mirror-save").onclick = () => {
      const a = document.createElement("a");
      a.href = dataURL;
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
    devNote.textContent = "Your device is on the slower side — “Fast” will be noticeably quicker here.";
  }
})();
