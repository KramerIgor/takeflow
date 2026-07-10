import {
  createReferencePreviewNode,
  insertReferenceToken,
  referenceLimitForForm,
  renderPromptEditorFromSource,
  renderReferenceTokenMenu,
  shouldShowReferenceTokenMenu,
  syncPromptSourceFromEditor
} from "./reference-ui.js";

// Single Generation references, edit prompt and paid confirmation
document.addEventListener("DOMContentLoaded", function () {
      const form = document.querySelector(".single-generation-form");
      if (!form) {
        return;
      }

      const promptField = form.elements.prompt;
      const promptEditor = form.querySelector("[data-prompt-rich-editor]");
      const nameField = form.elements.generation_name;
      const fileInput = form.querySelector("[data-reference-files]");
      const dropzone = form.querySelector("[data-single-dropzone]");
      const refsList = form.querySelector("[data-attached-refs]");
      const existingInputs = form.querySelector("[data-existing-reference-inputs]");
      const tokenMenu = form.querySelector("[data-ref-token-menu]");
      const pickerButton = form.querySelector("[data-trigger-reference-picker]");
      const counterNode = form.querySelector("[data-reference-count]");
      const attachedFiles = [];
      const existingRefs = [];
      let visibleRefs = [];

      function mediaTypeForName(name) {
        const suffix = String(name || "").toLowerCase().split(".").pop();
        if (["png", "jpg", "jpeg", "webp"].includes(suffix)) {
          return "image";
        }
        if (["mp4", "mov", "webm", "mkv"].includes(suffix)) {
          return "video";
        }
        if (["mp3", "wav", "m4a", "aac", "ogg", "flac"].includes(suffix)) {
          return "audio";
        }
        return "unsupported";
      }

      function syncFileInput() {
        const transfer = new DataTransfer();
        for (const file of attachedFiles) {
          transfer.items.add(file);
        }
        fileInput.files = transfer.files;
      }

      function syncExistingInputs() {
        existingInputs.innerHTML = "";
        for (const ref of existingRefs) {
          if (!ref.local_path) {
            continue;
          }
          const input = document.createElement("input");
          input.type = "hidden";
          input.name = "existing_reference_paths";
          input.value = ref.local_path;
          existingInputs.appendChild(input);

          const metadataInput = document.createElement("input");
          metadataInput.type = "hidden";
          metadataInput.name = "existing_reference_metadata";
          metadataInput.value = JSON.stringify({
            local_path: ref.local_path,
            original_filename: ref.original_filename || ref.filename || "",
            filename: ref.filename || ref.original_filename || "",
            media_type: ref.media_type || mediaTypeForName(ref.filename || ref.local_path)
          });
          existingInputs.appendChild(metadataInput);
        }
      }

      function currentRefs() {
        const uploaded = attachedFiles.map(function (file, index) {
          return {
            kind: "file",
            index: index,
            filename: file.name,
            media_type: mediaTypeForName(file.name),
            preview_url: URL.createObjectURL(file)
          };
        });
        const existing = existingRefs.map(function (ref, index) {
          return {
            kind: "existing",
            index: index,
            filename: ref.filename || ref.original_filename || "reference",
            media_type: ref.media_type || mediaTypeForName(ref.filename || ref.local_path),
            preview_url: ref.preview_url || "",
            local_path: ref.local_path || "",
            api_warning: ref.api_warning || ""
          };
        });
        return existing.concat(uploaded);
      }

      function syncRefState(refs) {
        form.dataset.hasVideoReference = (refs || []).some(function (ref) {
          return ref.media_type === "video";
        }) ? "true" : "false";
        form.dispatchEvent(new CustomEvent("seedance:refs-changed", { bubbles: true }));
      }

      function currentReferenceLimit() {
        return referenceLimitForForm(form);
      }

      function updateReferenceCounter(count) {
        const limit = currentReferenceLimit();
        const atLimit = count >= limit;
        if (counterNode) {
          counterNode.textContent = count + "/" + limit;
          counterNode.classList.toggle("is-full", atLimit);
        }
        if (pickerButton) {
          pickerButton.disabled = atLimit;
          pickerButton.setAttribute("aria-disabled", atLimit ? "true" : "false");
        }
      }

      function insertToken(filename) {
        insertReferenceToken(promptEditor, promptField, filename, visibleRefs);
        hideTokenMenu();
      }

      function renderRefs() {
        const refs = currentRefs();
        visibleRefs = refs;
        refsList.innerHTML = "";
        syncRefState(refs);
        updateReferenceCounter(refs.length);
        renderPromptEditorFromSource(promptEditor, promptField, refs);
        if (!refs.length) {
          hideTokenMenu();
          return;
        }

        for (const ref of refs) {
          const card = document.createElement("div");
          card.className = "ref-card";
          card.tabIndex = 0;
          card.title = ref.filename;
          card.setAttribute("aria-label", "Insert " + ref.filename);
          card.appendChild(createReferencePreviewNode(ref));

          const remove = document.createElement("button");
          remove.type = "button";
          remove.className = "ref-remove-button";
          remove.setAttribute("aria-label", (window.seedanceTranslate ? window.seedanceTranslate("remove") : "Remove") + " " + ref.filename);
          remove.textContent = "×";
          remove.addEventListener("click", function (event) {
            event.stopPropagation();
            if (ref.kind === "file") {
              attachedFiles.splice(ref.index, 1);
              syncFileInput();
            } else {
              existingRefs.splice(ref.index, 1);
              syncExistingInputs();
            }
            renderRefs();
          });

          card.addEventListener("click", function () {
            insertToken(ref.filename);
          });
          card.addEventListener("keydown", function (event) {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              insertToken(ref.filename);
            }
          });

          card.appendChild(remove);
          refsList.appendChild(card);
        }
      }

      function addFiles(files) {
        const availableSlots = Math.max(0, currentReferenceLimit() - currentRefs().length);
        let added = 0;
        for (const file of Array.from(files || [])) {
          if (added >= availableSlots) {
            break;
          }
          if (mediaTypeForName(file.name) === "unsupported") {
            continue;
          }
          attachedFiles.push(file);
          added += 1;
        }
        syncFileInput();
        renderRefs();
      }

      function hideTokenMenu() {
        tokenMenu.hidden = true;
        tokenMenu.innerHTML = "";
      }

      function showTokenMenu() {
        const refs = visibleRefs.length ? visibleRefs : currentRefs();
        if (!refs.length) {
          hideTokenMenu();
          return;
        }

        renderReferenceTokenMenu(tokenMenu, refs, promptEditor, dropzone, insertToken);
      }

      function maybeShowTokenMenu() {
        if (shouldShowReferenceTokenMenu(promptEditor)) {
          showTokenMenu();
        } else {
          hideTokenMenu();
        }
      }

      fileInput.addEventListener("change", function () {
        addFiles(fileInput.files);
      });
      if (pickerButton) {
        pickerButton.addEventListener("click", function () {
          fileInput.click();
        });
      }
      for (const eventName of ["dragenter", "dragover"]) {
        dropzone.addEventListener(eventName, function (event) {
          event.preventDefault();
          dropzone.classList.add("drag-over");
        });
      }

      for (const eventName of ["dragleave", "drop"]) {
        dropzone.addEventListener(eventName, function () {
          dropzone.classList.remove("drag-over");
        });
      }

      dropzone.addEventListener("drop", function (event) {
        event.preventDefault();
        addFiles(event.dataTransfer.files);
      });

      promptEditor.addEventListener("input", function () {
        syncPromptSourceFromEditor(promptEditor, promptField);
        maybeShowTokenMenu();
      });
      promptEditor.addEventListener("keyup", maybeShowTokenMenu);
      promptEditor.addEventListener("click", hideTokenMenu);
      promptField.addEventListener("input", function () {
        renderPromptEditorFromSource(promptEditor, promptField, visibleRefs);
      });
      document.addEventListener("seedance:language-changed", renderRefs);
      if (form.elements.model) {
        form.elements.model.addEventListener("change", renderRefs);
      }

      function applyHistoryItem(item) {
        nameField.value = item.name || "";
        promptField.value = item.prompt || "";
        form.elements.model.value = item.model || "seedance-2.0";
        if (window.seedanceSyncModelOptions) {
          window.seedanceSyncModelOptions(form, {
            duration: item.duration || "4",
            resolution: item.resolution || "480p",
            aspect_ratio: item.aspect_ratio || "16:9"
          });
        } else {
          form.elements.duration.value = item.duration || "4";
          form.elements.resolution.value = item.resolution || "480p";
          form.elements.aspect_ratio.value = item.aspect_ratio || "16:9";
        }
        form.elements.seed.value = item.seed ?? -1;
        form.elements.generate_audio.checked = Boolean(item.generate_audio);
        form.elements.return_last_frame.checked = Boolean(item.return_last_frame);
        attachedFiles.splice(0, attachedFiles.length);
        existingRefs.splice(0, existingRefs.length);

        for (const ref of item.refs || []) {
          if (ref.local_path && ref.exists !== false) {
            existingRefs.push(ref);
          }
        }

        syncFileInput();
        syncExistingInputs();
        renderRefs();
      }

      function readHistoryItem(button) {
        const card = button.closest(".single-history-card");
        const dataNode = card ? card.querySelector(".history-item-data") : null;
        if (!dataNode) {
          return null;
        }
        try {
          return JSON.parse(dataNode.textContent);
        } catch (error) {
          return null;
        }
      }

      async function confirmPaidGeneration() {
        const modal = document.querySelector("[data-paid-confirm-modal]");
        if (!modal) {
          return window.confirm("This will start a paid generation. Continue?");
        }

        const ok = modal.querySelector("[data-paid-confirm-ok]");
        const cancel = modal.querySelector("[data-paid-confirm-cancel]");
        if (!ok || !cancel) {
          return window.confirm("This will start a paid generation. Continue?");
        }
        const previousFocus = document.activeElement;

        modal.hidden = false;
        cancel.focus();
        return new Promise(function (resolve) {
          function focusableControls() {
            return Array.from(
              modal.querySelectorAll("button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])")
            ).filter(function (node) {
              return !node.disabled && !node.hidden;
            });
          }

          function cleanup(result) {
            modal.hidden = true;
            ok.removeEventListener("click", onOk);
            cancel.removeEventListener("click", onCancel);
            document.removeEventListener("keydown", onKeyDown);
            if (previousFocus && typeof previousFocus.focus === "function") {
              previousFocus.focus();
            }
            resolve(result);
          }

          function onOk() {
            cleanup(true);
          }

          function onCancel() {
            cleanup(false);
          }

          function onKeyDown(event) {
            if (modal.hidden) {
              return;
            }
            if (event.key === "Escape") {
              event.preventDefault();
              cleanup(false);
              return;
            }
            if (event.key !== "Tab") {
              return;
            }

            const controls = focusableControls();
            if (!controls.length) {
              return;
            }
            const first = controls[0];
            const last = controls[controls.length - 1];
            if (event.shiftKey && document.activeElement === first) {
              event.preventDefault();
              last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
              event.preventDefault();
              first.focus();
            }
          }

          ok.addEventListener("click", onOk);
          cancel.addEventListener("click", onCancel);
          document.addEventListener("keydown", onKeyDown);
        });
      }

      document.addEventListener("click", async function (event) {
        const editButton = event.target.closest(".history-edit-button");
        const regenerateButton = event.target.closest(".history-regenerate-button");

        if (editButton) {
          const item = readHistoryItem(editButton);
          if (item) {
            applyHistoryItem(item);
            window.seedanceActivateTab("single-generation");
            promptEditor.focus();
          }
          return;
        }

        if (regenerateButton) {
          const item = readHistoryItem(regenerateButton);
          if (!item) {
            return;
          }
          applyHistoryItem(item);
          window.seedanceActivateTab("single-generation");
          if (await confirmPaidGeneration()) {
            form.requestSubmit();
          }
        }
      });

      form.addEventListener("submit", async function (event) {
        const submitter = event.submitter;
        if (!submitter || !submitter.matches("[data-paid-single-submit]")) {
          return;
        }
        event.preventDefault();
        if (await confirmPaidGeneration()) {
          submitter.disabled = true;
          syncPromptSourceFromEditor(promptEditor, promptField);
          form.submit();
        }
      });

      renderRefs();
    });
