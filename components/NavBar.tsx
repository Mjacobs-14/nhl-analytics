"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const tabs = [
  { href: "/", label: "The Board" },
  { href: "/analytics", label: "Analytics" },
];

export function NavBar() {
  const path = usePathname();

  return (
    <nav className="flex gap-5 mt-3" aria-label="Sections">
      {tabs.map((t) => {
        const active =
          t.href === "/"
            ? path === "/" || path.startsWith("/player")
            : path.startsWith(t.href);
        return (
          <Link
            key={t.href}
            href={t.href}
            className="display text-sm no-underline pb-0.5"
            aria-current={active ? "page" : undefined}
            style={{
              color: active ? "var(--ink)" : "var(--muted)",
              borderBottom: `2px solid ${active ? "var(--rink-red)" : "transparent"}`,
            }}
          >
            {t.label}
          </Link>
        );
      })}
    </nav>
  );
}
