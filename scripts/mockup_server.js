// BuildWatch mockup server — serves mockups/ and receives annotation POSTs.
// A new annotation is saved to mockups/annotations.json and forwarded to the
// BB thread with `bb thread tell`, so the agent starts processing right away.
import { createServer } from "node:http";
import { readFile, writeFile, stat } from "node:fs/promises";
import { execFile } from "node:child_process";
import { join, extname, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(fileURLToPath(import.meta.url)); // .../BuildWatch/scripts
const MOCKUPS = join(ROOT, "..", "mockups");
const ANNOTATIONS = join(MOCKUPS, "annotations.json");
const PORT = 8420;
const THREAD_ID = process.env.BB_THREAD_ID || "thr_yibw7irsbs";
const PUBLIC_ORIGIN = "https://kobbas--8420.getbb.app";

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
};

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

function send(res, code, body, type = "application/json; charset=utf-8") {
  res.writeHead(code, { ...CORS, "Content-Type": type });
  res.end(body);
}

async function readAnnotations() {
  try {
    const raw = await readFile(ANNOTATIONS, "utf8");
    return JSON.parse(raw);
  } catch {
    return [];
  }
}

async function tellThread(text) {
  await new Promise((resolve, reject) => {
    execFile("bb", ["thread", "tell", THREAD_ID, text], (err) => {
      if (err) reject(err);
      else resolve();
    });
  });
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url, PUBLIC_ORIGIN);
  if (req.method === "OPTIONS") {
    res.writeHead(204, CORS);
    return res.end();
  }

  if (url.pathname === "/api/annotations") {
    if (req.method === "GET") {
      return send(res, 200, JSON.stringify(await readAnnotations()));
    }
    if (req.method === "POST") {
      let raw = "";
      req.on("data", (chunk) => (raw = (raw || "") + chunk));
      req.on("end", async () => {
        try {
          const item = JSON.parse(raw);
          if (!item || typeof item.comment !== "string" || !item.comment.trim()) {
            return send(res, 400, JSON.stringify({ ok: false, error: "comment required" }));
          }
          if (item.comment.length > 4000) item.comment = item.comment.slice(0, 4000);
          const annotation = {
            receivedAt: new Date().toISOString(),
            dry: url.searchParams.get("dry") === "1",
            file: String(item.file || "unknown"),
            no: Number(item.no) || null,
            target: String(item.target || ""),
            label: String(item.label || ""),
            comment: item.comment.trim(),
          };
          const all = await readAnnotations();
          all.push(annotation);
          await writeFile(ANNOTATIONS, JSON.stringify(all, null, 2));

          let delivered = true;
          if (url.searchParams.get("dry") !== "1") {
            const message =
              `Новый комментарий к макету ${annotation.file}` +
              (annotation.no ? ` №${annotation.no}` : "") +
              ` — элемент «${annotation.label}».\nКомментарий: ${annotation.comment}\n` +
              `Селектор: ${annotation.target}\n` +
              `Полный журнал: mockups/annotations.json. Обработай: разбери замечание и внеси правку в макет.`;
            try {
              await tellThread(message);
            } catch (cause) {
              console.error("bb thread tell failed:", cause.message);
              delivered = false;
            }
          }
          return send(res, 200, JSON.stringify({ ok: true, delivered }));
        } catch (cause) {
          return send(res, 500, JSON.stringify({ ok: false, error: cause.message }));
        }
      });
      return;
    }
    return send(res, 405, JSON.stringify({ ok: false, error: "method" }));
  }

  // Static files from mockups/ (path traversal-safe: resolve and confine).
  const rel = url.pathname === "/" ? "index.html" : decodeURIComponent(url.pathname).replace(/^\/+/, "");
  const abs = join(MOCKUPS, rel);
  if (!abs.startsWith(MOCKUPS)) return send(res, 403, "{}");
  try {
    const st = await stat(abs);
    if (!st.isFile()) throw new Error("not a file");
    const data = await readFile(abs);
    send(res, 200, data, MIME[extname(abs).toLowerCase()] || "application/octet-stream");
  } catch {
    send(res, 404, "Not found", "text/plain");
  }
});

server.listen(PORT, "0.0.0.0", () => console.log(`mockup server on :${PORT}`));
