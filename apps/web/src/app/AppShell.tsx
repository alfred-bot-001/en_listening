"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import NavLinks from "./NavLinks";
import { isAuthenticated, logout } from "@/lib/auth";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [checked, setChecked] = useState(false);

  const isLogin = pathname === "/login";

  useEffect(() => {
    if (!isLogin && !isAuthenticated()) {
      router.replace("/login");
      return;
    }
    setChecked(true);
  }, [isLogin, pathname, router]);

  // The login page renders its own full-screen layout (no sidebar).
  if (isLogin) return <>{children}</>;

  // Avoid flashing protected content before the auth check completes.
  if (!checked) return null;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link className="logo" href="/materials">
          ListenFlow
        </Link>
        <NavLinks />
        <button className="button secondary logout-btn" onClick={logout}>
          退出登录
        </button>
      </aside>
      <main className="main">{children}</main>
    </div>
  );
}
