"use client";

import { useCallback, useEffect, useState } from "react";
import {
  listMaterials,
  importURL,
  uploadFile,
  deleteMaterial,
  getJobStatus,
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

  const statusBadge = (status: string | null) => {
    if (!status) return null;
    const colors: Record<string, string> = {
      pending: "bg-yellow-100 text-yellow-700",
      downloading: "bg-blue-100 text-blue-700",
      extracting_audio: "bg-blue-100 text-blue-700",
      transcribing: "bg-blue-100 text-blue-700",
      splitting: "bg-blue-100 text-blue-700",
      done: "bg-green-100 text-green-700",
      failed: "bg-red-100 text-red-700",
    };
    return (
      <span
        className={`px-2 py-0.5 rounded text-xs ${
          colors[status] || "bg-gray-100 text-gray-600"
        }`}
      >
        {status}
      </span>
    );
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

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-5xl mx-auto px-6 py-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">
          Materials Library
        </h1>

        {error && (
          <div className="bg-red-50 text-red-700 px-4 py-3 rounded mb-4">
            {error}
          </div>
        )}

        {/* Import section */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">Import Material</h2>

          {/* URL import */}
          <div className="flex gap-3 mb-4">
            <input
              type="text"
              placeholder="YouTube or Bilibili URL"
              value={importUrl}
              onChange={(e) => setImportUrl(e.target.value)}
              className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
            <input
              type="text"
              placeholder="Title (optional)"
              value={importTitle}
              onChange={(e) => setImportTitle(e.target.value)}
              className="w-48 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
            <button
              onClick={handleImport}
              disabled={importing || !importUrl}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {importing ? "Importing..." : "Import"}
            </button>
          </div>

          {/* File upload */}
          <div>
            <label className="px-4 py-2 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 cursor-pointer">
              Upload File
              <input
                type="file"
                accept="video/*,audio/*"
                className="hidden"
                onChange={handleUpload}
              />
            </label>
            <span className="ml-3 text-sm text-gray-500">
              MP4, MKV, AVI, MOV, MP3, WAV, etc.
            </span>
          </div>
        </div>

        {/* Materials list */}
        <div className="bg-white rounded-lg shadow-sm">
          {loading ? (
            <div className="p-8 text-center text-gray-500">Loading...</div>
          ) : materials.length === 0 ? (
            <div className="p-8 text-center text-gray-400">
              No materials yet. Import a video or audio to get started.
            </div>
          ) : (
            <div className="divide-y">
              {materials.map((m) => (
                <div
                  key={m.id}
                  className="flex items-center justify-between px-6 py-4 hover:bg-gray-50"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-xl">{sourceIcon(m.source_type)}</span>
                    <div>
                      <h3 className="font-medium text-gray-900">{m.title}</h3>
                      <div className="flex items-center gap-2 text-sm text-gray-500">
                        <span>{m.source_type}</span>
                        {m.category && <span>· {m.category}</span>}
                        {m.duration_seconds && (
                          <span>
                            · {Math.floor(m.duration_seconds / 60)}:
                            {String(
                              Math.floor(m.duration_seconds % 60)
                            ).padStart(2, "0")}
                          </span>
                        )}
                        {statusBadge(m.job_status)}
                        {jobStatuses[m.id] && (
                          <span className="text-xs text-blue-500">
                            {jobStatuses[m.id]}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    {m.job_status === "done" && (
                      <a
                        href={`/practice?material_id=${m.id}`}
                        className="px-3 py-1 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
                      >
                        Practice
                      </a>
                    )}
                    <button
                      onClick={() => handleDelete(m.id)}
                      className="px-3 py-1 text-red-600 hover:bg-red-50 rounded text-sm"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
