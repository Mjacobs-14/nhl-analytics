import type { Metadata } from "next";
import { Suspense } from "react";
import { AnalyticsFilters } from "@/components/analytics/AnalyticsFilters";
import { AthleticismChart } from "@/components/analytics/AthleticismChart";
import { CoachChangeChart } from "@/components/analytics/CoachChangeChart";
import { CoachStyleChart } from "@/components/analytics/CoachStyleChart";
import { QuadrantChart } from "@/components/analytics/QuadrantChart";
import { VegasFluChart } from "@/components/analytics/VegasFluChart";
import { XgHeatmap } from "@/components/analytics/XgHeatmap";
import {
  getAthleticism,
  getCoachChanges,
  getCoachStyle,
  getShotVolumeOutput,
  getShotVolumeSeasons,
  getVegasFlu,
  getXgGrid,
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

function SectionHeader({ title, note }: { title: string; note: string }) {
  return (
    <div className="mb-3">
      <h3 className="display text-lg">{title}</h3>
      <p className="text-sm mt-1" style={{ color: "var(--muted)" }}>
        {note}
      </p>
    </div>
  );
}

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
          Apply the sql/ views to the shared DB, then refresh.
        </p>
      </div>
    );
  }

  const requested = Number(params.season);
  const season = seasons.includes(requested) ? requested : seasons[0];
  const pos = params.pos === "F" || params.pos === "D" ? params.pos : undefined;

  const [allPoints, flu, xgCells, coachStyle, coachChanges, athleticism] =
    await Promise.all([
      getShotVolumeOutput(season),
      getVegasFlu(),
      getXgGrid(),
      getCoachStyle(season),
      getCoachChanges(),
      getAthleticism(season),
    ]);

  const points =
    pos === "D"
      ? allPoints.filter((p) => p.position === "D")
      : pos === "F"
        ? allPoints.filter((p) => p.position !== "D")
        : allPoints;
  const medianX = median(points.map((p) => p.sogPer60));
  const medianY = median(points.map((p) => p.ppg));

  const athletes =
    pos === "D"
      ? athleticism.filter((r) => r.position === "D")
      : pos === "F"
        ? athleticism.filter((r) => r.position !== "D")
        : athleticism;

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
        <SectionHeader
          title="Shot volume vs. output"
          note={`${formatSeason(season)} regular season · one dot per skater (min 20 GP) · midlines are the medians of the ${points.length} skaters shown`}
        />
        <QuadrantChart points={points} medianX={medianX} medianY={medianY} />
      </section>

      <section className="card p-5 mb-6">
        <SectionHeader
          title="Where goals actually come from"
          note="Goal probability by shot location, all unblocked on-net shots with a goalie in net since 2018 (676k) · pooled across seasons · 0° = head-on, shots beyond 90 ft excluded"
        />
        <XgHeatmap cells={xgCells} />
      </section>

      <hr className="blue-line mb-6" />

      <section className="card p-5 mb-6">
        <SectionHeader
          title="Coach fingerprints"
          note={`${formatSeason(season)} regular season · one dot per bench (min 20 GP behind it) · chance quality created vs. conceded, from the location-xG model above — down and right is where you want your guy`}
        />
        <CoachStyleChart rows={coachStyle} />
      </section>

      <section className="card p-5 mb-6">
        <SectionHeader
          title="The coaching-change experiment"
          note="Every mid-season change since 2018 with 10+ games on both sides — same roster, same season, so the swing is the closest thing to a causal coach signal"
        />
        <CoachChangeChart rows={coachChanges} />
      </section>

      <hr className="blue-line mb-6" />

      <section className="card p-5 mb-6">
        <SectionHeader
          title="Fast vs. relentless"
          note={`${formatSeason(season)} NHL Edge tracking (min 20 GP) · peak speed is a gift; burst count is a choice`}
        />
        <AthleticismChart rows={athletes} />
      </section>

      <section className="card p-5">
        <SectionHeader
          title="The Vegas Flu"
          note="Scoring at T-Mobile Arena vs. every other road game, all regular seasons since 2018 · min 5 Vegas + 20 other road games · VGK excluded — home teams can't catch the flu"
        />
        <VegasFluChart rows={flu} />
      </section>

      <p className="text-xs mt-4" style={{ color: "var(--faint)" }}>
        Backed by shot_events play-by-play (1.3M shot attempts since 2018) and the
        empirical xg_grid. Rush-vs-cycle splits arrive once the is_rush backfill runs.
      </p>
    </div>
  );
}
