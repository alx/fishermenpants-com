/* Visit page — PhotoSwipe lightbox for the shop gallery.
 *
 * Progressive enhancement: every thumbnail is a plain <a href="full-image">
 * that works with JS disabled or if this fails to load. This only upgrades the
 * click into a lightbox. Loaded on /visit/ only.
 */
(function () {
  "use strict";

  var gallery = document.querySelector(".visit-gallery");
  if (!gallery) return;
  // No links enhanced -> nothing to do (and no needless downloads).
  if (!gallery.querySelector("a.visit-photo-link")) return;

  // Respect the user's motion preference: skip the zoom transition entirely.
  var reduced = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);

  // Dynamic imports so a missing/blocked asset leaves the plain links working
  // instead of throwing at parse time.
  Promise.all([
    import("/photoswipe/photoswipe-lightbox.esm.min.js"),
    import("/photoswipe/photoswipe.esm.min.js"),
  ])
    .then(function (mods) {
      var PhotoSwipeLightbox = mods[0].default;
      var PhotoSwipe = mods[1].default;

      var lightbox = new PhotoSwipeLightbox({
        gallery: ".visit-gallery",
        children: "a.visit-photo-link",
        pswpModule: function () { return Promise.resolve(PhotoSwipe); },
        bgOpacity: 0.92,
        showHideAnimationType: reduced ? "none" : "zoom",
        paddingFn: function () { return { top: 20, bottom: 20, left: 10, right: 10 }; },
      });

      // Caption from the anchor's data attribute, falling back to the thumb alt.
      lightbox.on("uiRegister", function () {
        lightbox.pswp.ui.registerElement({
          name: "custom-caption",
          order: 9,
          isButton: false,
          appendTo: "root",
          html: "",
          onInit: function (el, pswp) {
            pswp.on("change", function () {
              var cur = pswp.currSlide && pswp.currSlide.data ? pswp.currSlide.data.element : null;
              var caption = cur ? (cur.getAttribute("data-pswp-caption") || "") : "";
              if (!caption) {
                var img = cur ? cur.querySelector("img") : null;
                caption = img ? (img.getAttribute("alt") || "") : "";
              }
              el.textContent = caption || "";
              el.className = caption ? "pswp__custom-caption" : "";
            });
          },
        });
      });

      // Return focus to the clicked thumbnail when the lightbox closes, so
      // keyboard users are never stranded at the top of the document.
      lightbox.on("close", function () {
        var d = lightbox.pswp && lightbox.pswp.currSlide && lightbox.pswp.currSlide.data;
        var t = d ? d.element : null;
        if (t && typeof t.focus === "function") {
          try { t.focus({ preventScroll: true }); } catch (e) { t.focus(); }
        }
      });

      lightbox.init();
    })
    .catch(function () {
      /* Leave the plain links in place — they open the full image. */
    });
})();
