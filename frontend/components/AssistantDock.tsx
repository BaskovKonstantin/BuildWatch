"use client";

import { usePathname } from "next/navigation";
import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/api";

type Evidence = { label: string; url: string };
type Proposal = {
  id: string; object_id: number; stage_name: string;
  old_from: string; old_to: string; new_from: string; new_to: string;
};
type Reply = { answer: string; evidence: Evidence[]; proposal: Proposal | null };
type Exchange = { question: string; reply: Reply; applied?: boolean };

const SUGGESTIONS = ["Какие объекты требуют проверки?", "Что известно по последнему снимку?"];

export function AssistantDock() {
  const pathname = usePathname();
  const objectId = /^\/objects\/(\d+)(?:\/|$)/.exec(pathname)?.[1];
  const [open, setOpen] = useState(false);
  const [available, setAvailable] = useState<boolean | null>(null);
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState<Exchange[]>([]);
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [error, setError] = useState("");
  const trigger = useRef<HTMLButtonElement>(null);
  const invoker = useRef<HTMLElement | null>(null);
  const panel = useRef<HTMLElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!open) return;
    input.current?.focus();
    apiFetch("/api/assistant/status")
      .then((res) => res.ok ? res.json() : { available: false })
      .then((data) => setAvailable(Boolean(data.available)))
      .catch(() => setAvailable(false));
  }, [open]);

  useEffect(() => {
    setHistory([]);
    setError("");
  }, [pathname]);


  function close() {
    setOpen(false);
    (invoker.current ?? trigger.current)?.focus();
    invoker.current = null;
  }

  function openAssistant() {
    const active = document.activeElement;
    invoker.current = active instanceof HTMLElement ? active : trigger.current;
    setOpen(true);
  }

  function panelKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (event.key === "Escape") { close(); return; }
    if (event.key !== "Tab" || !panel.current) return;
    const items = Array.from(panel.current.querySelectorAll<HTMLElement>(
      "a[href], button:not([disabled]), textarea:not([disabled])",
    ));
    if (!items.length) return;
    const first = items[0], last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  }

  async function ask(value: string) {
    const message = value.trim();
    if (!message || busy) return;
    setBusy(true);
    setError("");
    try {
      const response = await apiFetch("/api/assistant/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, object_id: objectId ? Number(objectId) : null }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Не удалось получить ответ");
      setHistory((current) => [...current, { question: message, reply: data as Reply }]);
      setQuestion("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Не удалось получить ответ");
    } finally {
      setBusy(false);
      input.current?.focus();
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void ask(question);
  }

  async function confirm(proposal: Proposal) {
    setConfirming(proposal.id);
    setError("");
    try {
      const response = await apiFetch(`/api/assistant/proposals/${proposal.id}/confirm`, { method: "POST" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Не удалось применить изменение");
      setHistory((current) => current.map((item) =>
        item.reply.proposal?.id === proposal.id ? { ...item, applied: true } : item,
      ));
      window.dispatchEvent(new CustomEvent("buildwatch:plan-updated", { detail: { objectId: proposal.object_id } }));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Не удалось применить изменение");
    } finally {
      setConfirming(null);
    }
  }

  return (
    <>
      <button ref={trigger} className="assistant-trigger" onClick={openAssistant} aria-label="Открыть ИИ-помощника">
        <span className="assistant-trigger-mark" aria-hidden="true">✳</span>
        <span>Спросить BuildWatch</span>
      </button>
      {open && (
        <div className="assistant-overlay" onMouseDown={(event) => { if (event.target === event.currentTarget) close(); }}>
          <section ref={panel} className="assistant-drawer" role="dialog" aria-modal="true" aria-labelledby="assistant-heading" onKeyDown={panelKeyDown}>
            <div className="assistant-head">
              <div>
                <span className="assistant-eyebrow">BUILDWATCH / АНАЛИТИКА</span>
                <h2 id="assistant-heading">Спросить по данным</h2>
                <p>{objectId ? "Контекст: текущий объект" : "Контекст: все объекты"}</p>
              </div>
              <button className="assistant-close" onClick={close} aria-label="Закрыть помощника">×</button>
            </div>
            <div className="assistant-feed" aria-live="polite">
              {history.length === 0 && (
                <div className="assistant-intro">
                  <div className="assistant-intro-mark" aria-hidden="true">✳</div>
                  <h3>Разберите проблему за минуту</h3>
                  <p>Помощник отвечает по плану, снимкам и предупреждениям. У каждого вывода есть ссылка на источник. Изменение плана сначала появится как черновик.</p>
                  <div className="assistant-suggestions">
                    {(objectId ? ["Почему объект требует проверки?", "Сдвинь текущий этап на неделю"] : SUGGESTIONS).map((tip) => (
                      <button key={tip} onClick={() => void ask(tip)} disabled={busy}>{tip}<span aria-hidden="true">↗</span></button>
                    ))}
                  </div>
                </div>
              )}
              {history.map((item, index) => (
                <div className="assistant-exchange" key={index}>
                  <div className="assistant-question">{item.question}</div>
                  <div className="assistant-answer">
                    <span className="assistant-answer-label">АНАЛИЗ ДАННЫХ</span>
                    <p>{item.reply.answer}</p>
                    {item.reply.evidence.length > 0 && (
                      <div className="assistant-evidence">
                        <strong>Источники</strong>
                        {item.reply.evidence.map((source) => (
                          <a href={source.url} key={source.url}>{source.label} <span aria-hidden="true">↗</span></a>
                        ))}
                      </div>
                    )}
                    {item.reply.proposal && (
                      <div className="assistant-proposal">
                        <strong>Черновик изменения · {item.reply.proposal.stage_name}</strong>
                        <div><span>Сейчас</span><b>{item.reply.proposal.old_from} — {item.reply.proposal.old_to}</b></div>
                        <div><span>После</span><b>{item.reply.proposal.new_from} — {item.reply.proposal.new_to}</b></div>
                        {item.applied ? <p className="assistant-applied">План обновлён, предупреждения пересчитаны.</p> : (
                          <button className="assistant-confirm" disabled={confirming === item.reply.proposal.id}
                            onClick={() => void confirm(item.reply.proposal!)}>
                            {confirming === item.reply.proposal.id ? "Применение…" : "Подтвердить изменение плана"}
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {busy && <div className="assistant-thinking" role="status">Сверяю план и наблюдения…</div>}
            </div>
            <form className="assistant-compose" onSubmit={submit}>
              {available === false && <p className="assistant-service-note">Ключ OpenCode Zen недоступен серверу. Остальные функции BuildWatch работают.</p>}
              {error && <p className="assistant-error" role="alert">{error}</p>}
              <label htmlFor="assistant-question">Ваш вопрос или команда</label>
              <textarea ref={input} id="assistant-question" rows={3} maxLength={1000} value={question}
                onChange={(event) => setQuestion(event.target.value)}
                onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); if (question.trim()) void ask(question); } }}
                placeholder="Например: почему котлован под риском?" />
              <div className="assistant-compose-foot">
                <span>{question.length}/1000 · Enter — отправить</span>
                <button type="submit" disabled={!question.trim() || busy || available === false}>Спросить <span aria-hidden="true">↗</span></button>
              </div>
              <p className="assistant-disclaimer">Выводы ИИ требуют проверки. План меняется только после подтверждения.</p>
            </form>
          </section>
        </div>
      )}
    </>
  );
}
