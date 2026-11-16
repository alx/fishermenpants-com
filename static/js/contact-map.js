/* Fishermen Pants — Leaflet map on the contact page. */
(function () {
  const el = document.getElementById("contact-map");
  if (!el || typeof L === "undefined") return;

  const lat = parseFloat(el.dataset.lat) || 9.4693;
  const lng = parseFloat(el.dataset.lng) || 100.0492;
  const name = el.dataset.name || "GAYA";
  const maps = el.dataset.maps || "";

  const map = L.map(el, { scrollWheelZoom: false }).setView([lat, lng], 16);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  }).addTo(map);

  const marker = L.marker([lat, lng]).addTo(map);
  marker.bindPopup(
    `<strong>${name}</strong><br>156, beach 7 Had Lamai Rd<br>Lamai Beach, Koh Samui` +
      (maps ? `<br><a href="${maps}" target="_blank" rel="noopener">Directions</a>` : "")
  );

  // Scroll-zoom off until the user clicks the map, so page scrolling stays natural.
  map.on("click", () => map.scrollWheelZoom.enable());
  map.on("mouseout", () => map.scrollWheelZoom.disable());

  // Keep tiles crisp after the container is laid out / resized.
  window.addEventListener("resize", () => map.invalidateSize());
  setTimeout(() => map.invalidateSize(), 200);
})();
