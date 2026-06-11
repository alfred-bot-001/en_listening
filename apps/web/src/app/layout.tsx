import type { Metadata } from "next";
import Link from "next/link";

import "./globals.css";

export const metadata: Metadata = {
  title: "ListenFlow",
  description: "English listening practice workspace",
};

const navItems = [
  { href: "/materials", label: "资料库" },
  { href: "/practice", label: "继续学习" },
  { href: "/favorites", label: "收藏句子" },
  { href: "/wrongbook", label: "错题集" },
];

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
            <nav className="nav" aria-label="Main navigation">
              {navItems.map((item) => (
                <Link key={item.href} href={item.href}>
                  {item.label}
                </Link>
              ))}
            </nav>
          </aside>
          <main className="main">{children}</main>
        </div>
      </body>
    </html>
  );
}

