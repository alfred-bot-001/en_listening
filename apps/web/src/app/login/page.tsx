"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { login } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(username, password);
      router.replace("/materials");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-screen">
      <form className="panel login-card" onSubmit={handleSubmit}>
        <h1 className="login-logo">🎧 ListenFlow</h1>
        <p className="subtitle" style={{ marginBottom: 20 }}>
          登录以继续
        </p>
        {error && <div className="alert error">{error}</div>}
        <label className="login-field">
          <span>用户名</span>
          <input
            className="input"
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoFocus
            autoComplete="username"
          />
        </label>
        <label className="login-field">
          <span>密码</span>
          <input
            className="input"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
          />
        </label>
        <button
          className="button"
          type="submit"
          disabled={loading || !username || !password}
          style={{ width: "100%", justifyContent: "center", marginTop: 8 }}
        >
          {loading ? "登录中…" : "登录"}
        </button>
      </form>
    </div>
  );
}
