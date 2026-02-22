"use client";

import { useEffect, useState } from "react";
import { useSession, signIn } from "next-auth/react";
import { useRouter } from "next/navigation";
import Waves from "./components/Waves";

// ---------------------------------------------------------------------------
// Feature callouts
// ---------------------------------------------------------------------------

const FEATURES = [
  { countTo: null, suffix: "UMAP", label: "3D Vector Space", delay: 0 },
  { countTo: null, suffix: "AI", label: "Gemini Powered", delay: 120 },
  { countTo: null, suffix: "↗", label: "Embedded Playback", delay: 240 },
  { countTo: 100, suffix: "K", label: "Songs Mapped", delay: 360 },
];

// ---------------------------------------------------------------------------
// Animated counter
// ---------------------------------------------------------------------------

function AnimatedStat({ countTo, suffix, delay }: { countTo: number | null; suffix: string; delay: number }) {
  const [value, setValue] = useState(0);

  useEffect(() => {
    if (countTo === null) return;
    const DURATION = 1400;
    let raf: number;
    let startTime: number | null = null;

    const timer = setTimeout(() => {
      function step(ts: number) {
        if (!startTime) startTime = ts;
        const progress = Math.min((ts - startTime) / DURATION, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        setValue(Math.round(eased * countTo!));
        if (progress < 1) raf = requestAnimationFrame(step);
      }
      raf = requestAnimationFrame(step);
    }, delay);

    return () => { clearTimeout(timer); cancelAnimationFrame(raf); };
  }, [countTo, delay]);

  if (countTo === null) {
    return <span className="font-black text-2xl text-white leading-none tracking-tight">{suffix}</span>;
  }


  return (
    <span className="font-black text-2xl text-white leading-none tracking-tight">
      {value}{suffix}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function LandingPage() {
  const { status } = useSession();
  const router = useRouter();
  const [transitioning, setTransitioning] = useState(false);

  const isAuthenticated = status === "authenticated";

  function handleContinue() {
    setTransitioning(true);
    setTimeout(() => router.push("/explore"), 350);
  }

  return (
    <div
      className="relative w-screen h-screen overflow-hidden flex flex-col"
      style={{ backgroundColor: "#080808" }}
    >
      {/* ── Fade-to-black transition overlay ── */}
      <div
        className="fixed inset-0 z-50 pointer-events-none"
        style={{
          backgroundColor: "#080808",
          opacity: transitioning ? 1 : 0,
          transition: "opacity 350ms ease-in-out",
        }}
      />
      {/* ── Diagonal background gradients ── */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: `
            radial-gradient(ellipse 60% 65% at 90% 15%, rgba(29,185,84,0.65) 0%, rgba(29,185,84,0.20) 48%, transparent 68%),
            radial-gradient(ellipse 58% 62% at 3% 92%, rgba(210,210,210,0.45) 0%, rgba(140,140,140,0.18) 52%, transparent 70%)
          `,
        }}
      />

      {/* ── Waves background ── */}
      <Waves
        lineColor="rgba(29, 185, 84, 0.45)"
        backgroundColor="transparent"
        waveSpeedX={0.0125}
        waveSpeedY={0.01}
        waveAmpX={40}
        waveAmpY={20}
        friction={0.9}
        tension={0.01}
        maxCursorMove={120}
        xGap={12}
        yGap={36}
        style={{ zIndex: 1 }}
      />

      {/* ── Main content ── */}
      <main className="relative z-10 flex-1 flex items-stretch px-6 md:px-10 lg:px-16 py-6 gap-8">

        {/* Left — Wordmark */}
        <div className="flex flex-col justify-center pb-64 pl-2 md:pl-6 flex-1 min-w-0">
          <span
            className="font-black uppercase text-white leading-none tracking-tight"
            style={{ fontSize: "clamp(2.5rem, 8vw, 7.5rem)" }}
          >
            SOUND
          </span>
          <span
            className="font-black uppercase text-white leading-none tracking-tight"
            style={{ fontSize: "clamp(2.5rem, 8vw, 7.5rem)", marginTop: "-0.05em" }}
          >
            GAZE
          </span>
          <p className="font-mono text-sm uppercase tracking-widest text-white/55 mt-6 pl-1 text-left">
            Your music universe — visualised in 3D
          </p>
        </div>

        {/* Right — CTA + features */}
        <div className="flex flex-col justify-center items-end pt-64 pr-2 md:pr-6 gap-5 w-full max-w-[44rem] shrink-0">

          <div className="flex flex-col items-center gap-3 w-full">
            {isAuthenticated ? (
              <button
                onClick={handleContinue}
                className="font-black text-sm uppercase tracking-widest px-8 py-4
                           border-2 transition-all hover:-translate-y-px active:translate-y-0"
                style={{
                  backgroundColor: "#1DB954",
                  color: "#000",
                  borderColor: "#1DB954",
                  boxShadow: "0 0 0 2px #000",
                }}
              >
                CONTINUE →
              </button>
            ) : (
              <button
                onClick={() => signIn("spotify", { callbackUrl: "/explore" })}
                disabled={status === "loading"}
                className="font-black text-sm uppercase tracking-widest px-8 py-4
                           border-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed
                           hover:-translate-y-px active:translate-y-0"
                style={{
                  backgroundColor: "#1DB954",
                  color: "#000",
                  borderColor: "#1DB954",
                  boxShadow: "0 0 0 2px #000",
                }}
              >
                {status === "loading" ? "Connecting..." : "CONNECT SPOTIFY →"}
              </button>
            )}

          </div>

          {/* Feature cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 w-full">
            {FEATURES.map(({ countTo, suffix, label, delay }) => (
              <div
                key={label}
                className="flex flex-col gap-2 p-3 lg:p-4 border transition-colors"
                style={{
                  borderColor: "rgba(29,185,84,0.40)",
                  backgroundColor: "rgba(0,0,0,0.45)",
                }}
              >
                <AnimatedStat countTo={countTo} suffix={suffix} delay={delay} />
                <span className="font-black text-xs uppercase tracking-normal text-white leading-snug">
                  {label}
                </span>
              </div>
            ))}
          </div>

        </div>
      </main>
    </div>
  );
}
