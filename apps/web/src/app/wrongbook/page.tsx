"use client";

import { useEffect, useState } from "react";
import { getWrongbook } from "@/lib/api";
import type { Sentence } from "@/types/listenflow";

export default function WrongbookPage() {
  const [sentences, setSentences] = useState<Sentence[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getWrongbook()
      .then(setSentences)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="page">
      <div className="page-head">
        <h1>✗ 错题集</h1>
      </div>
      {loading ? (
        <div className="empty">加载中…</div>
      ) : sentences.length === 0 ? (
        <div className="empty">还没有错题。同一句错满 3 次会出现在这里。</div>
      ) : (
        <div className="grid">
          {sentences.map((s) => (
            <div key={s.id} className="sentence-item is-wrong">
              <div>
                <p>{s.text}</p>
                <div className="sentence-meta">
                  <span className="danger">✗ 错 {s.wrong_count} 次</span>
                  <span>
                    第 {s.group_index + 1} 组 · 第 {s.sentence_index + 1} 句
                  </span>
                  <span>关键词：{s.keywords.join("、")}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
