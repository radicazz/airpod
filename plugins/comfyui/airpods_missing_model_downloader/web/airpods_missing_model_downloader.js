import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const URL_RE = /(https?:\/\/[^\s"'<>]+)/gi;
const MODEL_PATH_RE = /models\/([A-Za-z0-9_.-]+)(?:\/([A-Za-z0-9_./-]+))?/i;
const FILENAME_RE =
  /([A-Za-z0-9_.-]+\.(?:safetensors|ckpt|pt|pth|bin|onnx|gguf))/i;

function textLower(el) {
  return (el?.textContent ?? "").trim().toLowerCase();
}

function findButtonByText(container, needle) {
  const want = needle.toLowerCase();
  const buttons = Array.from(container.querySelectorAll("button"));
  return buttons.find((b) => textLower(b) === want) || null;
}

function closestRow(el) {
  if (!el) return null;
  return (
    el.closest("tr") ||
    el.closest("li") ||
    el.closest(".row") ||
    el.closest(".item") ||
    el.closest("div")
  );
}

function extractUrl(row) {
  const a =
    row.querySelector('a[href^="https://huggingface.co"]') ||
    row.querySelector('a[href^="http://huggingface.co"]') ||
    row.querySelector('a[href^="https://"]') ||
    row.querySelector('a[href^="http://"]');
  if (a?.href) return a.href;
  const m = (row.textContent || "").match(URL_RE);
  return m?.[0] ?? "";
}

function extractDest(row) {
  const txt = row.textContent || "";
  const m = txt.match(MODEL_PATH_RE);
  if (!m) return { folderKey: "", subdir: "" };
  const folderKey = m[1] || "";
  const subpath = m[2] || "";
  // subpath may include the filename; we only want directory bits
  const filenameMatch = subpath.match(FILENAME_RE);
  if (filenameMatch) {
    const withoutFile = subpath.replace(filenameMatch[0], "");
    const trimmed = withoutFile.replace(/^\/+/, "").replace(/\/+$/, "");
    return { folderKey, subdir: trimmed };
  }
  return { folderKey, subdir: subpath.replace(/^\/+/, "").replace(/\/+$/, "") };
}

function extractFilename(row, url) {
  const txt = row.textContent || "";
  const m = txt.match(FILENAME_RE);
  if (m?.[1]) return m[1];
  try {
    const u = new URL(url);
    const base = u.pathname.split("/").pop() || "";
    return base;
  } catch {
    return "";
  }
}

async function pollJob(jobId, onUpdate, signal) {
  while (true) {
    if (signal?.aborted) throw new Error("aborted");
    const r = await api.fetchApi(`/airpods/models/download/${jobId}`);
    const j = await r.json();
    if (!j.ok) throw new Error(j.error || "status failed");
    onUpdate(j);
    if (j.status === "done") return j;
    if (j.status === "error") throw new Error(j.error || "download failed");
    await new Promise((res) => setTimeout(res, 1000));
  }
}

function formatProgress(bytesDone, bytesTotal) {
  if (!bytesTotal) return "";
  const pct = Math.max(0, Math.min(100, Math.floor((bytesDone / bytesTotal) * 100)));
  return `${pct}%`;
}

function injectThirdButton(row) {
  if (!row || row.dataset.airpodsDownloaderInjected === "1") return;
  const copyBtn = findButtonByText(row, "Copy link");
  const dlBtn = findButtonByText(row, "Download");
  if (!copyBtn || !dlBtn) return;

  const btn = dlBtn.cloneNode(true);
  btn.textContent = "Download to ComfyUI";
  btn.disabled = false;
  btn.style.marginLeft = "0.5rem";

  btn.addEventListener("click", async (ev) => {
    ev.preventDefault();
    ev.stopPropagation();

    const rowEl = closestRow(btn) || row;
    const url = extractUrl(rowEl);
    const { folderKey, subdir } = extractDest(rowEl);
    const filename = extractFilename(rowEl, url);

    if (!url) {
      btn.textContent = "No URL found";
      setTimeout(() => (btn.textContent = "Download to ComfyUI"), 2500);
      return;
    }
    if (!folderKey) {
      btn.textContent = "No folder found";
      setTimeout(() => (btn.textContent = "Download to ComfyUI"), 2500);
      return;
    }

    btn.disabled = true;
    const orig = btn.textContent;
    btn.textContent = "Starting…";

    const controller = new AbortController();
    try {
      const r = await api.fetchApi("/airpods/models/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url,
          folder_key: folderKey,
          subdir,
          filename,
          overwrite: false,
        }),
        signal: controller.signal,
      });
      const j = await r.json();
      if (!j.ok) throw new Error(j.error || "request failed");
      const jobId = j.job_id;
      btn.textContent = "Downloading…";

      await pollJob(
        jobId,
        (st) => {
          const pct = formatProgress(st.bytes_done, st.bytes_total);
          btn.textContent = pct ? `Downloading… ${pct}` : "Downloading…";
        },
        controller.signal,
      );

      btn.textContent = "Downloaded";
      btn.disabled = true;
    } catch (e) {
      console.error(e);
      btn.textContent = "Failed";
      btn.disabled = false;
      setTimeout(() => {
        btn.textContent = orig;
      }, 2500);
    }
  });

  dlBtn.parentElement?.appendChild(btn);
  row.dataset.airpodsDownloaderInjected = "1";
}

function scanAndInject() {
  const buttons = Array.from(document.querySelectorAll("button"));
  for (const b of buttons) {
    if (textLower(b) !== "copy link") continue;
    const row = closestRow(b);
    if (!row) continue;
    injectThirdButton(row);
  }
}

app.registerExtension({
  name: "airpods.missing_model_downloader",
  setup() {
    const observer = new MutationObserver(() => scanAndInject());
    observer.observe(document.body, { childList: true, subtree: true });
    scanAndInject();
  },
});
