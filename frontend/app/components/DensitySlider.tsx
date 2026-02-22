"use client";

interface DensitySliderProps {
  value: number;
  onChange: (value: number) => void;
}

export default function DensitySlider({ value, onChange }: DensitySliderProps) {
  return (
    <div
      className="flex flex-col items-center gap-2 px-4 py-5
                 border-4 border-black"
      style={{ backgroundColor: "#080808" }}
    >
      {/* Section label */}
      <span className="font-black text-xs uppercase tracking-widest text-white">
        Density
      </span>

      <div className="w-px h-3 bg-white/20" />

      {/* Top label */}
      <span className="font-mono text-xs uppercase tracking-widest text-white/50">
        High
      </span>

      {/* Vertical slider */}
      <input
        type="range"
        min={1}
        max={100}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="cursor-pointer accent-[#1DB954]"
        style={{
          writingMode: "vertical-lr" as React.CSSProperties["writingMode"],
          direction: "rtl",
          height: "220px",
          width: "6px",
          appearance: "slider-vertical" as React.CSSProperties["appearance"],
        }}
      />

      {/* Bottom label */}
      <span className="font-mono text-xs uppercase tracking-widest text-white/50">
        Low
      </span>

      <div className="w-px h-3 bg-white/20" />

      {/* Live value */}
      <span className="font-mono text-xs tabular-nums text-spotify-green font-bold">
        {value}
      </span>
    </div>
  );
}
