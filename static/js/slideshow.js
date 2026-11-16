// Hero slideshow: crossfade, dots, arrows, autoplay, pause on hover/focus.
(function () {
  const root = document.getElementById("hero-slideshow");
  if (!root) return;
  const slides = Array.from(root.querySelectorAll(".hero-slide"));
  const dots = Array.from(root.querySelectorAll(".hero-dot"));
  const prev = root.querySelector(".hero-arrow--prev");
  const next = root.querySelector(".hero-arrow--next");
  if (slides.length < 2) return;

  let idx = 0;
  let timer = null;
  const AUTOPLAY_MS = 6500;

  function show(i) {
    idx = (i + slides.length) % slides.length;
    slides.forEach((s, k) => s.classList.toggle("is-active", k === idx));
    dots.forEach((d, k) => d.classList.toggle("is-active", k === idx));
  }

  function play() {
    stop();
    timer = setInterval(() => show(idx + 1), AUTOPLAY_MS);
  }
  function stop() {
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
  }

  if (prev) prev.addEventListener("click", () => { show(idx - 1); play(); });
  if (next) next.addEventListener("click", () => { show(idx + 1); play(); });
  dots.forEach((d, k) => d.addEventListener("click", () => { show(k); play(); }));

  root.addEventListener("mouseenter", stop);
  root.addEventListener("mouseleave", play);
  root.addEventListener("focusin", stop);
  root.addEventListener("focusout", play);
  document.addEventListener("visibilitychange", () => (document.hidden ? stop() : play()));

  show(0);
  play();
})();
