"use client";

import { useEffect } from "react";
import { useSession, signIn } from "next-auth/react";
import { useRouter } from "next/navigation";
import MarqueeTicker from "../components/MarqueeTicker";

// ---------------------------------------------------------------------------
// Feature callouts
// ---------------------------------------------------------------------------

const FEATURES = [
  { label: "50M+ Tracks",        detail: "Mapped in 3D space"          },
  { label: "UMAP Clustering",    detail: "Songs grouped by similarity"  },
  { label: "AI Context",         detail: "Gemini cultural descriptions" },
  { label: "Spotify Native",     detail: "Save directly to your library"},
];

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function LandingPage() {
  const { status } = useSession();
  const router = useRouter();

  // Already authenticated — skip straight to the explorer
  useEffect(() => {
    if (status === "authenticated") router.replace("/");
  }, [status, router]);

  return (
    <div className="relative w-screen h-screen bg-near-black overflow-hidden flex flex-col">

      {/* ── Top marquee ── */}
      <MarqueeTicker
        text="SOUNDSCAPE • MUSIC UNIVERSE EXPLORER • DISCOVER YOUR SOUND •"
        variant="green"
        speed="medium"
        tilt={0}
      />

      {/* ── Hero ── */}
      <main className="flex-1 flex flex-col items-center justify-center px-6 gap-10">

        {/* Wordmark block */}
        <div className="flex flex-col items-start gap-1 select-none">
          <div className="flex items-center gap-4">
            <span
              className="font-black uppercase leading-none tracking-tighter text-white"
              style={{ fontSize: "clamp(4rem, 12vw, 9rem)" }}
            >
              Sound
            </span>
            {/* Green accent bar */}
            <span
              className="bg-spotify-green border-4 border-black self-stretch"
              style={{ width: "clamp(14px, 2vw, 28px)" }}
            />
          </div>
          <span
            className="font-black uppercase leading-none tracking-tighter text-white"
            style={{ fontSize: "clamp(4rem, 12vw, 9rem)" }}
          >
            Scape
          </span>
          <p className="font-mono font-bold text-sm uppercase tracking-widest text-white/40 mt-2">
            Your music universe — visualised in 3D
          </p>
        </div>

        {/* CTA */}
        <div className="flex flex-col items-center gap-3">
          <button
            onClick={() => signIn("spotify", { callbackUrl: "/" })}
            disabled={status === "loading"}
            className="font-black text-sm uppercase tracking-widest px-8 py-4
                       border-4 border-black
                       shadow-[6px_6px_0px_0px_#000]
                       hover:shadow-[8px_8px_0px_0px_#000] hover:-translate-y-px
                       active:shadow-none active:translate-y-0
                       transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            style={{ backgroundColor: "#1DB954", color: "#000" }}
          >
            {status === "loading" ? "Connecting..." : "Connect Spotify →"}
          </button>
          <span className="font-mono text-xs text-white/30 uppercase tracking-widest">
            Free account works · No credit card
          </span>

          {/* Dev-only bypass — automatically inactive in production builds */}
          {process.env.NODE_ENV === "development" && (
            <button
              onClick={() => router.push("/")}
              className="font-mono text-xs text-white/20 hover:text-white/50
                         underline underline-offset-4 transition-colors mt-2"
            >
              [dev] skip auth →
            </button>
          )}
        </div>

        {/* Feature grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 w-full max-w-2xl">
          {FEATURES.map(({ label, detail }) => (
            <div
              key={label}
              className="border-2 border-white/10 p-3 flex flex-col gap-1
                         hover:border-spotify-green transition-colors"
            >
              <span className="font-black text-xs uppercase tracking-widest text-white">
                {label}
              </span>
              <span className="font-mono text-xs text-white/40 leading-snug">
                {detail}
              </span>
            </div>
          ))}
        </div>

      </main>

      {/* ── Bottom marquee ── */}
      <MarqueeTicker
        text="EXPLORE • DISCOVER • CONNECT • VISUALISE • EXPLORE • DISCOVER • CONNECT •"
        variant="black"
        speed="fast"
        tilt={0}
      />

    </div>
  );
}
