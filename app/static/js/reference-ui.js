// Shared prompt reference UI helpers.
export const DEFAULT_REFERENCE_FILE_LIMIT = 9;

function padTimestampPart(value) {
  return String(value).padStart(2, "0");
}

function clipboardTimestamp(date) {
  return [
    date.getFullYear(),
    padTimestampPart(date.getMonth() + 1),
    padTimestampPart(date.getDate())
  ].join("") + "-" + [
    padTimestampPart(date.getHours()),
    padTimestampPart(date.getMinutes()),
    padTimestampPart(date.getSeconds())
  ].join("");
}

function clipboardExtension(file) {
  const type = String(file && file.type || "").toLowerCase();
  const extensions = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "video/mp4": "mp4",
    "video/webm": "webm",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/ogg": "ogg"
  };
  return extensions[type] || "bin";
}

function normalizeClipboardFile(file, index, timestamp) {
  const originalName = String(file && file.name || "").trim();
  const genericName = !originalName || /^(image|clipboard|blob)(\.[a-z0-9]+)?$/i.test(originalName);
  if (!genericName || typeof File !== "function") {
    return file;
  }

  const suffix = index > 0 ? "-" + (index + 1) : "";
  const filename = "screenshot-" + timestamp + suffix + "." + clipboardExtension(file);
  return new File([file], filename, {
    type: file.type,
    lastModified: file.lastModified || Date.now()
  });
}

export function referenceFilesFromClipboard(event) {
  const clipboard = event && event.clipboardData;
  if (!clipboard) {
    return [];
  }

  const itemFiles = Array.from(clipboard.items || [])
    .filter(function (item) {
      return item.kind === "file";
    })
    .map(function (item) {
      return item.getAsFile();
    })
    .filter(Boolean);
  const files = itemFiles.length ? itemFiles : Array.from(clipboard.files || []);
  const timestamp = clipboardTimestamp(new Date());
  return files.map(function (file, index) {
    return normalizeClipboardFile(file, index, timestamp);
  });
}

export function referenceLimitForForm(form) {
  const capabilities = (window.seedanceConfig && window.seedanceConfig.modelCapabilities) || {};
  const modelValue = form && form.elements && form.elements.model
    ? form.elements.model.value
    : "seedance-2.0";
  const config = capabilities[modelValue] || capabilities["seedance-2.0"] || {};
  const limit = Number.parseInt(config.reference_file_limit, 10);
  return Number.isFinite(limit) && limit > 0 ? limit : DEFAULT_REFERENCE_FILE_LIMIT;
}

function filenameFor(ref) {
  return ref && (ref.filename || ref.original_filename || "reference");
}

export function createReferencePreviewNode(ref) {
  if (ref && ref.media_type === "image" && ref.preview_url) {
    const image = document.createElement("img");
    image.src = ref.preview_url;
    image.alt = "";
    return image;
  }

  const badge = document.createElement("span");
  badge.className = "media-badge";
  badge.textContent = (ref && ref.media_type) || "file";
  return badge;
}

function refByFilename(refs, filename) {
  return (refs || []).find(function (ref) {
    return filenameFor(ref) === filename;
  });
}

function tokenPattern() {
  return /<@([^>]+)>/g;
}

function createInlineReferenceNode(ref, filename) {
  const chip = document.createElement("span");
  chip.className = "prompt-inline-ref";
  chip.contentEditable = "false";
  chip.dataset.referenceFilename = filename;
  chip.title = filename;
  chip.appendChild(createReferencePreviewNode(ref || { filename: filename, media_type: "file" }));

  const label = document.createElement("span");
  label.className = "prompt-inline-ref-label";
  label.textContent = filename;
  chip.appendChild(label);
  return chip;
}

export function renderPromptEditorFromSource(editor, sourceField, refs) {
  if (!editor || !sourceField) {
    return;
  }

  const value = sourceField.value || "";
  const pattern = tokenPattern();
  let index = 0;
  let match = pattern.exec(value);
  editor.dataset.rendering = "true";
  editor.innerHTML = "";

  while (match) {
    if (match.index > index) {
      editor.appendChild(document.createTextNode(value.slice(index, match.index)));
    }

    const filename = match[1];
    const ref = refByFilename(refs, filename);
    if (ref) {
      editor.appendChild(createInlineReferenceNode(ref, filename));
    } else {
      editor.appendChild(document.createTextNode(match[0]));
    }
    index = match.index + match[0].length;
    match = pattern.exec(value);
  }

  if (index < value.length) {
    editor.appendChild(document.createTextNode(value.slice(index)));
  }

  delete editor.dataset.rendering;
}

function serializeNode(node) {
  if (node.nodeType === Node.TEXT_NODE) {
    return node.nodeValue || "";
  }

  if (node.nodeType !== Node.ELEMENT_NODE) {
    return "";
  }

  if (node.classList && node.classList.contains("prompt-inline-ref")) {
    return "<@" + (node.dataset.referenceFilename || "") + ">";
  }

  if (node.nodeName === "BR") {
    return "\n";
  }

  let value = "";
  for (const child of Array.from(node.childNodes)) {
    value += serializeNode(child);
  }

  if (["DIV", "P"].includes(node.nodeName) && value && !value.endsWith("\n")) {
    value += "\n";
  }
  return value;
}

export function syncPromptSourceFromEditor(editor, sourceField) {
  if (!editor || !sourceField || editor.dataset.rendering === "true") {
    return;
  }

  sourceField.value = Array.from(editor.childNodes)
    .map(serializeNode)
    .join("")
    .replace(/\n+$/g, "");
}

function rangeInsideEditor(editor) {
  const selection = window.getSelection();
  if (!selection || !selection.rangeCount) {
    return null;
  }
  const range = selection.getRangeAt(0);
  return editor.contains(range.commonAncestorContainer) ? range : null;
}

function focusEditorEnd(editor) {
  editor.focus();
  const range = document.createRange();
  range.selectNodeContents(editor);
  range.collapse(false);
  const selection = window.getSelection();
  selection.removeAllRanges();
  selection.addRange(range);
  return range;
}

function deletePreviousAtSign(range) {
  if (range.startContainer.nodeType === Node.TEXT_NODE && range.startOffset > 0) {
    const text = range.startContainer;
    if (text.nodeValue.slice(range.startOffset - 1, range.startOffset) !== "@") {
      return range;
    }

    text.deleteData(range.startOffset - 1, 1);
    const nextRange = document.createRange();
    nextRange.setStart(text, range.startOffset - 1);
    nextRange.collapse(true);
    return nextRange;
  }

  if (range.startContainer.nodeType === Node.ELEMENT_NODE && range.startOffset > 0) {
    const previous = range.startContainer.childNodes[range.startOffset - 1];
    if (previous && previous.nodeType === Node.TEXT_NODE && previous.nodeValue.endsWith("@")) {
      previous.deleteData(previous.nodeValue.length - 1, 1);
      const nextRange = document.createRange();
      nextRange.setStart(previous, previous.nodeValue.length);
      nextRange.collapse(true);
      return nextRange;
    }
  }

  return range;
}

function setCaretAfter(node) {
  const range = document.createRange();
  range.setStartAfter(node);
  range.collapse(true);
  const selection = window.getSelection();
  selection.removeAllRanges();
  selection.addRange(range);
}

export function insertReferenceToken(editor, sourceField, filename, refs) {
  if (!editor || !sourceField || !filename) {
    return;
  }

  let range = rangeInsideEditor(editor) || focusEditorEnd(editor);
  range = deletePreviousAtSign(range);
  range.deleteContents();

  const ref = refByFilename(refs, filename);
  const chip = createInlineReferenceNode(ref, filename);
  const after = document.createTextNode(" ");
  range.insertNode(after);
  range.insertNode(chip);
  setCaretAfter(after);
  syncPromptSourceFromEditor(editor, sourceField);
}

function textBeforeCaret(editor) {
  const range = rangeInsideEditor(editor);
  if (!range) {
    return "";
  }
  const before = range.cloneRange();
  before.selectNodeContents(editor);
  before.setEnd(range.endContainer, range.endOffset);
  return before.toString();
}

export function shouldShowReferenceTokenMenu(editor) {
  return textBeforeCaret(editor).endsWith("@");
}

export function renderReferenceTokenMenu(tokenMenu, refs, editor, dropzone, onSelect) {
  if (!tokenMenu) {
    return;
  }

  tokenMenu.innerHTML = "";
  if (!refs || !refs.length) {
    tokenMenu.hidden = true;
    return;
  }

  for (const ref of refs) {
    const option = document.createElement("button");
    option.type = "button";
    option.className = "ref-token-option";
    option.appendChild(createReferencePreviewNode(ref));

    const title = document.createElement("span");
    title.className = "ref-token-option-title";
    title.textContent = filenameFor(ref);
    option.appendChild(title);

    option.addEventListener("click", function () {
      onSelect(filenameFor(ref));
    });
    tokenMenu.appendChild(option);
  }

  tokenMenu.hidden = false;
  positionReferenceTokenMenu(tokenMenu, editor, dropzone);
}

export function positionReferenceTokenMenu(tokenMenu, editor, dropzone) {
  if (!tokenMenu || !editor || !dropzone) {
    return;
  }

  const zoneRect = dropzone.getBoundingClientRect();
  const editorRect = editor.getBoundingClientRect();
  const range = rangeInsideEditor(editor);
  const rangeRect = range ? range.getBoundingClientRect() : null;
  const anchor = rangeRect && (rangeRect.width || rangeRect.height) ? rangeRect : editorRect;
  const menuWidth = tokenMenu.offsetWidth || 260;
  const menuHeight = tokenMenu.offsetHeight || 160;
  const padding = 8;
  const left = anchor.left - zoneRect.left;
  const top = anchor.bottom - zoneRect.top + 6;
  const maxLeft = Math.max(padding, zoneRect.width - menuWidth - padding);
  const maxTop = Math.max(padding, zoneRect.height - menuHeight - padding);

  tokenMenu.style.left = Math.min(Math.max(padding, left), maxLeft) + "px";
  tokenMenu.style.top = Math.min(Math.max(padding, top), maxTop) + "px";
}
