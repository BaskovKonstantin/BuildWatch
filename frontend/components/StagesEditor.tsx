"use client";

import { KeyboardEvent, useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/api";
import { Card, KIND_RU } from "@/lib/objectCard";
type EditorStage = {
  kind: string;
  name: string;
  date_from: string;
  date_to: string;
  status: string;
};

export function StagesEditor({
  card, onClose, onSaved,
}: { card: Card; onClose: () => void; onSaved: () => void }) {
  const [rows, setRows] = useState<EditorStage[]>(
    card.stages.map(({ kind, name, date_from, date_to, status }) => ({
      kind, name, date_from, date_to, status,
    })),
  );
  const [saving, setSaving] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importNote, setImportNote] = useState("");
  const [importIssues, setImportIssues] = useState<string[]>([]);
  const [editorError, setEditorError] = useState("");
  const dialog = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const previousFocus = document.activeElement as HTMLElement | null;
    dialog.current?.querySelector<HTMLButtonElement>("button")?.focus();
    return () => previousFocus?.focus();
  }, []);

  function dialogKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") { onClose(); return; }
    if (event.key !== "Tab" || !dialog.current) return;
    const focusable = Array.from(dialog.current.querySelectorAll<HTMLElement>(
      "button:not([disabled]), input:not([disabled]), select:not([disabled])",
    ));
    if (!focusable.length) return;
    if (event.shiftKey && document.activeElement === focusable[0]) {
      event.preventDefault(); focusable[focusable.length - 1].focus();
    } else if (!event.shiftKey && document.activeElement === focusable[focusable.length - 1]) {
      event.preventDefault(); focusable[0].focus();
    }
  }

  async function importPlan(file: File) {
    if (file.size > 2 * 1024 * 1024) {
      setEditorError("Файл должен быть не больше 2 МБ");
      return;
    }
    setImporting(true);
    setEditorError("");
    setImportNote("");
    setImportIssues([]);
    try {
      const body = new FormData();
      body.set("file", file);
      const response = await apiFetch(`/api/objects/${card.object.id}/plan/preview`, { method: "POST", body });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Не удалось прочитать план");
      const today = new Date().toISOString().slice(0, 10);
      setRows((data.stages as EditorStage[]).map((stage) => ({
        ...stage, status: stage.date_to < today ? "done" : stage.date_from <= today ? "current" : "future",
      })));
      setImportNote(`Загружено ${data.stages.length} этапов. Проверьте типы работ и даты перед сохранением.`);
      setImportIssues(data.issues ?? []);
    } catch (cause) {
      setEditorError(cause instanceof Error ? cause.message : "Не удалось прочитать план");
    } finally {
      setImporting(false);
    }
  }

  async function save() {
    setSaving(true);
    setEditorError("");
    try {
      const response = await apiFetch(`/api/objects/${card.object.id}/stages`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(rows),
      });
      if (!response.ok) throw new Error((await response.json()).detail || "Не удалось сохранить план");
      onSaved();
    } catch (cause) {
      setEditorError(cause instanceof Error ? cause.message : "Не удалось сохранить план");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-back" onClick={onClose}>
      <div className="modal" ref={dialog} role="dialog" aria-modal="true" aria-labelledby="plan-editor-title"
        onKeyDown={dialogKeyDown} onClick={(e) => e.stopPropagation()}>
        <div className="pane-h" style={{ padding: "0 0 12px" }}>
          <span id="plan-editor-title">Редактор этапов · план объекта</span>
          <button className="mini" onClick={onClose}>Закрыть</button>
        </div>
        <div className="hint" style={{ padding: "0 0 10px" }}>
          Виды работ выбираются из справочника ЛТЦ; плановые даты задаёт
          инспектор. После сохранения предупреждения пересчитываются.
        </div>
        <div className="plan-import">
          <div><strong>Импорт календарного плана</strong><p>CSV или XLSX со столбцами «Этап», «Дата начала», «Дата окончания». Сначала откроется предпросмотр.</p></div>
          <label className="mini pri plan-import-picker" style={{ cursor: importing ? "wait" : "pointer" }}>
            {importing ? "Чтение…" : "Выбрать файл"}
            <input type="file" accept=".csv,.xlsx" disabled={importing} aria-label="Выбрать календарный план CSV или XLSX"
              onChange={(event) => { const file = event.target.files?.[0]; if (file) void importPlan(file); event.target.value = ""; }} />
          </label>
        </div>
        {importNote && <p className="plan-import-ok" role="status">{importNote}</p>}
        {importIssues.length > 0 && <div className="plan-import-issues"><strong>Пропущено строк: {importIssues.length}</strong>{importIssues.slice(0, 3).map((issue) => <p key={issue}>{issue}</p>)}</div>}
        {editorError && <p className="plan-import-error" role="alert">{editorError}</p>}
        {rows.map((st, i) => (
          <div className="stage-row" key={i}>
            <input
              aria-label={`Название этапа ${i + 1}`}
              value={st.name}
              onChange={(e) => setRows(rows.map((r, j) => j === i ? { ...r, name: e.target.value } : r))}
            />
            <select
              aria-label={`Вид работ этапа ${i + 1}`}
              value={st.kind}
              onChange={(e) => setRows(rows.map((r, j) => j === i ? { ...r, kind: e.target.value } : r))}
            >
              {card.stage_kinds.map((k) => (
                <option key={k} value={k}>{KIND_RU[k] ?? k}</option>
              ))}
            </select>
            <input
              type="date"
              aria-label={`Дата начала этапа ${i + 1}`}
              value={st.date_from}
              onChange={(e) => setRows(rows.map((r, j) => j === i ? { ...r, date_from: e.target.value } : r))}
            />
            <input
              type="date"
              aria-label={`Дата окончания этапа ${i + 1}`}
              value={st.date_to}
              onChange={(e) => setRows(rows.map((r, j) => j === i ? { ...r, date_to: e.target.value } : r))}
            />
            <select
              aria-label={`Статус этапа ${i + 1}`}
              value={st.status}
              onChange={(e) => setRows(rows.map((r, j) => j === i ? { ...r, status: e.target.value } : r))}
            >
              <option value="done">завершён</option>
              <option value="current">текущий</option>
              <option value="future">ожидается</option>
            </select>
            <button
              className="mini"
              aria-label={`Удалить этап ${i + 1}`}
              onClick={() => setRows(rows.filter((_, j) => j !== i))}
            >
              ✕
            </button>
          </div>
        ))}
        <div className="warn-act">
          <button
            className="mini"
            onClick={() => setRows([...rows, {
              kind: "other", name: "Новый этап", date_from: card.snapshots[0]?.captured_at ?? "2026-07-01",
              date_to: "2026-12-31", status: "future",
            }])}
          >
            + Этап
          </button>
          <span style={{ flex: 1 }} />
          <button className="mini pri" disabled={saving} onClick={save}>
            {saving ? "Сохранение…" : "Сохранить план"}
          </button>
        </div>
      </div>
    </div>
  );
}
