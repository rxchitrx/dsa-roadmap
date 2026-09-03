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
  const customPanel = document.querySelector("[data-custom-tests]");
  const customList = customPanel?.querySelector("[data-custom-test-list]");
  const customSaveUrl = customPanel?.dataset.saveUrl;
  const customStatus = customPanel?.querySelector("[data-custom-status]");
  const customValidation = customPanel?.querySelector("[data-custom-validation]");
  const addCustomButton = customPanel?.querySelector("[data-add-custom-test]");
  const saveCustomButton = customPanel?.querySelector("[data-save-custom-tests]");

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

  function setCustomStatus(message, state = "saved") {
    if (!customStatus) return;
    customStatus.textContent = message;
    customStatus.dataset.state = state;
  }

  function setValidationMessage(message) {
    if (customValidation) customValidation.textContent = message || "";
  }

  function setFieldError(row, field, message) {
    const error = row.querySelector(`[data-custom-error="${field}"]`);
    if (error) error.textContent = message || "";
    const control = row.querySelector(
      field === "label" ? "[data-custom-label]" :
        field === "input" ? "[data-custom-input]" : "[data-custom-expected]",
    );
    if (control) {
      if (message) control.setAttribute("aria-invalid", "true");
      else control.removeAttribute("aria-invalid");
    }
  }

  function clearRowErrors(row) {
    setFieldError(row, "label", "");
    setFieldError(row, "input", "");
    setFieldError(row, "expected", "");
  }

  function showServerValidation(errors, message) {
    setValidationMessage(message || "Fix the highlighted custom tests.");
    for (const error of errors || []) {
      const row = customList?.querySelectorAll("[data-custom-test-row]")[error.index];
      if (row && error.field) setFieldError(row, error.field, error.message);
    }
  }

  function setEmptyState() {
    if (!customList) return;
    const hasRows = customList.querySelector("[data-custom-test-row]");
    const empty = customList.querySelector("[data-custom-empty]");
    if (!hasRows && !empty) {
      customList.appendChild(
        textElement(
          "p",
          "custom-tests-empty",
          "No custom cases yet. Add one when you have an edge case worth revisiting.",
        ),
      ).dataset.customEmpty = "";
    } else if (hasRows && empty) {
      empty.remove();
    }
  }

  function buildCustomRow(data = {}) {
    const row = document.createElement("article");
    row.className = "custom-test-row";
    row.dataset.customTestRow = "";
    if (data.id) row.dataset.caseId = String(data.id);

    const header = document.createElement("div");
    header.className = "custom-test-row-header";
    const nameLabel = document.createElement("label");
    nameLabel.appendChild(textElement("span", "field-label", "Name"));
    const nameInput = document.createElement("input");
    nameInput.className = "custom-label-input";
    nameInput.dataset.customLabel = "";
    nameInput.type = "text";
    nameInput.maxLength = 120;
    nameInput.value = data.label || "";
    nameInput.setAttribute("aria-label", "Custom test name");
    nameLabel.appendChild(nameInput);
    header.appendChild(nameLabel);

    const removeButton = document.createElement("button");
    removeButton.className = "text-button";
    removeButton.type = "button";
    removeButton.dataset.removeCustomTest = "";
    removeButton.textContent = "Remove";
    header.appendChild(removeButton);
    row.appendChild(header);

    const fields = document.createElement("div");
    fields.className = "custom-test-fields";
    const inputField = document.createElement("label");
    inputField.appendChild(textElement("span", "field-label", "Input arguments"));
    const input = document.createElement("textarea");
    input.className = "custom-json-input";
    input.dataset.customInput = "";
    input.rows = 3;
    input.spellcheck = false;
    input.setAttribute("aria-label", "Custom test input");
    input.value = valueLabel(data.input_data ?? []);
    inputField.appendChild(input);
    inputField.appendChild(textElement("span", "custom-field-error", ""));
    inputField.lastElementChild.dataset.customError = "input";
    inputField.lastElementChild.setAttribute("role", "alert");
    fields.appendChild(inputField);

    const expectedField = document.createElement("label");
    expectedField.appendChild(textElement("span", "field-label", "Expected output"));
    const expected = document.createElement("textarea");
    expected.className = "custom-json-input";
    expected.dataset.customExpected = "";
    expected.rows = 3;
    expected.spellcheck = false;
    expected.setAttribute("aria-label", "Custom test expected output");
    expected.value = valueLabel(
      Object.prototype.hasOwnProperty.call(data, "expected_output")
        ? data.expected_output
        : null,
    );
    expectedField.appendChild(expected);
    expectedField.appendChild(textElement("span", "custom-field-error", ""));
    expectedField.lastElementChild.dataset.customError = "expected";
    expectedField.lastElementChild.setAttribute("role", "alert");
    fields.appendChild(expectedField);
    row.appendChild(fields);
    const labelError = textElement("span", "custom-field-error", "");
    labelError.dataset.customError = "label";
    labelError.setAttribute("role", "alert");
    row.appendChild(labelError);
    return row;
  }

  function renderCustomCases(cases) {
    if (!customList) return;
    customList.replaceChildren();
    for (const caseData of cases || []) {
      customList.appendChild(buildCustomRow(caseData));
    }
    setEmptyState();
  }

  function collectCustomCases() {
    if (!customList) return [];
    setValidationMessage("");
    let invalid = false;
    const cases = [];
    for (const row of customList.querySelectorAll("[data-custom-test-row]")) {
      clearRowErrors(row);
      const label = row.querySelector("[data-custom-label]").value.trim();
      const inputText = row.querySelector("[data-custom-input]").value.trim();
      const expectedText = row.querySelector("[data-custom-expected]").value.trim();
      if (!label) {
        setFieldError(row, "label", "Add a short name for this test.");
        invalid = true;
      } else if (label.length > 120) {
        setFieldError(row, "label", "Keep the test name to 120 characters or fewer.");
        invalid = true;
      }

      let inputData;
      try {
        inputData = JSON.parse(inputText);
        if (!Array.isArray(inputData)) throw new Error("not an array");
      } catch (_error) {
        setFieldError(row, "input", "Input must be valid JSON in an array of arguments.");
        invalid = true;
      }

      let expectedOutput;
      try {
        if (!expectedText) throw new Error("missing expected output");
        expectedOutput = JSON.parse(expectedText);
      } catch (_error) {
        setFieldError(row, "expected", "Expected output must be valid JSON; type null for None.");
        invalid = true;
      }

      cases.push({
        id: row.dataset.caseId ? Number(row.dataset.caseId) : null,
        label,
        input_data: inputData,
        expected_output: expectedOutput,
      });
    }
    if (invalid) {
      setValidationMessage("Fix the highlighted custom tests before continuing.");
      return null;
    }
    return cases;
  }

  function markCustomDirty() {
    setCustomStatus("Unsaved custom tests", "dirty");
    setValidationMessage("");
  }

  async function saveCustomTests() {
    const cases = collectCustomCases();
    if (cases === null || !customSaveUrl) return false;
    const csrfToken = form?.querySelector("[name=csrfmiddlewaretoken]")?.value;
    saveCustomButton.disabled = true;
    setCustomStatus("Saving…", "saving");
    try {
      const response = await fetch(customSaveUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken || "",
          "X-Requested-With": "XMLHttpRequest",
        },
        body: JSON.stringify({ cases }),
      });
      const payload = await response.json();
      if (!response.ok || !payload.saved) {
        showServerValidation(payload.errors, payload.message);
        setCustomStatus("Needs your attention", "error");
        return false;
      }
      renderCustomCases(payload.cases);
      setCustomStatus("Saved just now", "saved");
      return true;
    } catch (_error) {
      setCustomStatus("Could not save — retry in a moment.", "error");
      return false;
    } finally {
      saveCustomButton.disabled = false;
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
      const caseLabel = document.createElement("span");
      caseLabel.appendChild(
        textElement(
          "span",
          "run-case-source",
          detail.kind === "custom" ? "Custom" : "Default",
        ),
      );
      caseLabel.appendChild(
        document.createTextNode(` ${detail.label || "Visible test"}`),
      );
      item.appendChild(caseLabel);
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

  customList?.addEventListener("input", (event) => {
    if (event.target.matches("[data-custom-label], [data-custom-input], [data-custom-expected]")) {
      const row = event.target.closest("[data-custom-test-row]");
      if (row) clearRowErrors(row);
      markCustomDirty();
    }
  });

  customList?.addEventListener("click", (event) => {
    const removeButton = event.target.closest("[data-remove-custom-test]");
    if (!removeButton) return;
    removeButton.closest("[data-custom-test-row]")?.remove();
    setEmptyState();
    markCustomDirty();
  });

  addCustomButton?.addEventListener("click", () => {
    customList?.querySelector("[data-custom-empty]")?.remove();
    const nextNumber = (customList?.querySelectorAll("[data-custom-test-row]").length || 0) + 1;
    customList?.appendChild(
      buildCustomRow({
        label: `Custom case ${nextNumber}`,
        input_data: [],
        expected_output: null,
      }),
    );
    markCustomDirty();
    customList?.lastElementChild?.querySelector("[data-custom-label]")?.focus();
  });

  saveCustomButton?.addEventListener("click", saveCustomTests);

  button.addEventListener("click", async () => {
    const customCases = collectCustomCases();
    if (customCases === null) {
      result.dataset.state = "request_error";
      result.replaceChildren(
        textElement("p", "run-outcome", "Custom tests need attention"),
        textElement("p", "run-message", "Fix the highlighted cases before execution."),
      );
      return;
    }
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
        body: JSON.stringify({ code: editor.value, custom_tests: customCases }),
      });
      const payload = await response.json();
      if (!response.ok || !payload.run) {
        if (payload.validation_errors) {
          showServerValidation(payload.validation_errors, payload.message);
          setCustomStatus("Needs your attention", "error");
        }
        throw new Error(payload.message || "The solution could not be run.");
      }
      if (payload.custom_tests) renderCustomCases(payload.custom_tests);
      setCustomStatus(
        payload.custom_tests?.length ? "Saved with latest run" : "No custom tests saved",
        "saved",
      );
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
