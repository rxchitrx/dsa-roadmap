(function () {
  function formatElapsed(totalSeconds) {
    var seconds = Math.max(0, Math.floor(totalSeconds));
    var hours = Math.floor(seconds / 3600);
    var minutes = Math.floor((seconds % 3600) / 60);
    var remainder = seconds % 60;

    return [hours, minutes, remainder]
      .map(function (value) {
        return String(value).padStart(2, "0");
      })
      .join(":");
  }

  function refreshTimer(panel) {
    var elapsed = Number(panel.dataset.elapsedSeconds || 0);
    var status = panel.dataset.status;
    var runningSince = Date.parse(panel.dataset.runningSince || "");

    if (status === "running" && Number.isFinite(runningSince)) {
      elapsed += Math.max(0, (Date.now() - runningSince) / 1000);
    }

    var readout = panel.querySelector("[data-testid=timer-readout]");
    if (readout) {
      readout.textContent = formatElapsed(elapsed);
    }
  }

  function refreshAllTimers() {
    document.querySelectorAll("[data-timer-panel]").forEach(refreshTimer);
  }

  refreshAllTimers();
  window.setInterval(refreshAllTimers, 1000);
})();
