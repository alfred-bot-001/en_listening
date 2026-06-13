"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/materials", label: "资料库" },
  { href: "/practice", label: "继续学习" },
  { href: "/favorites", label: "收藏句子" },
  { href: "/wrongbook", label: "错题集" },
];

export default function NavLinks() {
  const pathname = usePathname();
  return (
    <nav className="nav" aria-label="Main navigation">
      {navItems.map((item) => {
        const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={active ? "active" : undefined}
            aria-current={active ? "page" : undefined}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
