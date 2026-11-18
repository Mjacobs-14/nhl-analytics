import type { Metadata } from "next";
import { MatchupLab } from "@/components/matchup/MatchupLab";
import { getMatchupData } from "@/lib/matchup";

export const dynamic = "force-dynamic";

// Prototype/handoff tool — keep it off the public board (matches /analytics).
export const metadata: Metadata = {
  title: "Matchup Lab — Is He Cooked?",
  robots: { index: false, follow: false },
};

export default async function MatchupPage() {
  const data = await getMatchupData();

  if (data.st.length === 0) {
    return (
      <div className="card p-8 text-center max-w-xl mx-auto mt-10">
        <h2 className="display text-2xl mb-2">No matchup views yet</h2>
        <p style={{ color: "var(--muted)" }}>
          Apply sql/032 and sql/033 to the shared DB, then refresh.
        </p>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4">
        <p className="eyebrow mb-1">Two-team style-clash preview · not on the public board</p>
        <h2 className="display text-2xl">Matchup Lab</h2>
        <p className="text-sm mt-1" style={{ color: "var(--muted)" }}>
          A style-clash preview for any two teams: even-strength shot diets and concession profiles
          (road vs home), a separate power-play-vs-penalty-kill term, the transition (rush) clash, and
          the goalie&rsquo;s danger-band save % — all priced in expected goals. Override either goalie
          for a confirmed starter.
        </p>
      </div>
      <MatchupLab data={data} />
    </div>
  );
}
