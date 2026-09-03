(() => {
  const root = document.querySelector("[data-cutoff-at]");
  const timer = document.querySelector("[data-testid='assessment-timer']");
  if (!root || !timer || root.dataset.status !== "in_progress") return;

  const cutoff = Date.parse(root.dataset.cutoffAt);
  const format = (seconds) => {
    const minutes = Math.floor(seconds / 60).toString().padStart(2, "0");
    const remainder = (seconds % 60).toString().padStart(2, "0");
    return `${minutes}:${remainder}`;
  };
  const render = () => {
    const seconds = Math.max(0, Math.floor((cutoff - Date.now()) / 1000));
    timer.textContent = seconds ? format(seconds) : "Time reached";
    if (!seconds) window.clearInterval(interval);
  };
  const interval = window.setInterval(render, 1000);
  render();
})();
