"use client";

import { useCallback, useEffect, useState } from "react";
import {
  listMaterials,
  importURL,
  uploadFile,
  deleteMaterial,
  getJobStatus,
  reanalyzeKeywords,
} from "@/lib/api";
import type { Material } from "@/types/listenflow";

export default function MaterialsPage() {
  const [materials, setMaterials] = useState<Material[]>([]);
  const [loading, setLoading] = useState(true);
  const [importUrl, setImportUrl] = useState("");
  const [importTitle, setImportTitle] = useState("");
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState("");
  const [jobStatuses, setJobStatuses] = useState<Record<string, string>>({});
  const [reanalyzing, setReanalyzing] = useState<Record<string, boolean>>({});

  const load = useCallback(async () => {
    try {
      const data = await listMaterials();
      setMaterials(data);
      // Poll job statuses for pending/processing materials
      for (const m of data) {
        if (
          m.job_status &&
          !["done", "failed"].includes(m.job_status)
        ) {
          getJobStatus(m.id).then((j) =>
            setJobStatuses((prev) => ({
              ...prev,
              [m.id]: `${Math.round(j.progress)}%`,
            }))
          );
        }
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleImport = useCallback(async () => {
    if (!importUrl) return;
    setImporting(true);
    setError("");
    try {
      await importURL(importUrl, importTitle || undefined);
      setImportUrl("");
      setImportTitle("");
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setImporting(false);
    }
  }, [importUrl, importTitle, load]);

  const handleUpload = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;
      setError("");
      try {
        await uploadFile(file);
        await load();
      } catch (e) {
        setError(String(e));
      }
    },
    [load]
  );

  const handleDelete = useCallback(
    async (id: string) => {
      try {
        await deleteMaterial(id);
        await load();
      } catch (e) {
        setError(String(e));
      }
    },
    [load]
  );

  const handleReanalyze = useCallback(
    async (id: string) => {
      setReanalyzing((prev) => ({ ...prev, [id]: true }));
      setError("");
      try {
        await reanalyzeKeywords(id);
      } catch (e) {
        setError(String(e));
      } finally {
        setReanalyzing((prev) => {
          const next = { ...prev };
          delete next[id];
          return next;
        });
      }
    },
    []
  );

  const statusChip = (status: string | null) => {
    if (!status) return null;
    const variant =
      status === "done"
        ? "done"
        : status === "failed"
          ? "failed"
          : status === "pending"
            ? "pending"
            : "processing";
    return <span className={`chip ${variant}`}>{status}</span>;
  };

  const sourceIcon = (type: string) => {
    switch (type) {
      case "youtube":
        return "🎬";
      case "bilibili":
        return "📺";
      case "video":
        return "🎥";
      case "audio":
        return "🎵";
      default:
        return "📄";
    }
  };

  const formatDuration = (s: number) =>
    `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

  return (
    <div className="page">
      <div className="page-head">
        <h1>资料库</h1>
      </div>

      {error && <div className="alert error">{error}</div>}

      {/* Import */}
      <div className="panel">
        <h2 className="panel-title">导入素材</h2>
        <div className="form-row">
          <input
            className="input grow"
            type="text"
            placeholder="YouTube 或 Bilibili 链接"
            value={importUrl}
            onChange={(e) => setImportUrl(e.target.value)}
          />
          <input
            className="input"
            type="text"
            placeholder="标题（可选）"
            value={importTitle}
            onChange={(e) => setImportTitle(e.target.value)}
          />
          <button
            className="button"
            onClick={handleImport}
            disabled={importing || !importUrl}
          >
            {importing ? "导入中…" : "导入"}
          </button>
        </div>
        <div className="form-row" style={{ marginTop: 14 }}>
          <label className="button secondary upload">
            上传文件
            <input
              type="file"
              accept="video/*,audio/*,.srt,.vtt,.txt"
              onChange={handleUpload}
            />
          </label>
          <span className="hint">支持 MP4 / MKV / MOV / MP3 / WAV，或 SRT / VTT / TXT 字幕</span>
        </div>
      </div>

      {/* List */}
      <div className="list">
        {loading ? (
          <div className="empty">加载中…</div>
        ) : materials.length === 0 ? (
          <div className="empty">还没有素材，导入一个视频/音频或字幕开始吧。</div>
        ) : (
          materials.map((m) => (
            <div key={m.id} className="row">
              <div className="row-main">
                <span className="avatar">{sourceIcon(m.source_type)}</span>
                <div>
                  <h3 className="row-title">{m.title}</h3>
                  <div className="row-meta">
                    <span>{m.source_type}</span>
                    {m.category && <span>· {m.category}</span>}
                    {m.duration_seconds && (
                      <span>· {formatDuration(m.duration_seconds)}</span>
                    )}
                    {statusChip(m.job_status)}
                    {jobStatuses[m.id] && (
                      <span style={{ color: "var(--blue)" }}>
                        {jobStatuses[m.id]}
                      </span>
                    )}
                  </div>
                </div>
              </div>
              <div className="row-actions">
                {m.job_status === "done" && (
                  <>
                    <a className="button small" href={`/practice/${m.id}`}>
                      练习
                    </a>
                    <button
                      className="button secondary small"
                      onClick={() => handleReanalyze(m.id)}
                      disabled={!!reanalyzing[m.id]}
                      title="用 LLM 重新挑选每句的关键词"
                    >
                      {reanalyzing[m.id] ? "分析中…" : "重新分析"}
                    </button>
                  </>
                )}
                <button
                  className="button ghost small"
                  onClick={() => handleDelete(m.id)}
                >
                  删除
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
