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
  const firstInputRef = useRef<HTMLInputElement | null>(null);

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

  // Focus first blank once the inputs are actually enabled.
  // Why a separate effect: setResults(null) above is batched, so the input
  // is still disabled when the prior effect runs — focus() would be ignored.
  useEffect(() => {
    if (results === null && currentSentence) {
      firstInputRef.current?.focus();
    }
  }, [results, currentSentence?.id]);

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
        case "Enter":
          e.preventDefault();
          if (results) goNext();
          else handleSubmit();
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
    return <div className="center-screen">加载练习中…</div>;
  }

  if (error && !group) {
    return (
      <div className="center-screen" style={{ color: "var(--red)" }}>
        {error}
      </div>
    );
  }

  if (!group || !currentSentence) {
    return <div className="center-screen">没有可练习的句子</div>;
  }

  const allCorrect = results
    ? Object.values(results).every(Boolean)
    : false;

  return (
    <div className="page">
      {/* Header */}
      <div className="page-head">
        <div>
          <h1>第 {group.group_index + 1} 组</h1>
          <p className="subtitle">
            第 {currentIndex + 1} / {group.total_sentences} 句
          </p>
        </div>
        <button
          className={`chip ${currentSentence.is_favorite ? "ready" : ""}`}
          style={{ border: 0, cursor: "pointer" }}
          onClick={toggleFavorite}
        >
          {currentSentence.is_favorite ? "★ 已收藏" : "☆ 收藏"} (F)
        </button>
      </div>

      {/* Progress */}
      <div className="progress-track" style={{ marginBottom: 24 }}>
        <div
          className="progress-fill"
          style={{
            width: `${((currentIndex + 1) / group.total_sentences) * 100}%`,
          }}
        />
      </div>

      <div className="practice-layout">
        <div className="grid">
          {/* Sentence */}
          <div className="card practice-card">
            <p className="sentence">
              {renderDisplayText(
                currentSentence.display_text,
                currentSentence.keywords,
                inputs,
                results
              )}
            </p>
          </div>

          {/* Inputs */}
          <div className="panel">
            <h3 className="panel-title">填空</h3>
            <div className="answers">
              {currentSentence.keywords.map((kw, idx) => (
                <div key={kw} className="answer-row">
                  <input
                    ref={idx === 0 ? firstInputRef : undefined}
                    className={`blank-input ${
                      results ? (results[kw] ? "correct" : "wrong") : ""
                    }`}
                    type="text"
                    value={inputs[kw] || ""}
                    onChange={(e) =>
                      setInputs({ ...inputs, [kw]: e.target.value })
                    }
                    disabled={results !== null}
                    placeholder="在此输入…"
                  />
                  {results && !results[kw] && (
                    <span style={{ color: "var(--green)", fontSize: 14 }}>
                      答案：{kw}
                    </span>
                  )}
                </div>
              ))}
            </div>

            {/* Buttons */}
            <div className="row-buttons">
              {!results ? (
                <button
                  className="button"
                  style={{ flex: 1 }}
                  onClick={handleSubmit}
                >
                  检查 (Enter)
                </button>
              ) : (
                <>
                  {allCorrect && <div className="banner-success">✓ 全部正确</div>}
                  <button
                    className="button"
                    style={{ flex: 1 }}
                    onClick={goNext}
                  >
                    下一句 → (Enter)
                  </button>
                </>
              )}
              <button className="button secondary" onClick={replay}>
                🔊 播放 (Space)
              </button>
            </div>

            {results && !allCorrect && (
              <p style={{ color: "var(--red)", fontSize: 14, marginTop: 14 }}>
                错 {Object.values(results).filter((v) => !v).length} 处。
                {currentSentence.wrong_count + 1 >= 3 && " 已加入错题集！"}
              </p>
            )}
          </div>
        </div>

        {/* Shortcuts */}
        <div className="panel">
          <h3 className="panel-title">快捷键</h3>
          <div className="shortcuts">
            <div>
              <span className="kbd">Space</span> / <span className="kbd">R</span> 播放
            </div>
            <div>
              <span className="kbd">Enter</span> 检查 / 下一句
            </div>
            <div>
              <span className="kbd">←</span> <span className="kbd">→</span> 上一句 / 下一句
            </div>
            <div>
              <span className="kbd">F</span> 收藏
            </div>
          </div>
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
  const parts = displayText.split("____");
  const elements: React.ReactNode[] = [];

  for (let i = 0; i < parts.length; i++) {
    elements.push(
      <span key={`text-${i}`} className="token">
        {parts[i]}
      </span>
    );
    if (i < keywords.length) {
      const kw = keywords[i];
      const value = inputs[kw] || "";
      let cls = "blank";
      if (results) {
        cls += results[kw] ? " correct" : " wrong";
      } else if (value) {
        cls += " filled";
      }
      elements.push(
        <span key={`blank-${i}`} className={cls}>
          {value || "____"}
        </span>
      );
    }
  }

  return elements;
}
