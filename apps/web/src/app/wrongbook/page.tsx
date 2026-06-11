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
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto px-6 py-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">
          ✗ Wrong Book
        </h1>
        {loading ? (
          <div className="text-center text-gray-500 py-8">Loading...</div>
        ) : sentences.length === 0 ? (
          <div className="text-center text-gray-400 py-8">
            No wrong sentences yet. Mistakes made 3+ times will appear here.
          </div>
        ) : (
          <div className="space-y-3">
            {sentences.map((s) => (
              <div
                key={s.id}
                className="bg-white rounded-lg shadow-sm p-4 border-l-4 border-red-400"
              >
                <p className="text-gray-800">{s.text}</p>
                <div className="flex gap-4 mt-1 text-sm">
                  <span className="text-red-600">
                    ✗ {s.wrong_count} mistake(s)
                  </span>
                  <span className="text-gray-400">
                    Group {s.group_index + 1} · Sentence{" "}
                    {s.sentence_index + 1}
                  </span>
                </div>
                <div className="mt-2 text-sm text-blue-600">
                  Keywords: {s.keywords.join(", ")}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
