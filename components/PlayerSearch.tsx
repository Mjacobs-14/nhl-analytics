"use client";

import { useEffect, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";

interface Hit {
  id: number;
  firstName: string | null;
  lastName: string | null;
  fullName: string;
  teamAbbrev: string | null;
  position: string | null;
  headshotUrl: string | null;
}

export function PlayerSearch() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Hit[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const boxRef = useRef<HTMLDivElement>(null);

  // debounced fetch
  useEffect(() => {
    const term = q.trim();
    if (term.length < 2) {
      setHits([]);
      return;
    }
    const ctl = new AbortController();
    const t = setTimeout(async () => {
      try {
        const res = await fetch(`/api/search?q=${encodeURIComponent(term)}`, { signal: ctl.signal });
        if (res.ok) {
          setHits(await res.json());
          setActive(0);
          setOpen(true);
        }
      } catch {
        /* aborted or offline — ignore */
      }
    }, 150);
    return () => {
      clearTimeout(t);
      ctl.abort();
    };
  }, [q]);

  // close on outside click
  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const go = (h: Hit) => {
    setOpen(false);
    setQ("");
    setHits([]);
    router.push(`/player/${h.id}`);
  };

  const onKey = (e: ReactKeyboardEvent<HTMLInputElement>) => {
    if (!open || hits.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, hits.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (hits[active]) go(hits[active]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <div ref={boxRef} style={{ position: "relative", marginLeft: "auto", width: "min(15rem, 40vw)" }}>
      <input
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onFocus={() => hits.length > 0 && setOpen(true)}
        onKeyDown={onKey}
        placeholder="Search any player…"
        aria-label="Search players"
        autoComplete="off"
        className="stat text-sm"
        style={{
          width: "100%",
          padding: "6px 11px",
          borderRadius: 8,
          border: "1px solid var(--chip-border, var(--chip-bg))",
          background: "var(--chip-bg)",
          color: "var(--ink)",
        }}
      />
      {open && hits.length > 0 && (
        <ul
          role="listbox"
          style={{
            position: "absolute",
            top: "calc(100% + 4px)",
            right: 0,
            left: 0,
            zIndex: 50,
            margin: 0,
            padding: 4,
            listStyle: "none",
            background: "var(--card-bg, var(--chip-bg))",
            border: "1px solid var(--chip-bg)",
            borderRadius: 10,
            boxShadow: "0 8px 28px rgba(0,0,0,.18)",
            maxHeight: "70vh",
            overflowY: "auto",
          }}
        >
          {hits.map((h, i) => (
            <li key={h.id} role="option" aria-selected={i === active}>
              <button
                type="button"
                onMouseEnter={() => setActive(i)}
                onClick={() => go(h)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  width: "100%",
                  padding: "6px 8px",
                  borderRadius: 7,
                  border: 0,
                  cursor: "pointer",
                  textAlign: "left",
                  background: i === active ? "var(--chip-bg)" : "transparent",
                  color: "var(--ink)",
                }}
              >
                {h.headshotUrl ? (
                  <Image
                    src={h.headshotUrl}
                    alt=""
                    width={26}
                    height={26}
                    className="rounded-full"
                    style={{ background: "var(--chip-bg)" }}
                  />
                ) : (
                  <span style={{ width: 26, height: 26 }} />
                )}
                <span className="font-medium text-sm">
                  {h.firstName && h.lastName ? `${h.firstName} ${h.lastName}` : h.fullName}
                </span>
                <span className="stat text-xs" style={{ marginLeft: "auto", color: "var(--muted)" }}>
                  {[h.teamAbbrev, h.position].filter(Boolean).join(" · ")}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
