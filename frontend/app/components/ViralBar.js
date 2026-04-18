"use client";

export default function ViralBar({ probability }) {
  const pct = Math.min(Math.max(probability || 0, 0), 100);
  let color;
  if (pct >= 70) color = "var(--accent-red)";
  else if (pct >= 40) color = "var(--accent-yellow)";
  else color = "var(--accent-green)";

  let label;
  if (pct >= 80) label = "🔥 Đột phá";
  else if (pct >= 60) label = "🚀 Cao";
  else if (pct >= 35) label = "📈 Trung bình";
  else label = "💤 Thấp";

  return (
    <div className="flex items-center gap-3">
      <div className="viral-bar flex-1">
        <div
          className="viral-bar-fill"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <span className="text-xs font-semibold whitespace-nowrap" style={{ color, minWidth: "60px" }}>
        {pct.toFixed(1)}%
      </span>
      <span className="text-xs hidden sm:inline" style={{ color: "var(--text-muted)", minWidth: "80px" }}>
        {label}
      </span>
    </div>
  );
}
