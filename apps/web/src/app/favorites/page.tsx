"use client";

import { useEffect, useState } from "react";
import { getFavorites, removeFavorite } from "@/lib/api";
import type { Sentence } from "@/types/listenflow";

export default function FavoritesPage() {
  const [sentences, setSentences] = useState<Sentence[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getFavorites()
      .then(setSentences)
      .finally(() => setLoading(false));
  }, []);

  const handleRemove = async (id: string) => {
    await removeFavorite(id);
    setSentences((prev) => prev.filter((s) => s.id !== id));
  };

  return (
    <div className="page">
      <div className="page-head">
        <h1>★ 收藏句子</h1>
      </div>
      {loading ? (
        <div className="empty">加载中…</div>
      ) : sentences.length === 0 ? (
        <div className="empty">还没有收藏。练习时按 F 即可收藏当前句。</div>
      ) : (
        <div className="grid">
          {sentences.map((s) => (
            <div key={s.id} className="sentence-item">
              <div>
                <p>{s.text}</p>
                <div className="sentence-meta">
                  <span>
                    第 {s.group_index + 1} 组 · 第 {s.sentence_index + 1} 句
                  </span>
                </div>
              </div>
              <button
                className="button ghost small"
                onClick={() => handleRemove(s.id)}
              >
                取消收藏
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
