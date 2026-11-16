/* Fishermen Pants — Formspree newsletter ("Get 10% off your first order"). */
(function () {
  const form = document.getElementById("formspree-form");
  if (!form) return;
  const note = document.getElementById("form-note");
  form.addEventListener("submit", async e => {
    e.preventDefault();
    const endpoint = form.action;
    if (!endpoint || endpoint.includes("your-form-id")) {
      note.hidden = false;
      note.textContent = "Newsletter endpoint not configured yet (params.formspree.endpoint in hugo.toml).";
      return;
    }
    note.hidden = false;
    note.textContent = "Sending…";
    try {
      const res = await fetch(endpoint, {
        method: "POST",
        body: new FormData(form),
        headers: { Accept: "application/json" }
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        note.textContent = "Thank you! Check your inbox for your 10% off code.";
        form.reset();
        document.dispatchEvent(new CustomEvent("fp:newsletter"));
      } else {
        note.textContent = data.message || "Something went wrong — please email us directly.";
      }
    } catch {
      note.textContent = "Network error — please try again.";
    }
  });
})();
