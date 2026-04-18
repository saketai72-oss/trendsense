"use client";

export default function StatCard({ icon, label, value, delta, color = "var(--accent-primary)", delay = 0 }) {
  return (
    <div
      className={`glass-card neon-border p-5 opacity-0 animate-fadeInUp`}
      style={{ animationDelay: `${delay}ms`, animationFillMode: "forwards" }}
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-2xl">{icon}</span>
        {delta !== undefined && (
          <span
            className="text-xs font-semibold px-2 py-0.5 rounded-full"
            style={{
              background: delta >= 0 ? "rgba(16, 185, 129, 0.15)" : "rgba(239, 68, 68, 0.15)",
              color: delta >= 0 ? "var(--accent-green)" : "var(--accent-red)",
            }}
          >
            {delta >= 0 ? "↑" : "↓"} {Math.abs(delta)}%
          </span>
        )}
      </div>
      <div className="text-2xl font-bold mb-1" style={{ color }}>{value}</div>
      <div className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>{label}</div>
    </div>
  );
}
