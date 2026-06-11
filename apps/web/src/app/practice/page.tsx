"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  continuePractice,
  getGroup,
  submitAnswer,
  addFavorite,
  removeFavorite,
} from "@/lib/api";
import type { Group, Sentence, SubmitResult } from "@/types/listenflow";

// Material ID from query param
function getMaterialId(): string {
  if (typeof window === "undefined") return "";
  const params = new URLSearchParams(window.location.search);
  return params.get("material_id") || "";
}

export default function PracticePage() {
  const materialId = getMaterialId();
  const [group, setGroup] = useState<Group | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [inputs, setInputs] = useState<Record<string, string>>({});
  const [results, setResults] = useState<Record<string, boolean> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const playCountRef = useRef(0);

  const currentSentence: Sentence | undefined = group?.sentences[currentIndex];

  // Load practice data
  useEffect(() => {
    if (!materialId) {
      setError("No material_id specified");
      setLoading(false);
      return;
    }
    continuePractice(materialId)
      .then((res) => {
        setGroup(res.group);
        setCurrentIndex(res.progress.sentence_index);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [materialId]);

  // Play audio when sentence changes
  useEffect(() => {
    if (!currentSentence) return;
    playCountRef.current = 0;
    setInputs({});
    setResults(null);
    playAudio();
  }, [currentSentence?.id]);

  const playAudio = useCallback(() => {
    if (!currentSentence?.audio_path) return;
    const API_BASE =
      process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const url = `${API_BASE}/storage/${currentSentence.audio_path}`;
    if (!audioRef.current) {
      audioRef.current = new Audio();
    }
    audioRef.current.src = url;
    audioRef.current.play().catch(() => {});
    playCountRef.current += 1;
  }, [currentSentence?.audio_path]);

  // Replay: if already played twice, allow one more replay
  const replay = useCallback(() => {
    playAudio();
  }, [playAudio]);

  // Submit current sentence
  const handleSubmit = useCallback(async () => {
    if (!currentSentence || results) return;
    try {
      const res = await submitAnswer(currentSentence.id, inputs);
      setResults(res.results);
    } catch (e) {
      setError(String(e));
    }
  }, [currentSentence, inputs, results]);

  // Next sentence
  const goNext = useCallback(() => {
    if (!group) return;
    if (currentIndex < group.sentences.length - 1) {
      setCurrentIndex(currentIndex + 1);
    } else {
      // Load next group
      getGroup(materialId, group.group_index + 1)
        .then((g) => {
          setGroup(g);
          setCurrentIndex(0);
        })
        .catch(() => setError("No more groups"));
    }
  }, [group, currentIndex, materialId]);

  // Previous sentence
  const goPrev = useCallback(() => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1);
    }
  }, [currentIndex]);

  // Toggle favorite
  const toggleFavorite = useCallback(async () => {
    if (!currentSentence) return;
    try {
      if (currentSentence.is_favorite) {
        await removeFavorite(currentSentence.id);
      } else {
        await addFavorite(currentSentence.id);
      }
      // Refresh group
      if (group) {
        const g = await getGroup(materialId, group.group_index);
        setGroup(g);
      }
    } catch (e) {
      setError(String(e));
    }
  }, [currentSentence, group, materialId]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) {
        if (e.key === "Enter") {
          e.preventDefault();
          if (results) {
            goNext();
          } else {
            handleSubmit();
          }
        }
        return;
      }
      switch (e.key) {
        case " ":
          e.preventDefault();
          replay();
          break;
        case "r":
          replay();
          break;
        case "ArrowRight":
          if (results) goNext();
          break;
        case "ArrowLeft":
          goPrev();
          break;
        case "f":
          toggleFavorite();
          break;
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [replay, handleSubmit, goNext, goPrev, toggleFavorite, results]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-xl text-gray-500">Loading practice...</div>
      </div>
    );
  }

  if (error && !group) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-xl text-red-500">{error}</div>
      </div>
    );
  }

  if (!group || !currentSentence) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-xl text-gray-500">No sentences available</div>
      </div>
    );
  }

  const allCorrect = results
    ? Object.values(results).every(Boolean)
    : false;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-gray-900">
            Group {group.group_index + 1}
          </h1>
          <p className="text-sm text-gray-500">
            Sentence {currentIndex + 1} / {group.total_sentences}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={toggleFavorite}
            className={`px-3 py-1 rounded text-sm ${
              currentSentence.is_favorite
                ? "bg-yellow-100 text-yellow-700"
                : "bg-gray-100 text-gray-600"
            }`}
          >
            {currentSentence.is_favorite ? "★ Favorited" : "☆ Favorite"} (F)
          </button>
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-1 bg-gray-200">
        <div
          className="h-full bg-blue-500 transition-all"
          style={{
            width: `${((currentIndex + 1) / group.total_sentences) * 100}%`,
          }}
        />
      </div>

      {/* Main content */}
      <div className="max-w-3xl mx-auto px-6 py-12">
        {/* Sentence display */}
        <div className="bg-white rounded-lg shadow-sm p-8 mb-8">
          <p className="text-xl leading-relaxed">
            {renderDisplayText(
              currentSentence.display_text,
              currentSentence.keywords,
              inputs,
              results
            )}
          </p>
        </div>

        {/* Input area */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <h3 className="text-sm font-medium text-gray-500 mb-3">
            Fill in the blanks:
          </h3>
          <div className="space-y-3">
            {currentSentence.keywords.map((kw) => (
              <div key={kw} className="flex items-center gap-3">
                <label className="text-sm text-gray-600 w-24">{kw}</label>
                <input
                  type="text"
                  value={inputs[kw] || ""}
                  onChange={(e) =>
                    setInputs({ ...inputs, [kw]: e.target.value })
                  }
                  disabled={results !== null}
                  className={`flex-1 px-3 py-2 border rounded-md text-lg focus:outline-none focus:ring-2 focus:ring-blue-400 ${
                    results
                      ? results[kw]
                        ? "border-green-500 bg-green-50 text-green-700"
                        : "border-red-500 bg-red-50 text-red-700"
                      : "border-gray-300"
                  }`}
                  placeholder="Type here..."
                  autoFocus={currentSentence.keywords.indexOf(kw) === 0}
                />
                {results && !results[kw] && (
                  <span className="text-sm text-green-600">
                    Answer: {kw}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex gap-3">
          {!results ? (
            <button
              onClick={handleSubmit}
              className="flex-1 bg-blue-600 text-white py-3 rounded-lg text-lg font-medium hover:bg-blue-700"
            >
              Check (Enter)
            </button>
          ) : (
            <>
              {allCorrect && (
                <div className="flex-1 bg-green-50 text-green-700 py-3 rounded-lg text-center text-lg font-medium">
                  ✓ All correct!
                </div>
              )}
              <button
                onClick={goNext}
                className="flex-1 bg-blue-600 text-white py-3 rounded-lg text-lg font-medium hover:bg-blue-700"
              >
                Next → (Enter)
              </button>
            </>
          )}
          <button
            onClick={replay}
            className="px-6 py-3 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200"
          >
            🔊 Play (Space)
          </button>
        </div>

        {/* Wrong book indicator */}
        {results && !allCorrect && (
          <div className="mt-4 text-sm text-orange-600">
            {Object.values(results).filter((v) => !v).length} mistake(s).
            {currentSentence.wrong_count + 1 >= 3 &&
              " Added to wrong book!"}
          </div>
        )}
      </div>

      {/* Shortcuts help */}
      <div className="fixed bottom-4 right-4 bg-white/90 shadow rounded-lg p-3 text-xs text-gray-500 space-y-1">
        <div>
          <kbd className="px-1 bg-gray-100 rounded">Space</kbd> /{" "}
          <kbd className="px-1 bg-gray-100 rounded">R</kbd> Play
        </div>
        <div>
          <kbd className="px-1 bg-gray-100 rounded">Enter</kbd> Check / Next
        </div>
        <div>
          <kbd className="px-1 bg-gray-100 rounded">←</kbd>{" "}
          <kbd className="px-1 bg-gray-100 rounded">→</kbd> Prev / Next
        </div>
        <div>
          <kbd className="px-1 bg-gray-100 rounded">F</kbd> Favorite
        </div>
      </div>
    </div>
  );
}

function renderDisplayText(
  displayText: string,
  keywords: string[],
  inputs: Record<string, string>,
  results: Record<string, boolean> | null
) {
  // Split display text by ____ placeholders
  const parts = displayText.split("____");
  const elements: React.ReactNode[] = [];

  for (let i = 0; i < parts.length; i++) {
    elements.push(
      <span key={`text-${i}`} className="text-gray-800">
        {parts[i]}
      </span>
    );
    if (i < keywords.length) {
      const kw = keywords[i];
      const value = inputs[kw] || "";
      let className = "border-b-2 px-1 ";
      if (results) {
        className += results[kw]
          ? "border-green-500 text-green-700 bg-green-50"
          : "border-red-500 text-red-700 bg-red-50";
      } else {
        className += value
          ? "border-blue-400 text-blue-600"
          : "border-gray-300 text-gray-400";
      }
      elements.push(
        <span key={`blank-${i}`} className={className}>
          {value || "____"}
        </span>
      );
    }
  }

  return elements;
}
