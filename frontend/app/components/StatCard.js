"use client";

export default function StatCard({ icon, label, value, delta, color = "var(--accent-primary)", delay = 0 }) {
  return (
    <div
      className={`glass-card neon-border px-6 py-4 opacity-0 animate-fadeInUp`}
      style={{
        animationDelay: `${delay}ms`,
        animationFillMode: "forwards",
        boxShadow: `0 8px 32px ${color}15`, // Subtle colored glow based on the stat's primary color
      }}
    >
      <div className="flex items-center justify-between mb-4">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center text-xl"
            style={{
              background: `linear-gradient(135deg, ${color}20, ${color}05)`,
              color: color,
              border: `1px solid ${color}30`
            }}>
          {icon}
        </div>
        {delta !== undefined && (
          <span
            className="text-xs font-bold px-2.5 py-1 rounded-full"
            style={{
              background: delta >= 0 ? "rgba(16, 185, 129, 0.15)" : "rgba(239, 68, 68, 0.15)",
              color: delta >= 0 ? "var(--accent-green)" : "var(--accent-red)",
            }}
          >
            {delta >= 0 ? "↑" : "↓"} {Math.abs(delta)}%
          </span>
        )}
      </div>
      <div className="text-3xl font-black mb-1.5 tracking-tight" style={{ color, textShadow: `0 0 20px ${color}40` }}>
        {value}
      </div>
      <div className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--text-muted)", opacity: 0.8 }}>
        {label}
      </div>
    </div>
  );
}
