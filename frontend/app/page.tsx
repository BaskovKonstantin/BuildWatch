"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Topbar } from "@/components/Topbar";

type Obj = {
  id: number;
  name: string;
  type: string;
  snapshots: number;
  warnings_open: number;
  cover: string | null;
};

export default function Home() {
  const [objects, setObjects] = useState<Obj[] | null>(null);
  useEffect(() => {
    fetch("/api/objects")
      .then((r) => r.json())
      .then(setObjects)
      .catch(() => setObjects([]));
  }, []);

  return (
    <main>
      <Topbar crumbs="Объекты" />
      <div className="grid">
        {objects === null ? (
          <div className="empty">Загрузка…</div>
        ) : objects.length === 0 ? (
          <div className="empty">Нет объектов</div>
        ) : (
          objects.map((o) => (
            <Link key={o.id} className="obj-card" href={`/objects/${o.id}`}>
              {o.cover && <img src={o.cover} alt={o.name} />}
              <div className="obj-body">
                <div className="obj-name">{o.name}</div>
                <div className="obj-meta">
                  <span className="chip ok">Снимков: {o.snapshots}</span>
                  {o.warnings_open > 0 ? (
                    <span className="chip bad">
                      Предупреждений: {o.warnings_open}
                    </span>
                  ) : (
                    <span className="chip ok">Нарушений нет</span>
                  )}
                  <span className="chip">{o.type}</span>
                </div>
              </div>
            </Link>
          ))
        )}
      </div>
    </main>
  );
}
