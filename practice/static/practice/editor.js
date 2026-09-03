(() => {
  const editor = document.querySelector("[data-draft-editor]");
  if (!editor) return;

  const form = editor.closest("form");
  const status = document.querySelector("[data-draft-status]");
  const revisionLabel = document.querySelector("[data-draft-revision]");
  const saveUrl = editor.dataset.saveUrl;
  const debounceMs = Number(editor.dataset.debounceMs || 600);

  let serverRevision = Number(editor.dataset.revision || 1);
  let changeSequence = 0;
  let timerId = null;
  let activeRequest = null;

  function setStatus(message, state) {
    if (!status) return;
    status.textContent = message;
    status.dataset.state = state;
  }

  function updateRevision(revision) {
    serverRevision = Number(revision);
    editor.dataset.revision = String(serverRevision);
    if (revisionLabel) revisionLabel.textContent = `Revision ${serverRevision}`;
  }

  function queueSave() {
    changeSequence += 1;
    clearTimeout(timerId);
    setStatus("Unsaved changes", "dirty");
    const sequenceAtQueue = changeSequence;
    timerId = setTimeout(() => saveDraft(sequenceAtQueue), debounceMs);
  }

  async function saveDraft(sequenceAtStart) {
    const codeAtStart = editor.value;
    const revisionAtStart = serverRevision;
    const csrfToken = form?.querySelector("[name=csrfmiddlewaretoken]")?.value;

    if (activeRequest) activeRequest.abort();
    activeRequest = new AbortController();
    setStatus("Saving…", "saving");

    try {
      const response = await fetch(saveUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken || "",
          "X-Requested-With": "XMLHttpRequest",
        },
        body: JSON.stringify({ code: codeAtStart, base_revision: revisionAtStart }),
        signal: activeRequest.signal,
      });
      const payload = await response.json();

      if (response.status === 409 && payload.stale) {
        updateRevision(payload.revision);
        if (sequenceAtStart === changeSequence) {
          setStatus("Newer draft found; saving your latest text…", "saving");
          timerId = setTimeout(() => saveDraft(changeSequence), 0);
        }
        return;
      }

      if (!response.ok || !payload.saved) {
        throw new Error(payload.message || "Draft could not be saved.");
      }

      updateRevision(payload.revision);
      if (sequenceAtStart === changeSequence && editor.value === codeAtStart) {
        setStatus("Saved just now", "saved");
      }
    } catch (error) {
      if (error.name === "AbortError") return;
      setStatus("Could not save — keep this tab open and retry.", "error");
    } finally {
      activeRequest = null;
    }
  }

  editor.addEventListener("input", queueSave);
})();
