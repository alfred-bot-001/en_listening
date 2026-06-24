import type { Metadata } from "next";

import AppShell from "./AppShell";
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
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
