import type { Metadata } from "next";
import { Suspense } from "react";
import { AnalyticsFilters } from "@/components/analytics/AnalyticsFilters";
import { QuadrantChart } from "@/components/analytics/QuadrantChart";
import { VegasFluChart } from "@/components/analytics/VegasFluChart";
import {
  getShotVolumeOutput,
  getShotVolumeSeasons,
  getVegasFlu,
  median,
} from "@/lib/analytics";
import { formatSeason } from "@/lib/zones";

export const dynamic = "force-dynamic";

// Not public-facing yet — keep crawlers out even after the app goes live,
// until this section graduates on purpose.
export const metadata: Metadata = {
  title: "Analytics — Is He Cooked?",
  robots: { index: false, follow: false },
};

export default async function AnalyticsPage({
  searchParams,
}: {
  searchParams: Promise<{ season?: string; pos?: string }>;
}) {
  const params = await searchParams;
  const seasons = await getShotVolumeSeasons();

  if (seasons.length === 0) {
    return (
      <div className="card p-8 text-center max-w-xl mx-auto mt-10">
        <h2 className="display text-2xl mb-2">No analytics views yet</h2>
        <p style={{ color: "var(--muted)" }}>
          Apply sql/014 and sql/015 to the shared DB, then refresh.
        </p>
      </div>
    );
  }

  const requested = Number(params.season);
  const season = seasons.includes(requested) ? requested : seasons[0];
  const pos = params.pos === "F" || params.pos === "D" ? params.pos : undefined;

  const [allPoints, flu] = await Promise.all([
    getShotVolumeOutput(season),
    getVegasFlu(),
  ]);
  const points =
    pos === "D"
      ? allPoints.filter((p) => p.position === "D")
      : pos === "F"
        ? allPoints.filter((p) => p.position !== "D")
        : allPoints;
  const medianX = median(points.map((p) => p.sogPer60));
  const medianY = median(points.map((p) => p.ppg));

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3 mb-4">
        <div>
          <p className="eyebrow mb-1">League-wide views · not on the public board</p>
          <h2 className="display text-2xl">Analytics</h2>
        </div>
        <Suspense>
          <AnalyticsFilters seasons={seasons} season={season} />
        </Suspense>
      </div>

      <section className="card p-5 mb-6">
        <div className="mb-3">
          <h3 className="display text-lg">Shot volume vs. output</h3>
          <p className="text-sm mt-1" style={{ color: "var(--muted)" }}>
            {formatSeason(season)} regular season · one dot per skater (min 20 GP) ·
            midlines are the medians of the {points.length} skaters shown
          </p>
        </div>
        <QuadrantChart points={points} medianX={medianX} medianY={medianY} />
      </section>

      <hr className="blue-line mb-6" />

      <section className="card p-5">
        <div className="mb-3">
          <h3 className="display text-lg">The Vegas Flu</h3>
          <p className="text-sm mt-1" style={{ color: "var(--muted)" }}>
            Scoring at T-Mobile Arena vs. every other road game, all regular seasons
            since 2018 · min 5 Vegas + 20 other road games · VGK excluded — home
            teams can&rsquo;t catch the flu
          </p>
        </div>
        <VegasFluChart rows={flu} />
      </section>

      <p className="text-xs mt-4" style={{ color: "var(--faint)" }}>
        Backed by shot_events play-by-play (964k shot attempts since 2018). Coach-impact
        views land here once the coach backfill completes.
      </p>
    </div>
  );
}
