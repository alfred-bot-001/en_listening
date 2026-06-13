import type { Metadata } from "next";
import Link from "next/link";

import NavLinks from "./NavLinks";
import "./globals.css";

export const metadata: Metadata = {
  title: "ListenFlow",
  description: "English listening practice workspace",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>
        <div className="app-shell">
          <aside className="sidebar">
            <Link className="logo" href="/materials">
              ListenFlow
            </Link>
            <NavLinks />
          </aside>
          <main className="main">{children}</main>
        </div>
      </body>
    </html>
  );
}
