/* Fishermen Pants — The Mirror: in-browser person segmentation + garment compositing.
 *
 * Self-contained module: loads lazily (on first use), no build step, no server.
 * Everything runs in the browser — the captured frame never leaves the device.
 *
 * Pipeline (measured real-time on a 2015 i5 laptop CPU — see
 * docs/mirror-ml-research.md):
 *   1. MediaPipe selfie_segmenter (WASM, ~26–36 ms/frame) → per-pixel
 *      person-confidence mask at frame resolution.
 *   2. Canvas composite: the garment photo is cover-fitted into the body
 *      region for that piece type and alpha-composited through the person
 *      mask, so it sits on the person and never bleeds into the background.
 *
 * Exposes window.FPMirrorML = { applyPiece, dispose }.
 *   applyPiece(frame, piece) -> Promise<{ dataUrl, mode }>
 *     frame  = { dataURL, w, h }   (captured, already mirror-flipped)
 *     piece  = { img, region: [topFrac, botFrac] }
 *     mode   = "segmented" | "stub"   (stub = placard fallback when the
 *                                       model can't be loaded)
 */
(function () {
  "use strict";

  const BASE = (document.getElementById("mirror-app") || {}).dataset?.base || "/";
  const WASM_DIR = BASE + "mirror/wasm/";
  const BUNDLE_URL = BASE + "mirror/vision_bundle.js";
  const MODEL_URL = BASE + "mirror/selfie_segmenter.tflite";

  let bundlePromise = null;   // one-time <script> load
  let segmenterPromise = null; // one-time segmenter creation
  let videoTimestamp = 0;

  function loadBundle() {
    if (bundlePromise) return bundlePromise;
    bundlePromise = new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = BUNDLE_URL;
      s.onload = () => (window.Vision ? resolve() : reject(new Error("Vision global missing")));
      s.onerror = () => reject(new Error("bundle load failed"));
      document.head.appendChild(s);
    });
    return bundlePromise;
  }

  function ensureSegmenter() {
    if (segmenterPromise) return segmenterPromise;
    segmenterPromise = (async () => {
      await loadBundle();
      const { FilesetResolver, ImageSegmenter } = window.Vision;
      const fileset = await FilesetResolver.forVisionTasks(WASM_DIR);
      const seg = await ImageSegmenter.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: MODEL_URL, delegate: "CPU" },
        runningMode: "VIDEO",
      });
      // Throw away any failure so a retry can try again (e.g. network blip).
      segmenterPromise.catch?.(() => {});
      return seg;
    })().catch(err => {
      segmenterPromise = null; // allow retry on next call
      throw err;
    });
    return segmenterPromise;
  }

  /** Person bbox (in pixels) from a confidence array; null if no person. */
  function personBounds(arr, w, h, threshold) {
    let minX = w, minY = h, maxX = -1, maxY = -1, count = 0;
    for (let y = 0; y < h; y++) {
      const row = y * w;
      for (let x = 0; x < w; x++) {
        if (arr[row + x] > threshold) {
          if (x < minX) minX = x;
          if (x > maxX) maxX = x;
          if (y < minY) minY = y;
          if (y > maxY) maxY = y;
          count++;
        }
      }
    }
    if (maxX < 0) return null;
    // Require a minimum person size (defends against a tiny false positive).
    const minSide = Math.min(w, h);
    if (maxX - minX < minSide * 0.08 || maxY - minY < minSide * 0.12) return null;
    return { x: minX, y: minY, w: maxX - minX + 1, h: maxY - minY + 1, count };
  }

  async function loadImage(src) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error("image load failed: " + src.slice(0, 40)));
      img.src = src;
    });
  }

  /** Cover-fit draw: scale `img` to fill rect, centred, cropping overflow. */
  function coverDraw(ctx, img, rx, ry, rw, rh) {
    const scale = Math.max(rw / img.width, rh / img.height);
    const dw = img.width * scale, dh = img.height * scale;
    ctx.drawImage(img, rx + (rw - dw) / 2, ry + (rh - dh) / 2, dw, dh);
  }

  /**
   * Composite the garment over the captured frame using the person mask.
   * Returns a JPEG data URL. Throws on failure; caller decides the fallback.
   */
  async function applyPiece(frame, piece) {
    const seg = await ensureSegmenter();

    const frameImg = await loadImage(frame.dataURL);
    const garment = await loadImage(piece.img);

    // --- 1. segment -------------------------------------------------
    videoTimestamp += 33; // strictly increasing, ms-ish
    const result = seg.segmentForVideo(frameImg, videoTimestamp);
    const maskImg = result.confidenceMasks && result.confidenceMasks[0];
    if (!maskImg) throw new Error("no mask in result");
    const mw = maskImg.width, mh = maskImg.height;
    const conf = maskImg.getAsFloat32Array();
    try { maskImg.close(); } catch (e) { /* ignore */ }

    const bounds = personBounds(conf, mw, mh, 0.5);
    if (!bounds) throw new Error("no person detected");

    // --- 2. build an 8-bit alpha mask canvas (person = opaque) -------
    const maskCanvas = document.createElement("canvas");
    maskCanvas.width = mw; maskCanvas.height = mh;
    const mctx = maskCanvas.getContext("2d");
    const imgData = mctx.createImageData(mw, mh);
    for (let i = 0; i < conf.length; i++) {
      const v = Math.max(0, Math.min(255, Math.round(conf[i] * 255)));
      imgData.data[i * 4] = v;
      imgData.data[i * 4 + 1] = v;
      imgData.data[i * 4 + 2] = v;
      imgData.data[i * 4 + 3] = 255;
    }
    mctx.putImageData(imgData, 0, 0);

    // --- 3. garment layer: cover-fit into the body region, cut by mask -
    const region = piece.region || [0.3, 1.0];
    const gx = bounds.x, gy = bounds.y;
    const gw = bounds.w, gh = bounds.h;
    const rx = gx + 0; // full person width; region controls vertical band
    const ry = gy + gh * region[0];
    const rh = gh * (region[1] - region[0]);

    const layer = document.createElement("canvas");
    layer.width = mw; layer.height = mh;
    const lctx = layer.getContext("2d");
    coverDraw(lctx, garment, rx, ry, gw, rh);
    lctx.globalCompositeOperation = "destination-in";
    lctx.drawImage(maskCanvas, 0, 0);
    lctx.globalCompositeOperation = "source-over";

    // --- 4. final composite ------------------------------------------
    const out = document.createElement("canvas");
    out.width = mw; out.height = mh;
    const octx = out.getContext("2d");
    octx.drawImage(frameImg, 0, 0, mw, mh);
    octx.globalAlpha = 0.85;
    octx.drawImage(layer, 0, 0);
    octx.globalAlpha = 1;

    return { dataUrl: out.toDataURL("image/jpeg", 0.92), mode: "segmented" };
  }

  /** Stub composite (no ML): frame + garment placard. Used when the model
   *  can't be loaded so the flow still completes. */
  async function applyPieceStub(frame, piece) {
    const [frameImg, garment] = await Promise.all([
      loadImage(frame.dataURL),
      loadImage(piece.img),
    ]);
    const c = document.createElement("canvas");
    c.width = frame.w; c.height = frame.h;
    const ctx = c.getContext("2d");
    ctx.drawImage(frameImg, 0, 0, frame.w, frame.h);
    const gw = Math.round(frame.w * 0.30);
    const gh = Math.round(gw * (garment.height / garment.width));
    const x = frame.w - gw - Math.round(frame.w * 0.04);
    const y = frame.h - gh - Math.round(frame.w * 0.04);
    ctx.globalAlpha = 0.94;
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(x - 8, y - 8, gw + 16, gh + 16);
    ctx.drawImage(garment, x, y, gw, gh);
    ctx.globalAlpha = 1;
    return { dataUrl: c.toDataURL("image/jpeg", 0.92), mode: "stub" };
  }

  /** Public: try the real pipeline, fall back to the stub on any failure. */
  async function applyPieceSafe(frame, piece) {
    try {
      return await applyPiece(frame, piece);
    } catch (err) {
      console.warn("mirror: segmentation unavailable, using stub:", err);
      return applyPieceStub(frame, piece);
    }
  }

  window.FPMirrorML = {
    applyPiece: applyPieceSafe,
    prewarm: () => ensureSegmenter().then(() => "ready").catch(() => "unavailable"),
    _internal: { applyPiece, applyPieceStub, ensureSegmenter },
  };
})();
