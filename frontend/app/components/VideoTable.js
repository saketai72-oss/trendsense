"use client";

export default function VideoTable({ videos, sortBy, sortOrder, onSort }) {
  const columns = [
    { key: "index", label: "#", sortable: false },
    { key: "name", label: "VIDEO", sortable: false },
    { key: "category", label: "DANH MỤC", sortable: false },
    { key: "viral_probability", label: "VIRAL %", sortable: true },
    { key: "viral_velocity", label: "VELOCITY", sortable: true },
    { key: "views", label: "VIEWS", sortable: true },
    { key: "engagement_rate", label: "ENGAGE %", sortable: true },
    { key: "action", label: "", sortable: false },
  ];

  const formatNumber = (n) => {
    if (!n) return "0";
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
    if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
    return n.toLocaleString();
  };

  const getViralColor = (pct) => {
    if (pct >= 70) return "var(--accent-red)";
    if (pct >= 40) return "var(--accent-yellow)";
    return "var(--accent-green)";
  };

  return (
    <div className="glass-card overflow-hidden w-full">
      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={col.sortable ? "cursor-pointer select-none" : ""}
                  onClick={() => col.sortable && onSort?.(col.key)}
                >
                  <div className="flex items-center gap-1">
                    {col.label}
                    {col.sortable && sortBy === col.key && (
                      <span className="text-xs">{sortOrder === "asc" ? "↑" : "↓"}</span>
                    )}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {videos.map((video, i) => {
              const name = video.caption && video.caption.length > 3
                ? video.caption.substring(0, 45) + "..."
                : `ID: ${(video.video_id || "").substring(0, 12)}...`;

              return (
                <tr key={video.video_id || i}>
                  <td style={{ color: "var(--text-muted)" }}>{i + 1}</td>
                  <td>
                    <div className="flex flex-col">
                      <a href={video.link} target="_blank" rel="noopener noreferrer"
                        className="font-medium text-sm no-underline hover:underline"
                        style={{ color: "var(--text-primary)" }}>
                        {name}
                      </a>
                      {video.video_description && (
                        <span className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
                          {video.video_description.substring(0, 60)}...
                        </span>
                      )}
                    </div>
                  </td>
                  <td>
                    <div className="flex flex-wrap gap-1">
                      {(video.category || "—").split("|").map((cat, ci) => (
                        <span key={ci} className="badge badge-category">{cat.trim()}</span>
                      ))}
                    </div>
                  </td>
                  <td>
                    <div className="flex items-center gap-2">
                      <div className="viral-bar" style={{ width: "60px" }}>
                        <div className="viral-bar-fill"
                          style={{
                            width: `${Math.min(video.viral_probability || 0, 100)}%`,
                            background: getViralColor(video.viral_probability || 0),
                          }}
                        />
                      </div>
                      <span className="text-sm font-semibold" style={{ color: getViralColor(video.viral_probability || 0) }}>
                        {(video.viral_probability || 0).toFixed(1)}%
                      </span>
                    </div>
                  </td>
                  <td>
                    <span className="text-sm font-medium" style={{ color: "var(--accent-cyan)" }}>
                      {(video.viral_velocity || 0).toFixed(1)}
                    </span>
                  </td>
                  <td className="font-medium text-sm">{formatNumber(video.views)}</td>
                  <td>
                    <span className="text-sm" style={{ color: "var(--accent-blue)" }}>
                      {(video.engagement_rate || 0).toFixed(1)}%
                    </span>
                  </td>
                  <td>
                    <a href={`/video/${video.video_id}`}
                      className="text-xs font-medium px-3 py-1.5 rounded-lg no-underline transition-all"
                      style={{
                        background: "rgba(124, 58, 237, 0.1)",
                        color: "var(--accent-primary)",
                        border: "1px solid rgba(124, 58, 237, 0.2)",
                      }}
                      onMouseEnter={(e) => {
                        e.target.style.background = "rgba(124, 58, 237, 0.25)";
                      }}
                      onMouseLeave={(e) => {
                        e.target.style.background = "rgba(124, 58, 237, 0.1)";
                      }}>
                      Chi tiết →
                    </a>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
