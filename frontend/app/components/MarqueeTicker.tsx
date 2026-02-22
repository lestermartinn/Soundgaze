interface MarqueeTickerProps {
  /** Text content — duplicated automatically for seamless loop */
  text?: string;
  /** Visual variant */
  variant?: "green" | "black";
  /** Animation speed */
  speed?: "slow" | "medium" | "fast";
  /** Rotation angle in degrees (positive = clockwise) */
  tilt?: number;
}

const DEFAULT_TEXT =
  "EXPLORE • DISCOVER • SOUNDGAZE • EXPLORE • DISCOVER • SOUNDGAZE •";

const SPEED_CLASS = {
  slow:   "animate-marquee-slow",
  medium: "animate-marquee-medium",
  fast:   "animate-marquee-fast",
} as const;

export default function MarqueeTicker({
  text = DEFAULT_TEXT,
  variant = "green",
  speed = "medium",
  tilt = 0,
}: MarqueeTickerProps) {
  const isGreen = variant === "green";

  const wrapperStyle = tilt !== 0 ? { transform: `rotate(${tilt}deg)` } : undefined;

  return (
    <div
      className={`w-full overflow-hidden whitespace-nowrap border-y-4 border-black py-1.5
                  ${isGreen ? "bg-spotify-green" : "bg-black"}`}
      style={wrapperStyle}
    >
      {/* Duplicate the text so the loop is seamless at exactly -50% */}
      <span
        className={`inline-block ${SPEED_CLASS[speed]}
                    font-black text-lg uppercase tracking-widest select-none
                    ${isGreen ? "text-black" : "text-white"}`}
      >
        {/* Repeated twice — CSS animation shifts by -50% for a perfect loop */}
        {text}&nbsp;&nbsp;&nbsp;{text}&nbsp;&nbsp;&nbsp;
      </span>
    </div>
  );
}
