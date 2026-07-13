"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { formatSeason } from "@/lib/zones";

export function AnalyticsFilters({ seasons, season }: { seasons: number[]; season: number }) {
  const router = useRouter();
  const params = useSearchParams();

  function update(key: string, value: string) {
    const next = new URLSearchParams(params.toString());
    if (value) next.set(key, value);
    else next.delete(key);
    router.replace(`/analytics?${next.toString()}`);
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <select
        className="control"
        aria-label="Season"
        value={String(season)}
        onChange={(e) => update("season", e.target.value)}
      >
        {seasons.map((s) => (
          <option key={s} value={s}>
            {formatSeason(s)}
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
    </div>
  );
}
