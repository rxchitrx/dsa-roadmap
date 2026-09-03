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

(() => {
  const button = document.querySelector("[data-run-tests]");
  const editor = document.querySelector("[data-draft-editor]");
  const result = document.querySelector("[data-run-result]");
  if (!button || !editor || !result) return;

  const form = editor.closest("form");
  const runUrl = button.dataset.runUrl;

  function textElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    element.textContent = text;
    return element;
  }

  function valueLabel(value) {
    try {
      return JSON.stringify(value);
    } catch (_error) {
      return String(value);
    }
  }

  function renderRun(payload) {
    result.dataset.state = payload.status || "runtime_error";
    result.replaceChildren(
      textElement("p", "run-outcome", payload.status_label || "Run result"),
      textElement("p", "run-summary", payload.summary || "The runner returned no summary."),
    );

    if (payload.message) {
      result.appendChild(textElement("p", "run-message", payload.message));
    }

    const cases = document.createElement("ol");
    cases.className = "run-cases";
    for (const detail of payload.details || []) {
      const item = document.createElement("li");
      item.dataset.state = detail.passed ? "passed" : "failed";
      item.appendChild(textElement("span", "run-case-label", detail.label || "Visible test"));
      item.appendChild(
        textElement(
          "strong",
          "run-case-status",
          detail.passed ? "Passed" : "Needs another look",
        ),
      );
      if (detail.message) item.appendChild(textElement("small", "", detail.message));
      if (!detail.passed && Object.prototype.hasOwnProperty.call(detail, "expected")) {
        item.appendChild(
          textElement(
            "small",
            "run-case-comparison",
            `Expected ${valueLabel(detail.expected)} · got ${valueLabel(detail.actual)}`,
          ),
        );
      }
      if (!detail.passed && Object.prototype.hasOwnProperty.call(detail, "expected_args")) {
        item.appendChild(
          textElement(
            "small",
            "run-case-comparison",
            `Expected arguments ${valueLabel(detail.expected_args)} · got ${valueLabel(detail.actual_args)}`,
          ),
        );
      }
      cases.appendChild(item);
    }
    if (cases.children.length) result.appendChild(cases);
  }

  button.addEventListener("click", async () => {
    const csrfToken = form?.querySelector("[name=csrfmiddlewaretoken]")?.value;
    button.disabled = true;
    button.textContent = "Running…";
    result.dataset.state = "running";
    result.replaceChildren(textElement("p", "run-outcome", "Running visible tests…"));

    try {
      const response = await fetch(runUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken || "",
          "X-Requested-With": "XMLHttpRequest",
        },
        body: JSON.stringify({ code: editor.value }),
      });
      const payload = await response.json();
      if (!response.ok || !payload.run) {
        throw new Error(payload.message || "The solution could not be run.");
      }
      renderRun(payload);
    } catch (error) {
      result.dataset.state = "request_error";
      result.replaceChildren(
        textElement("p", "run-outcome", "Could not run the solution"),
        textElement("p", "run-message", error.message),
      );
    } finally {
      button.disabled = false;
      button.textContent = "Run visible tests";
    }
  });
})();
