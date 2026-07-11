from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAFE_OUTPUT_ROOT = PROJECT_ROOT / "tmp_test_output"
VISUAL_OUT = SAFE_OUTPUT_ROOT / "visual_qa_cdp"


CDP_JS = r"""
const { spawn } = require("child_process");
const fs = require("fs");
const http = require("http");
const path = require("path");
const crypto = require("crypto");

const targetUrl = process.env.SEEDANCE_GUI_URL;
const outDir = process.env.SEEDANCE_VISUAL_OUT_DIR;
const port = Number(process.env.SEEDANCE_CDP_PORT || 9333);
fs.mkdirSync(outDir, { recursive: true });

const browserCandidates = [
  process.env.SEEDANCE_BROWSER,
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"
].filter(Boolean);
const browserPath = browserCandidates.find((candidate) => fs.existsSync(candidate));
if (!browserPath) {
  throw new Error("No Edge/Chrome browser found. Set SEEDANCE_BROWSER to a Chromium-based browser path.");
}

const profileDir = path.join(outDir, "profile_" + crypto.randomBytes(4).toString("hex"));
fs.mkdirSync(profileDir, { recursive: true });
const browser = spawn(browserPath, [
  "--headless=new",
  "--disable-gpu",
  "--no-sandbox",
  "--no-first-run",
  "--disable-extensions",
  "--remote-debugging-port=" + port,
  "--user-data-dir=" + profileDir,
  "about:blank"
], { stdio: "ignore", windowsHide: true });

function requestJson(url, method = "GET") {
  return new Promise((resolve, reject) => {
    const req = http.request(url, { method }, (res) => {
      let data = "";
      res.on("data", (chunk) => data += chunk);
      res.on("end", () => {
        try {
          resolve(JSON.parse(data));
        } catch (error) {
          reject(new Error(data || error.message));
        }
      });
    });
    req.on("error", reject);
    req.end();
  });
}

async function waitForCdp() {
  for (let i = 0; i < 80; i += 1) {
    try {
      return await requestJson("http://127.0.0.1:" + port + "/json/version");
    } catch (error) {
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
  }
  throw new Error("CDP did not start");
}

function cdpSession(wsUrl) {
  const ws = new WebSocket(wsUrl);
  let nextId = 1;
  const pending = new Map();
  const events = [];

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.method === "Runtime.exceptionThrown" || msg.method === "Log.entryAdded") {
      events.push(msg);
    }
    if (msg.id && pending.has(msg.id)) {
      const handlers = pending.get(msg.id);
      pending.delete(msg.id);
      if (msg.error) {
        handlers.reject(new Error(JSON.stringify(msg.error)));
      } else {
        handlers.resolve(msg.result || {});
      }
    }
  };

  return new Promise((resolve, reject) => {
    ws.onerror = reject;
    ws.onopen = () => resolve({
      events,
      send(method, params = {}) {
        const id = nextId++;
        ws.send(JSON.stringify({ id, method, params }));
        return new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
      },
      close() {
        ws.close();
      }
    });
  });
}

async function run() {
  await waitForCdp();
  const target = await requestJson("http://127.0.0.1:" + port + "/json/new?" + encodeURIComponent("about:blank"), "PUT");
  const cdp = await cdpSession(target.webSocketDebuggerUrl);
  await cdp.send("Runtime.enable");
  await cdp.send("Log.enable");
  await cdp.send("Page.enable");

  async function evalJs(expression) {
    const result = await cdp.send("Runtime.evaluate", {
      expression,
      awaitPromise: true,
      returnByValue: true
    });
    if (result.exceptionDetails) {
      throw new Error(JSON.stringify(result.exceptionDetails));
    }
    return result.result.value;
  }

  await cdp.send("Emulation.setDeviceMetricsOverride", {
    width: 1440,
    height: 900,
    deviceScaleFactor: 1,
    mobile: false
  });
  await cdp.send("Page.navigate", { url: targetUrl });

  let ready = "";
  for (let i = 0; i < 100; i += 1) {
    ready = await evalJs(`[
      document.readyState,
      typeof window.seedanceSetLanguage,
      typeof window.seedanceInitHistoryPagination,
      typeof window.seedanceActivateTab,
      typeof window.seedanceUpdateCostEstimate
    ].join(":")`);
    if (ready === "complete:function:function:function:function") {
      break;
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }

  const initial = await evalJs(`(() => ({
    ready: ${JSON.stringify(ready)},
    appJsReady: Boolean(window.seedanceSetLanguage && window.seedanceInitHistoryPagination && window.seedanceActivateTab && window.seedanceUpdateCostEstimate),
    moduleScripts: Array.from(document.querySelectorAll('script[type="module"]')).filter((node) => node.getAttribute("src")?.startsWith("/static/app.js")).length,
    overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    width: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
    progressbarCount: document.querySelectorAll('[role="progressbar"].history-generation-progress').length,
    progressValue: Number(document.querySelector('.history-generation-progress')?.getAttribute('aria-valuenow') || -1)
  }))()`);

  const tabs = await evalJs(`(() => {
    const result = {};
    for (const name of ["project-settings", "single-generation", "queue-workflow"]) {
      document.querySelector('[data-tab-target="' + name + '"]')?.click();
      result[name] = document.querySelector('[data-tab-panel="' + name + '"]')?.classList.contains("active") === true;
    }
    return result;
  })()`);

  const i18n = await evalJs(`(() => {
    document.querySelector('[data-tab-target="queue-workflow"]')?.click();
    window.seedanceSetLanguage("ru");
    const ru = {
      lang: document.documentElement.lang,
      placeholder: document.querySelector('.queue-generation-form [data-queue-prompt-rich-editor]')?.dataset.placeholder,
      queueTitle: document.querySelector('.queue-history-rail h2')?.textContent.trim(),
      subtitle: document.querySelector('[data-i18n="app_subtitle"]')?.textContent.trim(),
      creator: document.querySelector('.creator-attribution')?.textContent.trim(),
      addLabel: document.querySelector('.single-generation-form [data-trigger-reference-picker] [data-i18n="add_files_short"]')?.textContent.trim(),
      addButtonOverflow: (() => {
        const button = document.querySelector('.single-generation-form [data-trigger-reference-picker]');
        const label = button?.querySelector('[data-i18n="add_files_short"]');
        return Boolean(button && label && (label.scrollWidth > label.clientWidth + 1 || button.scrollWidth > button.clientWidth + 1));
      })()
    };
    window.seedanceSetLanguage("en");
    const en = {
      lang: document.documentElement.lang,
      placeholder: document.querySelector('.queue-generation-form [data-queue-prompt-rich-editor]')?.dataset.placeholder,
      queueTitle: document.querySelector('.queue-history-rail h2')?.textContent.trim(),
      subtitle: document.querySelector('[data-i18n="app_subtitle"]')?.textContent.trim(),
      creator: document.querySelector('.creator-attribution')?.textContent.trim()
    };
    return {
      ru,
      en,
      oldAnimePlaceholder: document.body.innerText.includes("anime video") || document.body.innerText.includes("Describe the anime"),
      oldQueueHint: document.body.innerText.includes("Queue history uses compact cards") || document.body.innerText.includes("История очереди использует")
    };
  })()`);

  const costEstimate = await evalJs(`(() => {
    document.querySelector('[data-tab-target="single-generation"]')?.click();
    const form = document.querySelector('.single-generation-form');
    form.elements.model.value = "seedance-2.0-fast";
    form.elements.model.dispatchEvent(new Event("change", { bubbles: true }));
    form.elements.duration.value = "4";
    form.elements.duration.dispatchEvent(new Event("change", { bubbles: true }));
    form.elements.resolution.value = "480p";
    form.elements.resolution.dispatchEvent(new Event("change", { bubbles: true }));
    form.elements.aspect_ratio.value = "16:9";
    form.elements.aspect_ratio.dispatchEvent(new Event("change", { bubbles: true }));
    const value = form.querySelector("[data-cost-estimate-value]")?.textContent.trim() || "";
    const note = form.querySelector("[data-cost-estimate-note]")?.textContent.trim() || "";
    form.elements.duration.value = "15";
    form.elements.duration.dispatchEvent(new Event("change", { bubbles: true }));
    form.elements.aspect_ratio.value = "21:9";
    form.elements.aspect_ratio.dispatchEvent(new Event("change", { bubbles: true }));
    const longValue = form.querySelector("[data-cost-estimate-value]")?.textContent.trim() || "";
    form.elements.aspect_ratio.value = "1:1";
    form.elements.aspect_ratio.dispatchEvent(new Event("change", { bubbles: true }));
    const squareValue = form.querySelector("[data-cost-estimate-value]")?.textContent.trim() || "";
    window.seedanceSetLanguage("ru");
    const squareValueAfterRu = form.querySelector("[data-cost-estimate-value]")?.textContent.trim() || "";
    window.seedanceSetLanguage("en");
    return {
      value,
      note,
      longValue,
      squareValue,
      squareValueAfterRu,
      hasUsd: value.includes("$"),
      expectedFastEstimate: value === "~$0.2248",
      expectedFastLongEstimate: longValue === "~$0.8430",
      expectedFastSquareEstimate: squareValue === "~$0.8070" && squareValueAfterRu === "~$0.8070"
    };
  })()`);

  const textToAudioRemoved = await evalJs(`(() => ({
    noTab: !document.querySelector('[data-tab-target="text-to-audio"]'),
    noPanel: !document.querySelector('[data-tab-panel="text-to-audio"]'),
    noForm: !document.querySelector(".text-to-audio-form"),
    noRouteForm: !document.querySelector('form[action="/text-to-audio"]')
  }))()`);

  const refresh = await evalJs(`(async () => {
    document.querySelector('[data-tab-target="single-generation"]')?.click();
    const prompt = document.querySelector('.single-generation-form textarea[name="prompt"]');
    const editor = document.querySelector('.single-generation-form [data-prompt-rich-editor]');
    prompt.value = "BROWSER_CDP_REFRESH_GUARD_KEEP";
    prompt.dispatchEvent(new Event("input", { bubbles: true }));
    document.querySelector('[data-refresh-history="single"]')?.click();
    await new Promise((resolve) => setTimeout(resolve, 1200));
    const stableVideo = document.querySelector('[data-history-rail-content="single"] video');
    editor.focus();
    const caretRange = document.createRange();
    caretRange.selectNodeContents(editor);
    caretRange.collapse(false);
    const caretSelection = window.getSelection();
    caretSelection.removeAllRanges();
    caretSelection.addRange(caretRange);
    const expectedCaretOffset = caretSelection.anchorOffset;
    let automaticRefreshSeen = false;
    document.addEventListener("seedance:history-refreshed", function onRefresh(event) {
      if (event.detail?.historyKind === "single" && event.detail?.targeted === true) {
        automaticRefreshSeen = true;
      }
    }, { once: true });
    await new Promise((resolve) => setTimeout(resolve, 5200));
    return {
      active: document.querySelector('[data-tab-panel="single-generation"]')?.classList.contains("active") === true,
      prompt: prompt.value,
      editorText: editor?.innerText || "",
      automaticRefreshSeen,
      caretPreserved: window.getSelection()?.anchorOffset === expectedCaretOffset,
      completedVideoPreserved: !stableVideo || stableVideo === document.querySelector('[data-history-rail-content="single"] video')
    };
  })()`);

  const dragdrop = await evalJs(`(() => {
    function dropFile(zoneSelector, fileName, type) {
      const zone = document.querySelector(zoneSelector);
      const dt = new DataTransfer();
      dt.items.add(new File(["seedance-cdp"], fileName, { type }));
      zone.dispatchEvent(new DragEvent("drop", { bubbles: true, cancelable: true, dataTransfer: dt }));
    }
    document.querySelector('[data-tab-target="single-generation"]')?.click();
    dropFile("[data-single-dropzone]", "browser-single-ref.png", "image/png");
    const singlePrompt = document.querySelector('.single-generation-form textarea[name="prompt"]');
    const singleEditor = document.querySelector('.single-generation-form [data-prompt-rich-editor]');
    singleEditor.focus();
    singleEditor.textContent = "@";
    const range = document.createRange();
    range.selectNodeContents(singleEditor);
    range.collapse(false);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    singleEditor.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: "@" }));
    const singleMenu = document.querySelector("[data-ref-token-menu]");
    const singleZone = document.querySelector("[data-single-dropzone]");
    const menuRect = singleMenu.getBoundingClientRect();
    const zoneRect = singleZone.getBoundingClientRect();
    const tokenOptionText = singleMenu.querySelector(".ref-token-option-title")?.textContent || "";
    const tokenMenuInsidePrompt = !singleMenu.hidden &&
      menuRect.left >= zoneRect.left &&
      menuRect.right <= zoneRect.right + 1 &&
      menuRect.top >= zoneRect.top &&
      menuRect.bottom <= zoneRect.bottom + 1;
    singleMenu.querySelector(".ref-token-option")?.click();
    document.querySelector('[data-tab-target="queue-workflow"]')?.click();
    dropFile("[data-queue-prompt-dropzone]", "browser-queue-audio.mp3", "audio/mpeg");
    document.querySelector('[data-tab-target="single-generation"]')?.click();
    return {
      singleCards: document.querySelectorAll('.single-generation-form .ref-card').length,
      queueCards: document.querySelectorAll('.queue-generation-form .ref-card').length,
      queueText: document.querySelector('[data-queue-attached-refs]')?.innerText || "",
      queueTitle: document.querySelector('[data-queue-attached-refs] .ref-card')?.title || "",
      singleInsidePrompt: Boolean(document.querySelector('[data-single-dropzone] [data-attached-refs] .ref-card')),
      queueInsidePrompt: Boolean(document.querySelector('[data-queue-prompt-dropzone] [data-queue-attached-refs] .ref-card')),
      singleCounter: document.querySelector("[data-reference-count]")?.textContent || "",
      singleCardText: document.querySelector('[data-single-dropzone] [data-attached-refs] .ref-card')?.innerText || "",
      tokenMenuInsidePrompt,
      tokenOptionText,
      singlePromptText: singlePrompt.value,
      inlineRefText: document.querySelector(".single-generation-form .prompt-inline-ref")?.innerText || "",
      bottomTokenPreviewExists: Boolean(document.querySelector("[data-prompt-reference-tokens]"))
    };
  })()`);

  await cdp.send("Page.captureScreenshot", { format: "png" }).then((shot) => {
    fs.writeFileSync(path.join(outDir, "prompt_refs.png"), Buffer.from(shot.data, "base64"));
  });

  const clipboardPaste = await evalJs(`(() => {
    document.querySelector('[data-tab-target="single-generation"]')?.click();
    const editor = document.querySelector('.single-generation-form [data-prompt-rich-editor]');
    const source = document.querySelector('.single-generation-form textarea[name="prompt"]');
    const before = document.querySelectorAll('.single-generation-form .ref-card').length;
    const clipboard = new DataTransfer();
    clipboard.items.add(new File(["clipboard-image"], "image.png", { type: "image/png" }));
    const event = new Event("paste", { bubbles: true, cancelable: true });
    Object.defineProperty(event, "clipboardData", { value: clipboard });
    const dispatchResult = editor.dispatchEvent(event);
    const cards = Array.from(document.querySelectorAll('.single-generation-form .ref-card'));
    const pastedCard = cards[cards.length - 1];
    const textClipboard = new DataTransfer();
    textClipboard.setData("text/plain", "plain text remains text");
    const textEvent = new Event("paste", { bubbles: true, cancelable: true });
    Object.defineProperty(textEvent, "clipboardData", { value: textClipboard });
    editor.dispatchEvent(textEvent);
    document.querySelector('[data-tab-target="queue-workflow"]')?.click();
    const queueEditor = document.querySelector('.queue-generation-form [data-queue-prompt-rich-editor]');
    const queueBefore = document.querySelectorAll('.queue-generation-form .ref-card').length;
    const queueClipboard = new DataTransfer();
    queueClipboard.items.add(new File(["queue-clipboard-image"], "image.png", { type: "image/png" }));
    const queueEvent = new Event("paste", { bubbles: true, cancelable: true });
    Object.defineProperty(queueEvent, "clipboardData", { value: queueClipboard });
    queueEditor.dispatchEvent(queueEvent);
    const queueCards = Array.from(document.querySelectorAll('.queue-generation-form .ref-card'));
    document.querySelector('[data-tab-target="single-generation"]')?.click();
    return {
      before,
      after: cards.length,
      prevented: dispatchResult === false || event.defaultPrevented,
      filename: pastedCard?.title || "",
      noEmbeddedImage: Array.from(editor.querySelectorAll("img")).every((image) => Boolean(image.closest(".prompt-inline-ref"))),
      promptUnchanged: source.value.includes("<@browser-single-ref.png>"),
      plainTextAllowed: !textEvent.defaultPrevented,
      queueAdded: queueCards.length === queueBefore + 1,
      queueFilename: queueCards[queueCards.length - 1]?.title || "",
      queueNoEmbeddedImage: Array.from(queueEditor.querySelectorAll("img")).every((image) => Boolean(image.closest(".prompt-inline-ref")))
    };
  })()`);

  const referenceLimit = await evalJs(`(() => {
    function dropFile(zoneSelector, fileName, type) {
      const zone = document.querySelector(zoneSelector);
      const dt = new DataTransfer();
      dt.items.add(new File(["seedance-cdp"], fileName, { type }));
      zone.dispatchEvent(new DragEvent("drop", { bubbles: true, cancelable: true, dataTransfer: dt }));
    }
    document.querySelector('[data-tab-target="single-generation"]')?.click();
    const expectedLimit = window.seedanceConfig.modelCapabilities["seedance-2.0-fast"].reference_file_limit;
    for (let index = 0; index < 12; index += 1) {
      dropFile("[data-single-dropzone]", "limit-ref-" + index + ".png", "image/png");
    }
    return {
      expectedLimit,
      cards: document.querySelectorAll('.single-generation-form .ref-card').length,
      counter: document.querySelector("[data-reference-count]")?.textContent || "",
      addDisabled: document.querySelector("[data-trigger-reference-picker]")?.disabled === true
    };
  })()`);

  const failedActions = await evalJs(`(() => {
    window.seedanceSetLanguage("en");
    window.seedanceActivateTab("queue-workflow");
    const queueCard = document.querySelector('.queue-history-card .status-failed')?.closest('[data-history-item]');
    const queueDetails = queueCard?.querySelector('.history-details');
    if (queueDetails) queueDetails.open = true;
    const queueDebug = queueCard?.querySelector('.queue-debug');
    const queueError = queueCard?.querySelector('.queue-error')?.textContent.trim() || "";
    const queue = {
      retry: Boolean(queueCard?.querySelector('[data-i18n="add_to_queue_again"]')),
      remove: Boolean(queueCard?.querySelector('[data-i18n="delete_error_record"]')),
      friendly: queueError.includes("before Takeflow received confirmation"),
      rawOnlyInDebug: Boolean(queueDebug && queueDebug.textContent.includes("UNEXPECTED_EOF_WHILE_READING")),
      noDisabledOpen: !queueCard?.querySelector('button[disabled][data-i18n="open_video"]')
    };
    window.seedanceActivateTab("single-generation");
    const singleCard = document.querySelector('.single-history-card:not(.queue-history-card) .status-failed')?.closest('[data-history-item]');
    const single = {
      retry: Boolean(singleCard?.querySelector('[data-i18n="send_again"]')),
      remove: Boolean(singleCard?.querySelector('[data-i18n="delete_error_record"]')),
      noDisabledOpen: !singleCard?.querySelector('button[disabled][data-i18n="open_video"]')
    };
    window.seedanceActivateTab("queue-workflow");
    return { queue, single };
  })()`);

  await cdp.send("Page.captureScreenshot", { format: "png" }).then((shot) => {
    fs.writeFileSync(path.join(outDir, "failed-actions.png"), Buffer.from(shot.data, "base64"));
  });

  const history = await evalJs(`(() => {
    function inject(kind) {
      const content = document.querySelector('[data-history-rail-content="' + kind + '"]');
      content.innerHTML = '<div class="single-history-grid history-rail-grid" data-history-list="' + kind + '"></div>' +
        '<nav class="history-pagination" data-history-pagination="' + kind + '" aria-label="' + kind + ' history pages" hidden>' +
        '<button type="button" class="secondary-button" data-history-page-prev>Back</button>' +
        '<span class="history-page-indicator" data-history-page-indicator>1 / 1</span>' +
        '<button type="button" class="secondary-button" data-history-page-next>Next</button>' +
        '</nav>';
      const list = content.querySelector('[data-history-list="' + kind + '"]');
      for (let index = 1; index <= 5; index += 1) {
        const card = document.createElement("article");
        card.className = "single-history-card compact-history-card";
        card.dataset.historyItem = "";
        card.innerHTML = '<h3>' + kind + ' synthetic ' + index + '</h3><details class="history-details"><summary>Details</summary><div>Details ' + index + '</div></details>';
        list.appendChild(card);
      }
      window.seedanceHistoryPagerState[kind] = 1;
      window.seedanceInitHistoryPagination();
      const pager = content.querySelector('[data-history-pagination="' + kind + '"]');
      const before = Array.from(list.querySelectorAll("[data-history-item]")).filter((item) => !item.hidden).length;
      const details = list.querySelector("details");
      details.querySelector("summary").click();
      pager.querySelector("[data-history-page-next]").click();
      const indicator = pager.querySelector("[data-history-page-indicator]").textContent;
      return {
        pagerVisible: pager.hidden === false,
        before,
        detailsOpen: details.open,
        indicator
      };
    }
    return { single: inject("single"), queue: inject("queue") };
  })()`);

  const modal = await evalJs(`(() => {
    document.querySelector('[data-tab-target="single-generation"]')?.click();
    const host = document.createElement("article");
    host.className = "single-history-card";
    host.innerHTML = '<button type="button" class="paid-button history-regenerate-button">Regenerate</button>' +
      '<script type="application/json" class="history-item-data">' +
      JSON.stringify({ prompt: "CDP_MODAL_REGENERATE", model: "seedance-2.0-fast", duration: 4, resolution: "480p", aspect_ratio: "16:9", seed: -1, refs: [] }) +
      '<\\/script>';
    document.body.appendChild(host);
    host.querySelector(".history-regenerate-button").click();
    const modal = document.querySelector("[data-paid-confirm-modal]");
    const visible = modal && !modal.hidden;
    const focusText = document.activeElement?.textContent?.trim() || "";
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    const closedByEscape = modal.hidden === true;
    host.remove();
    return {
      visible,
      focusText,
      title: document.querySelector("#paid-confirm-title")?.textContent.trim(),
      closedByEscape
    };
  })()`);

  const queueControls = await evalJs(`(() => {
    window.seedanceActivateTab("queue-workflow");
    window.seedanceSetLanguage("en");
    const mode = document.querySelector("[data-queue-run-mode]");
    const concurrency = document.querySelector("[data-queue-max-concurrency]");
    const sequentialDisabled = concurrency?.disabled === true;
    mode.value = "parallel";
    mode.dispatchEvent(new Event("change", { bubbles: true }));
    return {
      modeValue: mode?.value,
      sequentialDisabled,
      parallelEnabled: concurrency?.disabled === false,
      max: concurrency?.max,
      noOverflow: document.documentElement.scrollWidth <= document.documentElement.clientWidth,
      batchInsideControls: document.querySelector("[data-batch-import-panel]")?.parentElement === document.querySelector("[data-queue-controls-panel]"),
      noRunNext: !document.querySelector(".advanced-run")
    };
  })()`);

  const formDefaults = await evalJs(`(() => {
    const forms = Array.from(document.querySelectorAll(".generation-form"));
    return {
      randomSeedControls: forms.length > 0 && forms.every((form) => form.querySelector("[data-random-seed]")?.defaultChecked === true),
      audioControls: forms.length > 0 && forms.every((form) => form.elements.generate_audio?.defaultChecked === true),
      shortModelLabels: Array.from(document.querySelectorAll('select[name="model"] option')).every((option) => ["Seedance 2.0 Pro", "Seedance 2.0 Fast", "Seedance 2.0 Mini"].includes(option.textContent.trim())),
      noDefaultModelSetting: !document.querySelector('select[name="default_model"]')
    };
  })()`);

  await cdp.send("Page.captureScreenshot", { format: "png" }).then((shot) => {
    fs.writeFileSync(path.join(outDir, "queue-controls-desktop.png"), Buffer.from(shot.data, "base64"));
  });

  await cdp.send("Emulation.setDeviceMetricsOverride", {
    width: 390,
    height: 844,
    deviceScaleFactor: 1,
    mobile: true
  });
  await new Promise((resolve) => setTimeout(resolve, 500));
  const mobile = await evalJs(`(() => ({
    width: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
    overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    active: document.querySelector("[data-tab-panel].active")?.dataset.tabPanel
  }))()`);
  await cdp.send("Page.captureScreenshot", { format: "png" }).then((shot) => {
    fs.writeFileSync(path.join(outDir, "mobile.png"), Buffer.from(shot.data, "base64"));
  });

  const errors = cdp.events.filter((event) => {
    if (event.method === "Runtime.exceptionThrown") {
      return true;
    }
    const entry = event.params && event.params.entry;
    return entry && entry.level === "error" && !String(entry.url || "").endsWith("/favicon.ico");
  });

  const checks = {
    app_js_ready: initial.appJsReady && initial.moduleScripts === 1,
    desktop_no_overflow: !initial.overflow,
    processing_progress_visible: initial.progressbarCount >= 1 && initial.progressValue >= 0 && initial.progressValue < 100,
    tabs_work: Object.values(tabs).every(Boolean),
    ru_en_placeholders: i18n.ru.placeholder === "Опишите видео-сцену..." && i18n.en.placeholder === "Describe the video scene...",
    bilingual_brand_copy: i18n.ru.subtitle === "Локальная AI-video студия" && i18n.en.subtitle === "Local AI-video studio" && i18n.ru.creator.includes("Игорь Олегович Крамер") && i18n.en.creator.includes("Igor Olegovich Kramer"),
    no_old_copy: !i18n.oldAnimePlaceholder && !i18n.oldQueueHint,
    ru_add_tile_fits: i18n.ru.addLabel === "Файл" && !i18n.ru.addButtonOverflow,
    cost_estimate_live: costEstimate.expectedFastEstimate && costEstimate.expectedFastLongEstimate && costEstimate.expectedFastSquareEstimate && costEstimate.note.length > 0,
    text_to_audio_removed: textToAudioRemoved.noTab && textToAudioRemoved.noPanel && textToAudioRemoved.noForm && textToAudioRemoved.noRouteForm,
    refresh_preserves_prompt: refresh.prompt === "BROWSER_CDP_REFRESH_GUARD_KEEP" && refresh.editorText.includes("BROWSER_CDP_REFRESH_GUARD_KEEP") && refresh.active && refresh.automaticRefreshSeen && refresh.caretPreserved,
    targeted_refresh_preserves_video: refresh.completedVideoPreserved,
    dragdrop_refs: dragdrop.singleCards >= 1 && dragdrop.queueCards >= 1 && dragdrop.queueTitle.includes("browser-queue-audio.mp3"),
    references_inside_prompt: dragdrop.singleInsidePrompt && dragdrop.queueInsidePrompt,
    reference_cards_are_visual_only: !dragdrop.singleCardText.includes("browser-single-ref.png"),
    reference_count_visible: dragdrop.singleCounter === "1/9",
    clipboard_image_becomes_reference: clipboardPaste.after === clipboardPaste.before + 1 && clipboardPaste.prevented && clipboardPaste.filename.startsWith("screenshot-") && clipboardPaste.filename.endsWith(".png") && clipboardPaste.noEmbeddedImage && clipboardPaste.promptUnchanged && clipboardPaste.plainTextAllowed && clipboardPaste.queueAdded && clipboardPaste.queueFilename.startsWith("screenshot-") && clipboardPaste.queueNoEmbeddedImage,
    reference_limit_enforced: referenceLimit.cards === referenceLimit.expectedLimit && referenceLimit.counter === referenceLimit.expectedLimit + "/" + referenceLimit.expectedLimit && referenceLimit.addDisabled,
    token_menu_inside_prompt: dragdrop.tokenMenuInsidePrompt && dragdrop.tokenOptionText.includes("browser-single-ref.png"),
    reference_tokens_highlighted: dragdrop.singlePromptText.includes("<@browser-single-ref.png>") && dragdrop.inlineRefText.includes("browser-single-ref.png") && !dragdrop.bottomTokenPreviewExists,
    pagination_and_details: history.single.pagerVisible && history.queue.pagerVisible && history.single.detailsOpen && history.queue.detailsOpen && history.single.indicator === "2 / 2" && history.queue.indicator === "2 / 2",
    paid_modal_safe: modal.visible && modal.closedByEscape && modal.title === "This will start a paid generation. Continue?",
    queue_modes_work: queueControls.modeValue === "parallel" && queueControls.sequentialDisabled && queueControls.parallelEnabled && queueControls.max === "10" && queueControls.noOverflow,
    queue_controls_polished: queueControls.batchInsideControls && queueControls.noRunNext,
    form_defaults_and_labels: formDefaults.randomSeedControls && formDefaults.audioControls && formDefaults.shortModelLabels && formDefaults.noDefaultModelSetting,
    failed_actions_and_errors: Object.values(failedActions.queue).every(Boolean) && Object.values(failedActions.single).every(Boolean),
    mobile_no_overflow: !mobile.overflow,
    no_console_errors: errors.length === 0
  };
  const ok = Object.values(checks).every(Boolean);
  const result = { checks, failedChecks: Object.entries(checks).filter(([, value]) => !value).map(([key]) => key), initial, tabs, i18n, costEstimate, textToAudioRemoved, refresh, dragdrop, clipboardPaste, referenceLimit, history, modal, queueControls, formDefaults, failedActions, mobile, errors, screenshots: outDir, new_paid_submit_started: false };
  fs.writeFileSync(path.join(outDir, "browser_check_result.json"), JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));
  cdp.close();
  browser.kill();
  if (!ok) {
    process.exit(1);
  }
}

run().catch((error) => {
  try {
    browser.kill();
  } catch (_) {
  }
  console.error(error.stack || error.message);
  process.exit(1);
});
"""


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_http(url: str, timeout_seconds: float = 12.0) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError) as error:
            last_error = error
        time.sleep(0.25)
    raise RuntimeError(f"GUI server did not become ready at {url}: {last_error}")


def find_node() -> str:
    candidates = [
        os.environ.get("NODE_EXE"),
        shutil.which("node"),
        str(Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node" / "bin" / "node.exe"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    raise RuntimeError("Node.js was not found. Set NODE_EXE to a Node executable.")


def main() -> int:
    print("=== Frontend browser CDP check ===")
    SAFE_OUTPUT_ROOT.mkdir(exist_ok=True)
    VISUAL_OUT.mkdir(parents=True, exist_ok=True)

    port = find_free_port()
    url = f"http://127.0.0.1:{port}/"
    env = os.environ.copy()
    env["PYTHON_DOTENV_DISABLED"] = "1"
    env["SEGMIND_API_KEY"] = ""
    env["OUTPUT_ROOT"] = str(SAFE_OUTPUT_ROOT)
    env["OUTPUT_DIR"] = str(SAFE_OUTPUT_ROOT / "MyFirstProject")
    env["TAKEFLOW_DATA_DIR"] = str(SAFE_OUTPUT_ROOT / f"browser_cdp_data_{port}")

    seed_script = """
from app.db import create_task, init_db, update_task_fields, utc_now
init_db()
task_id = create_task(
    model="seedance-2.0-mini",
    prompt="Browser-only progress check",
    params={
        "mode": "single_generation_paid",
        "single_generation_name": "Browser progress check",
        "project_name": "MyFirstProject",
        "project_dir": r"%s",
        "duration": 4,
        "resolution": "480p",
        "aspect_ratio": "16:9",
        "seed": -1,
    },
    refs=[],
    status="processing",
)
update_task_fields(task_id, started_at=utc_now())
queue_failed_id = create_task(
    model="seedance-2.0-mini",
    prompt="Browser-only failed queue check",
    params={
        "mode": "queued_no_generation_yet",
        "project_name": "MyFirstProject",
        "project_dir": r"%s",
        "duration": 4,
        "resolution": "480p",
        "aspect_ratio": "16:9",
        "seed": -1,
    },
    refs=[],
    status="failed",
)
update_task_fields(queue_failed_id, error="ConnectError: [SSL: UNEXPECTED_EOF_WHILE_READING] browser-only")
single_failed_id = create_task(
    model="seedance-2.0-mini",
    prompt="Browser-only failed single check",
    params={
        "mode": "single_generation_paid",
        "single_generation_name": "Failed single check",
        "project_name": "MyFirstProject",
        "project_dir": r"%s",
        "duration": 4,
        "resolution": "480p",
        "aspect_ratio": "16:9",
        "seed": -1,
    },
    refs=[],
    status="failed",
)
update_task_fields(single_failed_id, error="Synthetic single failure")
""" % (str(SAFE_OUTPUT_ROOT / "MyFirstProject"), str(SAFE_OUTPUT_ROOT / "MyFirstProject"), str(SAFE_OUTPUT_ROOT / "MyFirstProject"))
    seed_result = subprocess.run(
        [sys.executable, "-c", seed_script],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if seed_result.returncode != 0:
        print(seed_result.stdout, end="")
        print("RESULT=FRONTEND_BROWSER_CDP_FAILED")
        return 1

    out_log = SAFE_OUTPUT_ROOT / "browser_cdp_uvicorn.out.log"
    err_log = SAFE_OUTPUT_ROOT / "browser_cdp_uvicorn.err.log"
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=out_log.open("ab"),
        stderr=err_log.open("ab"),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

    try:
        wait_for_http(url)
        node_script = SAFE_OUTPUT_ROOT / "browser_cdp_runner.cjs"
        node_script.write_text(CDP_JS, encoding="utf-8")
        cdp_env = env.copy()
        cdp_env["SEEDANCE_GUI_URL"] = url
        cdp_env["SEEDANCE_VISUAL_OUT_DIR"] = str(VISUAL_OUT)
        cdp_env["SEEDANCE_CDP_PORT"] = str(find_free_port())
        result = subprocess.run(
            [find_node(), str(node_script)],
            cwd=PROJECT_ROOT,
            env=cdp_env,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        print(result.stdout, end="")
        print(f"browser_cdp_status={result.returncode}")
        if result.returncode != 0:
            print("RESULT=FRONTEND_BROWSER_CDP_FAILED")
            return 1
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)

    print("RESULT=FRONTEND_BROWSER_CDP_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
