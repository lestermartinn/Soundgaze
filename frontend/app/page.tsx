"use client";

import { useEffect, useState } from "react";
import { useSession, signIn } from "next-auth/react";
import { useRouter } from "next/navigation";
import Waves from "./components/Waves";

// ---------------------------------------------------------------------------
// Feature callouts
// ---------------------------------------------------------------------------

const FEATURES = [
  { countTo: 50,   suffix: "M+", label: "Tracks",     detail: "Mapped in 3D space",              delay: 0   },
  { countTo: 3,    suffix: "D",  label: "UMAP Space",  detail: "12-dim audio → 3D cluster",       delay: 120 },
  { countTo: null, suffix: "AI", label: "Context",     detail: "Gemini cultural descriptions",    delay: 240 },
  { countTo: 1,    suffix: "×",  label: "Click Save",  detail: "Save directly to your library",   delay: 360 },
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
      {value}<span style={{ color: "#1DB954" }}>{suffix}</span>
    </span>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function LandingPage() {
  const { status } = useSession();
  const router = useRouter();

  const isAuthenticated = status === "authenticated";

  return (
    <div
      className="relative w-screen h-screen overflow-hidden flex flex-col"
      style={{ backgroundColor: "#080808" }}
    >
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
        <div className="flex flex-col justify-center pb-[15vh] pl-2 md:pl-6 flex-1 min-w-0">
          <div className="flex items-start leading-none">
            <span
              className="font-black uppercase text-white leading-none tracking-tight"
              style={{ fontSize: "clamp(2.5rem, 8vw, 7.5rem)" }}
            >
              SOUND
            </span>
            <span
              className="shrink-0 ml-2 mt-1"
              style={{
                width: "clamp(4px, 0.45vw, 7px)",
                height: "clamp(2rem, 6.5vw, 6rem)",
                backgroundColor: "#1DB954",
              }}
            />
          </div>
          <span
            className="font-black uppercase text-white leading-none tracking-tight"
            style={{ fontSize: "clamp(2.5rem, 8vw, 7.5rem)", marginTop: "-0.05em" }}
          >
            GAZE
          </span>
          <p className="font-mono text-xs uppercase tracking-widest text-white/35 mt-4">
            Your music universe — visualised in 3D
          </p>
        </div>

        {/* Right — CTA + features */}
        <div className="flex flex-col justify-center items-center pt-[15vh] pr-2 md:pr-6 gap-5 w-full max-w-[44rem] shrink-0">

          <div className="flex flex-col items-center gap-3 w-full">
            {isAuthenticated ? (
              <button
                onClick={() => router.push("/explore")}
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

            <span className="font-mono text-xs tracking-widest text-white/30 uppercase">
              Free account works · No credit card
            </span>
          </div>

          {/* Feature cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 w-full">
            {FEATURES.map(({ countTo, suffix, label, detail, delay }) => (
              <div
                key={label}
                className="flex flex-col gap-2 p-3 lg:p-4 border min-h-[90px] transition-colors"
                style={{
                  borderColor: "rgba(29,185,84,0.40)",
                  backgroundColor: "rgba(0,0,0,0.45)",
                }}
              >
                <AnimatedStat countTo={countTo} suffix={suffix} delay={delay} />
                <span className="font-black text-xs uppercase tracking-normal text-white leading-snug">
                  {label}
                </span>
                <span className="font-mono text-xs text-white/40 leading-snug break-words">
                  {detail}
                </span>
              </div>
            ))}
          </div>

        </div>
      </main>
    </div>
  );
}
