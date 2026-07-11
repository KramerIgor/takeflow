import {
  createReferencePreviewNode,
  insertReferenceToken,
  referenceFilesFromClipboard,
  referenceLimitForForm,
  renderPromptEditorFromSource,
  renderReferenceTokenMenu,
  shouldShowReferenceTokenMenu,
  syncPromptSourceFromEditor
} from "./reference-ui.js?v=20260711-v014-frontend-cachefix-5";

// Queue references and edit-in-queue behavior
document.addEventListener("DOMContentLoaded", function () {
      const form = document.querySelector(".queue-generation-form");
      if (!form) {
        return;
      }

      const promptField = form.elements.prompt;
      const promptEditor = form.querySelector("[data-queue-prompt-rich-editor]");
      const fileInput = form.querySelector("[data-queue-reference-files]");
      const promptDropzone = form.querySelector("[data-queue-prompt-dropzone]");
      const fileDropzone = form.querySelector("[data-queue-dropzone]");
      const refsList = form.querySelector("[data-queue-attached-refs]");
      const tokenMenu = form.querySelector("[data-queue-ref-token-menu]");
      const pickerButton = form.querySelector("[data-trigger-queue-reference-picker]");
      const counterNode = form.querySelector("[data-queue-reference-count]");
      const existingInputs = form.querySelector("[data-queue-existing-reference-inputs]");
      const editTaskInput = form.querySelector("[data-edit-queue-task-id]");
      const addQueueButton = form.querySelector("[data-add-queue-button]");
      const draftQueueButton = form.querySelector("[data-draft-queue-button]");
      const updateQueueButton = form.querySelector("[data-update-queue-button]");
      const cancelEditButton = form.querySelector("[data-cancel-queue-edit]");
      const attachedFiles = [];
      const existingRefs = [];
      let visibleRefs = [];

      function mediaTypeForName(name) {
        const suffix = String(name || "").toLowerCase().split(".").pop();
        if (["png", "jpg", "jpeg", "webp"].includes(suffix)) return "image";
        if (["mp4", "mov", "webm", "mkv"].includes(suffix)) return "video";
        if (["mp3", "wav", "m4a", "aac", "ogg", "flac"].includes(suffix)) return "audio";
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
          if (!ref.local_path) continue;
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
        const existing = existingRefs.map(function (ref, index) {
          return {
            kind: "existing",
            index: index,
            filename: ref.filename || ref.original_filename || "reference",
            media_type: ref.media_type || mediaTypeForName(ref.filename || ref.local_path),
            preview_url: ref.preview_url || "",
            local_path: ref.local_path || ""
          };
        });
        const uploaded = attachedFiles.map(function (file, index) {
          return {
            kind: "file",
            index: index,
            filename: file.name,
            media_type: mediaTypeForName(file.name),
            preview_url: URL.createObjectURL(file)
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

      function hideTokenMenu() {
        tokenMenu.hidden = true;
        tokenMenu.innerHTML = "";
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
            if (ref.kind === "existing") {
              existingRefs.splice(ref.index, 1);
              syncExistingInputs();
            } else {
              attachedFiles.splice(ref.index, 1);
              syncFileInput();
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



      function setQueueEditMode(taskId) {
        editTaskInput.value = taskId || "";
        updateQueueButton.hidden = !taskId;
        cancelEditButton.hidden = !taskId;
        addQueueButton.hidden = Boolean(taskId);
        draftQueueButton.hidden = Boolean(taskId);
        if (taskId) {
          updateQueueButton.formAction = "/update-queued-task/" + encodeURIComponent(taskId);
        } else {
          updateQueueButton.formAction = "/add-to-queue";
        }
      }

      function clearQueueEditMode() {
        setQueueEditMode("");
        attachedFiles.splice(0, attachedFiles.length);
        existingRefs.splice(0, existingRefs.length);
        syncFileInput();
        syncExistingInputs();
        renderRefs();
      }

      function applyQueueItem(item) {
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
        if (window.seedanceApplySeedState) {
          window.seedanceApplySeedState(form, item);
        } else {
          form.elements.seed.value = item.seed ?? -1;
        }
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
        setQueueEditMode(item.queue_task_id || "");
      }

      function showTokenMenu() {
        const refs = visibleRefs.length ? visibleRefs : currentRefs();
        if (!refs.length) {
          hideTokenMenu();
          return;
        }
        renderReferenceTokenMenu(tokenMenu, refs, promptEditor, promptDropzone, insertToken);
      }

      function maybeShowTokenMenu() {
        if (shouldShowReferenceTokenMenu(promptEditor)) {
          showTokenMenu();
        } else {
          hideTokenMenu();
        }
      }

      function wireDropzone(zone) {
        if (!zone) return;
        for (const eventName of ["dragenter", "dragover"]) {
          zone.addEventListener(eventName, function (event) {
            event.preventDefault();
            zone.classList.add("drag-over");
          });
        }
        for (const eventName of ["dragleave", "drop"]) {
          zone.addEventListener(eventName, function () {
            zone.classList.remove("drag-over");
          });
        }
        zone.addEventListener("drop", function (event) {
          event.preventDefault();
          addFiles(event.dataTransfer.files);
        });
      }

      fileInput.addEventListener("change", function () {
        addFiles(fileInput.files);
      });
      if (pickerButton) {
        pickerButton.addEventListener("click", function () {
          fileInput.click();
        });
      }

      cancelEditButton.addEventListener("click", function () {
        clearQueueEditMode();
      });
      document.addEventListener("click", function (event) {
        const editButton = event.target.closest(".queue-edit-button");
        if (!editButton) return;
        const card = editButton.closest(".queue-history-card");
        const dataNode = card ? card.querySelector(".history-item-data") : null;
        if (!dataNode) return;
        try {
          const item = JSON.parse(dataNode.textContent);
          applyQueueItem(item);
          window.seedanceActivateTab("queue-workflow");
          promptEditor.focus();
        } catch (error) {
          return;
        }
      });
      promptEditor.addEventListener("input", function () {
        syncPromptSourceFromEditor(promptEditor, promptField);
        maybeShowTokenMenu();
      });
      promptEditor.addEventListener("paste", function (event) {
        const files = referenceFilesFromClipboard(event);
        if (!files.length) {
          return;
        }
        event.preventDefault();
        addFiles(files);
        hideTokenMenu();
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
      wireDropzone(promptDropzone);
      wireDropzone(fileDropzone);
      form.addEventListener("submit", function () {
        syncPromptSourceFromEditor(promptEditor, promptField);
      });
      renderRefs();
    });
