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
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto px-6 py-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">
          ★ Favorites
        </h1>
        {loading ? (
          <div className="text-center text-gray-500 py-8">Loading...</div>
        ) : sentences.length === 0 ? (
          <div className="text-center text-gray-400 py-8">
            No favorites yet. Press F during practice to save a sentence.
          </div>
        ) : (
          <div className="space-y-3">
            {sentences.map((s) => (
              <div
                key={s.id}
                className="bg-white rounded-lg shadow-sm p-4 flex justify-between items-start"
              >
                <div>
                  <p className="text-gray-800">{s.text}</p>
                  <p className="text-sm text-gray-400 mt-1">
                    Group {s.group_index + 1} · Sentence {s.sentence_index + 1}
                  </p>
                </div>
                <button
                  onClick={() => handleRemove(s.id)}
                  className="text-yellow-600 hover:text-yellow-800 text-sm"
                >
                  Unfavorite
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
