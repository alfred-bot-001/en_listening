"use client";

import { useEffect, useState } from "react";
import { use } from "react";
import Link from "next/link";
import { getStages, type Stage } from "@/lib/api";

const star = (filled: boolean) => (filled ? "★" : "☆");

function StarRow({ stars }: { stars: number }) {
  return (
    <span className="stage-stars" aria-label={`${stars} of 3 stars`}>
      <span className={stars >= 1 ? "on" : "off"}>{star(stars >= 1)}</span>
      <span className={stars >= 2 ? "on" : "off"}>{star(stars >= 2)}</span>
      <span className={stars >= 3 ? "on" : "off"}>{star(stars >= 3)}</span>
    </span>
  );
}

export default function StagesPage({
  params,
}: {
  params: Promise<{ materialId: string }>;
}) {
  const { materialId } = use(params);
  const [stages, setStages] = useState<Stage[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getStages(materialId)
      .then((res) => setStages(res.stages))
      .catch((e) => setError(String(e)));
  }, [materialId]);

  if (error) {
    return (
      <div className="page">
        <div className="alert error">{error}</div>
      </div>
    );
  }
  if (stages === null) {
    return <div className="center-screen">加载关卡中…</div>;
  }
  if (stages.length === 0) {
    return (
      <div className="page">
        <div className="page-head">
          <h1>关卡</h1>
        </div>
        <div className="empty">这个素材还没切出句子。</div>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-head">
        <h1>关卡</h1>
        <p className="subtitle">共 {stages.length} 关 · 自由解锁</p>
      </div>

      <div className="stages-grid">
        {stages.map((s) => (
          <Link
            key={s.group_index}
            href={`/practice?material_id=${materialId}&group_index=${s.group_index}`}
            className="stage-card"
          >
            <div className="stage-card-head">
              <h2>第 {s.group_index + 1} 关</h2>
              <StarRow stars={s.stars} />
            </div>
            <div className="stage-card-body">
              <span className="stage-meta">{s.sentence_count} 句</span>
              {s.attempts > 0 ? (
                <span className="stage-meta">
                  最佳 {Math.round(s.best_accuracy)}% · {s.attempts} 次
                </span>
              ) : (
                <span className="stage-meta muted">未挑战</span>
              )}
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
