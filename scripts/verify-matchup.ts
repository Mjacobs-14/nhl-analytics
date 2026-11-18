import { getMatchupDataUncached } from "@/lib/matchup";
import { direction, pickGk, seasonsIn, teamsIn } from "@/lib/matchup-compute";
import { client } from "@/db";

// Golden values from running Matt's v3 viz logic against its embedded snapshot.
const GOLD = {
  dalTotal: 2.5786, dalEv: 1.9134, dalPp: 0.6652,
  vgkTotal: 2.8076, vgkEv: 2.0844, vgkPp: 0.7231,
  gkA: "Jake Oettinger", gkB: "Akira Schmid",
};

function chk(label: string, got: number, want: number, tol = 0.02) {
  const ok = Math.abs(got - want) <= tol;
  console.log(`${ok ? "PASS" : "FAIL"}  ${label.padEnd(18)} got ${got.toFixed(4)}  want ${want.toFixed(4)}`);
  return ok;
}

async function main() {
  const D = await getMatchupDataUncached();
  const s = "20252026";
  console.log("seasons:", seasonsIn(D).join(", "));
  console.log("teams(2025-26) count:", teamsIn(D, s).length);

  const gkB = pickGk(D, s, "VGK", null);
  const gkA = pickGk(D, s, "DAL", null);
  const ab = direction(D, s, "DAL", "road", "VGK", "home", gkB, true);
  const ba = direction(D, s, "VGK", "home", "DAL", "road", gkA, true);

  let all = true;
  all = chk("DAL total", ab.xg, GOLD.dalTotal) && all;
  all = chk("DAL EV", ab.ev.xg, GOLD.dalEv) && all;
  all = chk("DAL PP", ab.pp.xg, GOLD.dalPp) && all;
  all = chk("VGK total", ba.xg, GOLD.vgkTotal) && all;
  all = chk("VGK EV", ba.ev.xg, GOLD.vgkEv) && all;
  all = chk("VGK PP", ba.pp.xg, GOLD.vgkPp) && all;
  const gkOk = gkA?.n === GOLD.gkA && gkB?.n === GOLD.gkB;
  console.log(`${gkOk ? "PASS" : "FAIL"}  default goalies    gkA=${gkA?.n} gkB=${gkB?.n}`);
  all = gkOk && all;

  console.log(all ? "\n✅ ALL GOLDEN CHECKS PASS" : "\n❌ SOME CHECKS FAILED");
  await client.end();
  process.exit(all ? 0 : 1);
}
main();
