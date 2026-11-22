// Small progressive enhancements. The app works without JavaScript; this only improves feedback.
document.addEventListener("DOMContentLoaded", function () {
  // 1) Loading state on forms that can take a moment (uploads, grading, analysis)
  document.querySelectorAll("form[data-loading]").forEach(function (form) {
    form.addEventListener("submit", function () {
      var btn = form.querySelector("[type=submit]");
      if (!btn || form.dataset.submitted) { return; }
      form.dataset.submitted = "1";
      btn.classList.add("is-loading");
      btn.setAttribute("aria-busy", "true");
      btn.textContent = form.dataset.loading;
    });
  });
  // 2) Confirm before destructive actions
  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      if (!window.confirm(form.dataset.confirm)) { e.preventDefault(); }
    });
  });
  // 3) Dashboard charts (data comes from json_script blocks rendered by the server)
  function readData(id) { var el = document.getElementById(id); return el ? JSON.parse(el.textContent) : null; }
  if (window.Chart) {
    var ev = readData("evidence-data");
    var evCanvas = document.getElementById("evidenceChart");
    if (ev && evCanvas && ev.values.length) {
      new Chart(evCanvas, { type: "doughnut",
        data: { labels: ev.labels, datasets: [{ data: ev.values, backgroundColor: ["#2563eb", "#60a5fa", "#94a3b8", "#0b1f3a", "#cbd5e1", "#1d4ed8"] }] },
        options: { maintainAspectRatio: false, plugins: { legend: { position: "bottom" } } } });
    }
    var tr = readData("trend-data");
    var trCanvas = document.getElementById("trendChart");
    if (tr && trCanvas && tr.score.length >= 2) {
      new Chart(trCanvas, { type: "line",
        data: { labels: tr.labels, datasets: [
          { label: "Expected readiness (%)", data: tr.score, borderColor: "#2563eb", backgroundColor: "#2563eb", tension: 0.25 },
          { label: "Conservative (%)", data: tr.conservative, borderColor: "#94a3b8", backgroundColor: "#94a3b8", borderDash: [5, 4], tension: 0.25 }] },
        options: { maintainAspectRatio: false, scales: { y: { min: 0, max: 100 } }, plugins: { legend: { position: "bottom" } } } });
    }
  }
});
