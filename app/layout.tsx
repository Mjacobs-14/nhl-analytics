import type { Metadata } from "next";
import Link from "next/link";
import { Barlow, Barlow_Condensed, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";

const display = Barlow_Condensed({
  variable: "--font-display",
  weight: ["500", "600", "700"],
  subsets: ["latin"],
});
const body = Barlow({
  variable: "--font-body",
  weight: ["400", "500", "600"],
  subsets: ["latin"],
});
const mono = IBM_Plex_Mono({
  variable: "--font-mono",
  weight: ["400", "500", "600"],
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Is He Cooked? — NHL decline detector",
  description:
    "A fun analytics project that scores NHL players on a fresh-to-cooked gauge from public NHL data.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`${display.variable} ${body.variable} ${mono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <header className="px-6 pt-6 pb-3 max-w-5xl w-full mx-auto">
          <Link href="/" className="no-underline text-inherit">
            <h1 className="display text-4xl sm:text-5xl">
              Is He <span style={{ color: "var(--rink-red)" }}>Cooked?</span>
            </h1>
          </Link>
          <p className="text-sm mt-1" style={{ color: "var(--muted)" }}>
            NHL player decline detection. For arguments in the group chat, not
            for wagering.
          </p>
        </header>
        <hr className="center-line max-w-5xl w-full mx-auto" />
        <main className="px-6 py-6 max-w-5xl w-full mx-auto flex-1">
          {children}
        </main>
        <footer
          className="px-6 py-4 max-w-5xl w-full mx-auto text-xs"
          style={{ color: "var(--faint)" }}
        >
          Data: public NHL API · Scores recompute with <span className="stat">npm run cook</span> ·
          Tune the model in <span className="stat">lib/cooked/config.ts</span>
        </footer>
      </body>
    </html>
  );
}
