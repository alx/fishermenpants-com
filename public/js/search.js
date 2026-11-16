/* Fishermen Pants — client-side search over a build-time JSON index. */
(function () {
  const results = document.getElementById("search-results");
  if (!results) return;
  const input = document.getElementById("search-input");
  const status = document.getElementById("search-status");

  // prefill from ?q=
  const q0 = new URLSearchParams(location.search).get("q");
  if (q0 && input) input.value = q0;

  function money(n) { return "$" + Number(n).toFixed(2); }

  function norm(s) { return (s || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, ""); }

  function score(doc, q) {
    let s = 0;
    const t = norm(doc.title), h = norm(doc.text);
    if (t === q) s += 100;
    if (t.startsWith(q)) s += 60;
    if (t.includes(q)) s += 40;
    if (h.includes(q)) s += 10;
    return s;
  }

  function render(list, q) {
    results.innerHTML = "";
    if (!list.length) {
      status.textContent = q ? `No matches for “${q}”.` : "";
      return;
    }
    status.textContent = `${list.length} result${list.length === 1 ? "" : "s"} for “${q}”`;
    for (const r of list) {
      const a = document.createElement("a");
      a.className = "product-card";
      a.href = r.url;
      a.innerHTML = `
        <span class="pc-img"><img src="${r.image || ""}" alt="" loading="lazy"></span>
        <span class="pc-info">
          <span class="pc-title">${r.title}</span>
          <span class="pc-price">${r.price || r.kind}</span>
        </span>`;
      results.appendChild(a);
    }
  }

  function run(q) {
    if (!q) { render([], ""); return; }
    const nq = norm(q);
    const hits = [];
    for (const doc of index.docs) {
      const s = score(doc, nq);
      if (s > 0) hits.push({ doc, s });
    }
    hits.sort((a, b) => b.s - a.s);
    render(hits.slice(0, 60).map(x => x.doc), q);
  }

  let index = null;
  fetch(window.FP_BASE + "js/search-index.json").then(r => r.json()).then(idx => {
    index = idx;
    run(q0 || "");
  }).catch(() => { status.textContent = "Search index not available."; });

  if (input) {
    input.addEventListener("input", () => {
      const v = input.value.trim();
      history.replaceState(null, "", v ? `?q=${encodeURIComponent(v)}` : location.pathname);
      run(v);
    });
  }
})();
