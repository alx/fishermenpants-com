# Mirror — ML/Inference Research (bead org-o39g)

Date: 2026-11-12 · Status: **decision made, numbers measured**

## Question

Which try-on approach is feasible for the /pages/mirror/ experiment, and what is the
quality/latency compromise between local GPU, in-browser WASM on low-end CPU, and
server-side inference?

## Measured, not guessed

Benchmarked the actual shipping stack in headless Chromium on the target-class
hardware available here (Intel i5-7200U, 2015 Skylake U-series, 4 threads — a real
low-end CPU, no GPU acceleration in the browser WASM path). Wall-clock A/B method:
identical runs with N=0 vs N=80 inferences; per-frame cost = Δwall/80.

Model: MediaPipe `selfie_segmenter` (249 KB float16 TFLite) via
`@mediapipe/tasks-vision` WASM, `segmentForVideo` video mode, 1086×1280 photo input.

| Condition | Per-frame cost | Effective |
|---|---|---|
| Input 1086×1280 | ~36 ms | ~27 fps |
| Input 543×640 | ~26 ms | ~38 fps |

Notes from the runs:

- **The model runs at a fixed internal resolution** — dropping input from 1080 to 640
  only saved ~10 ms (resize + mask-upscale cost), because the network FLOPs are
  constant. Input size is *not* the performance lever; the model is.
- Cold start: WASM init ~0 ms after first page, model load ~60–110 ms, first
  inference adds no visible cliff.
- Output verified: valid person mask (37.7% of a group-shop photo classified
  person, rest background — sane for that frame).
- **Payload:** WASM runtime 14.7 MB raw / **4.2 MB gzipped** (one file loaded),
  model 0.25 MB, JS glue 0.16 MB → **~4.4 MB gz** one-time when entering the mirror
  page. Must be lazy-loaded, never in the base site weight.

## Option comparison

| # | Approach | Low-end-CPU latency | Quality | Cost/infra | Verdict |
|---|---|---|---|---|---|
| a | **In-browser WASM** (MediaPipe tasks-vision) + canvas compositing | **~26–36 ms/frame, real-time** | Silhouette-grade person mask; garment composited over it | ~4.4 MB one-time download, **zero server cost, image never leaves the device** | **Ship this** |
| b | In-browser ONNX (onnxruntime-web), same model class | Same order (same kernels, similar speed) | Same class of model | Same payload, more integration work | No advantage over (a) |
| c | User's GPU via WebGPU | Faster where available | Same or better | 2015-era target has no WebGPU; helps only premium devices | Phase-2 optional flag |
| d | Server-side GPU diffusion VTON (IDM-VTON / CatVTON / OOTDiffusion) | Seconds per image + network round-trip | Best — true garment re-render | Server GPU $, photo upload (privacy), wait UX | Wrong tool for an experiment page |

## Decision

**Option (a): in-browser WASM segmentation + canvas compositing.**

- Real-time (25–30 fps headroom) on a 2015 laptop CPU — the "low-end CPU WASM"
  branch the plan asked about **clears the bar**, no server, no GPU, no upload.
- The garment is composited over the segmented person (cut person + garment
  layer + restore), which is exactly what `applyPiece()` in `static/js/mirror.js`
  is stubbed for. Swap the stub for: load tasks-vision lazily on entering the page,
  run `selfie_segmenter` on the captured frame, composite.
- **Do not** attempt diffusion-grade VTON in-browser: even quantised, a
  billion-parameter diffusion is minutes-per-frame on this CPU class. Server
  diffusion is a possible Phase-3 "pro mode" if the experiment earns it — it
  changes the privacy story (upload) and adds per-use cost.
- If richer garment drape is wanted later without leaving the browser: add
  MediaPipe **pose landmarks** (second small WASM model, same runtime already
  loaded) to warp the garment layer by pose. Cheap to add; not needed for v1.

## Integration notes for the implementer

- npm package `@mediapipe/tasks-vision`; browser API (measured, working):
  `FilesetResolver.forVisionTasks('wasm/')` →
  `ImageSegmenter.createFromOptions(fileset, { baseOptions: { modelAssetPath, delegate:'CPU' }, runningMode:'VIDEO' })` →
  `seg.segmentForVideo(imageBitmap, increasingTimestamp)`.
  Note: `segment()` (image mode) vs `segmentForVideo()` (video mode) are exclusive
  per runningMode; timestamps must be strictly increasing.
- Result: `res.confidenceMasks[0].getAsFloat32Array()` (Float32Array of person
  probabilities, 1.0 = person). Masks are MPImage objects with `.close()`.
- Model URL (GCS, verified 2026-11-12):
  `https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter/float16/latest/selfie_segmenter.tflite`
  (the older `selfie_multisegmenter/float32/1/...` URL is **dead** — 404).
- Lazy-load: load the WASM runtime only when the user enters the mirror page,
  ideally only when they press Capture, to keep the base site fast.
