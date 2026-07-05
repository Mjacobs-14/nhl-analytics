"use client";

import { useRouter, useSearchParams } from "next/navigation";

export function Filters({ teams }: { teams: Array<{ abbrev: string; name: string }> }) {
  const router = useRouter();
  const params = useSearchParams();

  function update(key: string, value: string) {
    const next = new URLSearchParams(params.toString());
    if (value) next.set(key, value);
    else next.delete(key);
    router.replace(`/?${next.toString()}`);
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <input
        type="search"
        className="control w-52"
        placeholder="Search players"
        aria-label="Search players"
        defaultValue={params.get("q") ?? ""}
        onChange={(e) => update("q", e.target.value)}
      />
      <select
        className="control"
        aria-label="Filter by team"
        value={params.get("team") ?? ""}
        onChange={(e) => update("team", e.target.value)}
      >
        <option value="">All teams</option>
        {teams.map((t) => (
          <option key={t.abbrev} value={t.abbrev}>
            {t.abbrev} — {t.name}
          </option>
        ))}
      </select>
      <select
        className="control"
        aria-label="Filter by position"
        value={params.get("pos") ?? ""}
        onChange={(e) => update("pos", e.target.value)}
      >
        <option value="">All skaters</option>
        <option value="F">Forwards</option>
        <option value="D">Defensemen</option>
      </select>
      <select
        className="control"
        aria-label="Sort order"
        value={params.get("sort") ?? "cooked"}
        onChange={(e) => update("sort", e.target.value)}
      >
        <option value="cooked">Most cooked first</option>
        <option value="fresh">Freshest first</option>
      </select>
    </div>
  );
}
