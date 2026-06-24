"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  continuePractice,
  getGroup,
  submitAnswer,
  addFavorite,
  removeFavorite,
  recentMaterial,
  completeStage,
  type Stage,
} from "@/lib/api";
import type { Group, Sentence } from "@/types/listenflow";

// URL query helpers — both run client-side only.
function getMaterialId(): string {
  if (typeof window === "undefined") return "";
  return new URLSearchParams(window.location.search).get("material_id") || "";
}

function getGroupIndexParam(): number | null {
  if (typeof window === "undefined") return null;
  const raw = new URLSearchParams(window.location.search).get("group_index");
  if (raw === null) return null;
  const n = Number(raw);
  return Number.isFinite(n) && n >= 0 ? Math.floor(n) : null;
}

// Mirror of backend listenflow.modules.practice.domain.normalize_answer
function normalize(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/’/g, "'")
    .replace(/^[^a-z0-9']+|[^a-z0-9']+$/g, "");
}

// Per-blank state: null = not yet judged, true/false = judged.
type Verdicts = Record<string, boolean | null>;

export default function PracticePage() {
  const router = useRouter();
  const materialId = getMaterialId();
  const requestedGroupIndex = getGroupIndexParam();
  const [group, setGroup] = useState<Group | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [inputs, setInputs] = useState<Record<string, string>>({});
  const [verdicts, setVerdicts] = useState<Verdicts>({});
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  // Per-attempt tally accumulated across the sentences of the current stage.
  const [stageCorrect, setStageCorrect] = useState(0);
  const [stageTotal, setStageTotal] = useState(0);
  const [stageResult, setStageResult] = useState<Stage | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const playCountRef = useRef(0);
  const inputRefs = useRef<Record<string, HTMLInputElement | null>>({});

  const currentSentence: Sentence | undefined = group?.sentences[currentIndex];
  const keywords = currentSentence?.keywords ?? [];
  const allJudged =
    keywords.length > 0 && keywords.every((kw) => verdicts[kw] != null);
  const allCorrect = allJudged && keywords.every((kw) => verdicts[kw] === true);

  // Load practice data:
  //   1. no material_id → "continue learning" → redirect to recent material
  //   2. material_id + group_index → load that exact stage (entered from card)
  //   3. material_id only → resume from saved progress
  useEffect(() => {
    if (!materialId) {
      recentMaterial()
        .then((res) => {
          if (res) {
            router.replace(`/practice?material_id=${res.material_id}`);
          } else {
            router.replace("/materials");
          }
        })
        .catch((e) => {
          setError(e.message);
          setLoading(false);
        });
      return;
    }
    if (requestedGroupIndex !== null) {
      getGroup(materialId, requestedGroupIndex)
        .then((g) => {
          setGroup(g);
          setCurrentIndex(0);
        })
        .catch((e) => setError(e.message))
        .finally(() => setLoading(false));
    } else {
      continuePractice(materialId)
        .then((res) => {
          setGroup(res.group);
          setCurrentIndex(res.progress.sentence_index);
        })
        .catch((e) => setError(e.message))
        .finally(() => setLoading(false));
    }
  }, [materialId, requestedGroupIndex, router]);

  // Reset attempt tally when we land on a new stage (group).
  useEffect(() => {
    setStageCorrect(0);
    setStageTotal(0);
    setStageResult(null);
  }, [group?.material_id, group?.group_index]);

  // Reset per-sentence state and play audio when sentence changes.
  useEffect(() => {
    if (!currentSentence) return;
    playCountRef.current = 0;
    setInputs({});
    setVerdicts({});
    setSubmitted(false);
    inputRefs.current = {};
    playAudio();
  }, [currentSentence?.id]);

  // Focus the first still-pending blank when the sentence (re)loads.
  useEffect(() => {
    if (!currentSentence || allJudged) return;
    const firstPending = keywords.find((kw) => verdicts[kw] !== true);
    if (firstPending) inputRefs.current[firstPending]?.focus();
  }, [currentSentence?.id, allJudged, keywords, verdicts]);

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

  // After every blank has been judged: (a) sync to the backend for stats,
  // (b) fold this sentence's correct/total into the stage tally.
  useEffect(() => {
    if (!currentSentence || !allJudged || submitted) return;
    setSubmitted(true);
    submitAnswer(currentSentence.id, inputs).catch((e) => setError(String(e)));
    const correct = keywords.filter((kw) => verdicts[kw] === true).length;
    setStageCorrect((c) => c + correct);
    setStageTotal((t) => t + keywords.length);
  }, [currentSentence, allJudged, submitted, inputs, keywords, verdicts]);

  // Focus the next still-pending blank, or null when nothing is pending.
  const focusNextPending = useCallback(
    (currentKw: string, newVerdicts: Verdicts) => {
      const startIdx = keywords.indexOf(currentKw);
      for (let i = startIdx + 1; i < keywords.length; i++) {
        if (newVerdicts[keywords[i]] !== true) {
          inputRefs.current[keywords[i]]?.focus();
          return;
        }
      }
      // Wrap to any still-pending (could be earlier blanks the user skipped).
      for (let i = 0; i < keywords.length; i++) {
        if (newVerdicts[keywords[i]] !== true && i !== startIdx) {
          inputRefs.current[keywords[i]]?.focus();
          return;
        }
      }
    },
    [keywords]
  );

  // Live-grade on every keystroke: a typed-perfect blank turns green and
  // hands focus to the next blank without requiring Enter.
  const handleInputChange = useCallback(
    (kw: string, value: string) => {
      setInputs((prev) => ({ ...prev, [kw]: value }));
      if (verdicts[kw] !== null && verdicts[kw] !== undefined) return;
      if (normalize(value) === normalize(kw)) {
        const next: Verdicts = { ...verdicts, [kw]: true };
        setVerdicts(next);
        focusNextPending(kw, next);
      }
    },
    [verdicts, focusNextPending]
  );

  // Enter inside a blank: judge that blank (if not yet) and advance.
  const handleBlankEnter = useCallback(
    (kw: string) => {
      const existing = verdicts[kw];
      if (existing != null) {
        focusNextPending(kw, verdicts);
        return;
      }
      const value = inputs[kw] || "";
      const correct = normalize(value) === normalize(kw);
      const next: Verdicts = { ...verdicts, [kw]: correct };
      setVerdicts(next);
      focusNextPending(kw, next);
    },
    [verdicts, inputs, focusNextPending]
  );

  // 显示答案: mark every pending blank as wrong so its answer shows up,
  // useful when the learner gives up on the rest of the sentence.
  const revealRemaining = useCallback(() => {
    if (allJudged) return;
    setVerdicts((prev) => {
      const next: Verdicts = { ...prev };
      for (const kw of keywords) {
        if (next[kw] == null) next[kw] = false;
      }
      return next;
    });
  }, [allJudged, keywords]);

  // Next sentence — last sentence of the stage triggers the summary modal
  // instead of silently rolling into the next group.
  const goNext = useCallback(() => {
    if (!group) return;
    if (currentIndex < group.sentences.length - 1) {
      setCurrentIndex(currentIndex + 1);
      return;
    }
    if (stageResult !== null) return; // already showing summary
    // Fold in this sentence even if the user pressed Enter very fast — the
    // tally-effect runs after render, so use a fresh snapshot here.
    const lastCorrect = keywords.filter((kw) => verdicts[kw] === true).length;
    const correct = stageCorrect + (submitted ? 0 : lastCorrect);
    const total = stageTotal + (submitted ? 0 : keywords.length);
    completeStage(materialId, group.group_index, correct, total)
      .then(setStageResult)
      .catch((e) => setError(String(e)));
  }, [
    group,
    currentIndex,
    materialId,
    stageCorrect,
    stageTotal,
    stageResult,
    keywords,
    verdicts,
    submitted,
  ]);

  const restartStage = useCallback(() => {
    if (!group) return;
    setCurrentIndex(0);
    setInputs({});
    setVerdicts({});
    setSubmitted(false);
    setStageCorrect(0);
    setStageTotal(0);
    setStageResult(null);
  }, [group]);

  const loadNextStage = useCallback(() => {
    if (!group) return;
    const nextIndex = group.group_index + 1;
    getGroup(materialId, nextIndex)
      .then((g) => {
        setGroup(g);
        setCurrentIndex(0);
        setStageResult(null);
        // The router URL drifts out of sync with the loaded stage; rewrite it
        // so reloads and 后退 keep landing on the right place.
        if (typeof window !== "undefined") {
          window.history.replaceState(
            null,
            "",
            `/practice?material_id=${materialId}&group_index=${nextIndex}`
          );
        }
      })
      .catch(() => setError("已是最后一关"));
  }, [group, materialId]);

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

  // Window-level shortcuts. Enter inside a blank is handled per-input below
  // — this hook only sees Enter when focus has left the inputs (e.g. once
  // every blank is judged and they're all disabled).
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) return; // per-input handler
      switch (e.key) {
        case " ":
          e.preventDefault();
          replay();
          break;
        case "r":
          replay();
          break;
        case "Enter":
          if (allJudged) {
            e.preventDefault();
            goNext();
          }
          break;
        case "ArrowRight":
          if (allJudged) goNext();
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
  }, [replay, goNext, goPrev, toggleFavorite, allJudged]);

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

  const wrongCount = keywords.filter((kw) => verdicts[kw] === false).length;

  return (
    <div className="page">
      {stageResult && (
        <StageSummary
          stage={stageResult}
          materialId={materialId}
          onRestart={restartStage}
          onNext={loadNextStage}
        />
      )}

      {/* Header */}
      <div className="page-head">
        <div>
          <h1>第 {group.group_index + 1} 关</h1>
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
          {/* Sentence with inline blanks */}
          <div className="card practice-card">
            <p className="sentence">
              {renderInlineBlanks({
                displayText: currentSentence.display_text,
                keywords: currentSentence.keywords,
                inputs,
                verdicts,
                registerRef: (kw, el) => {
                  inputRefs.current[kw] = el;
                },
                onChange: handleInputChange,
                onEnter: handleBlankEnter,
              })}
            </p>
          </div>

          {/* Buttons */}
          <div className="panel">
            <div className="row-buttons">
              {allJudged ? (
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
              ) : (
                <button
                  className="button secondary"
                  style={{ flex: 1 }}
                  onClick={revealRemaining}
                >
                  显示答案
                </button>
              )}
              <button className="button secondary" onClick={replay}>
                🔊 播放 (Space)
              </button>
            </div>

            {allJudged && wrongCount > 0 && (
              <p style={{ color: "var(--red)", fontSize: 14, marginTop: 14 }}>
                错 {wrongCount} 处。
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
              <span className="kbd">Enter</span> 检查当前空 / 下一空 / 下一句
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

function StageSummary({
  stage,
  materialId,
  onRestart,
  onNext,
}: {
  stage: Stage;
  materialId: string;
  onRestart: () => void;
  onNext: () => void;
}) {
  const accuracy = Math.round(stage.best_accuracy);
  const star = (filled: boolean) => (filled ? "★" : "☆");
  return (
    <div className="stage-summary-backdrop" role="dialog" aria-modal="true">
      <div className="stage-summary">
        <h2>第 {stage.group_index + 1} 关 完成</h2>
        <div className="stage-summary-stars">
          <span className={stage.stars >= 1 ? "on" : "off"}>
            {star(stage.stars >= 1)}
          </span>
          <span className={stage.stars >= 2 ? "on" : "off"}>
            {star(stage.stars >= 2)}
          </span>
          <span className={stage.stars >= 3 ? "on" : "off"}>
            {star(stage.stars >= 3)}
          </span>
        </div>
        <p className="stage-summary-meta">
          最佳正确率 {accuracy}% · 共 {stage.attempts} 次挑战
        </p>
        <div className="stage-summary-actions">
          <button className="button secondary" onClick={onRestart}>
            重玩本关
          </button>
          <button className="button" onClick={onNext}>
            下一关 →
          </button>
          <a
            className="button ghost"
            href={`/practice/${materialId}`}
          >
            回章节
          </a>
        </div>
      </div>
    </div>
  );
}

function renderInlineBlanks({
  displayText,
  keywords,
  inputs,
  verdicts,
  registerRef,
  onChange,
  onEnter,
}: {
  displayText: string;
  keywords: string[];
  inputs: Record<string, string>;
  verdicts: Verdicts;
  registerRef: (kw: string, el: HTMLInputElement | null) => void;
  onChange: (kw: string, value: string) => void;
  onEnter: (kw: string) => void;
}) {
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
      const judged = verdicts[kw];
      const verdictClass =
        judged === true ? "correct" : judged === false ? "wrong" : "";
      // Size to the expected word so the blank visually hints at the length.
      const size = Math.max(kw.length + 1, 4);
      elements.push(
        <span key={`blank-${i}`} className="inline-blank">
          <input
            ref={(el) => registerRef(kw, el)}
            className={`blank-input ${verdictClass}`}
            type="text"
            value={value}
            onChange={(e) => onChange(kw, e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                onEnter(kw);
              }
            }}
            disabled={judged != null}
            size={size}
            autoComplete="off"
            spellCheck={false}
          />
          {judged === false && <span className="blank-answer">{kw}</span>}
        </span>
      );
    }
  }

  return elements;
}
