"use client";

export default function VideoTable({ videos, sortBy, sortOrder, onSort }) {
  const columns = [
    { key: "index", label: "#", sortable: false, align: "left", width: "4%" },
    { key: "name", label: "VIDEO", sortable: false, align: "left", width: "32%" },
    { key: "category", label: "DANH MỤC", sortable: false, align: "left", width: "18%" },
    { key: "viral_probability", label: "VIRAL %", sortable: true, align: "right", width: "11%" },
    { key: "viral_velocity", label: "VELOCITY", sortable: true, align: "right", width: "11%" },
    { key: "views", label: "VIEWS", sortable: true, align: "right", width: "11%" },
    { key: "engagement_rate", label: "ENGAGE %", sortable: true, align: "right", width: "11%" },
    { key: "action", label: "", sortable: false, align: "center", width: "2%" },
  ];

  const formatNumber = (n) => {
    if (!n) return "0";
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
    if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
    return n.toLocaleString();
  };

  const getViralColor = (pct) => {
    if (pct === 0) return "rgba(255, 255, 255, 0.15)"; // Xám nhạt cho 0%
    if (pct >= 60) return "var(--accent-green)"; // Xanh lá mạ cho viral tốt
    if (pct >= 30) return "var(--text-primary)"; // Trắng/Xám nhat
    return "var(--text-muted)"; // Xám tối
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
                  className={`${col.sortable ? "cursor-pointer select-none" : ""} ${col.align === "right" ? "text-right" : ""}`}
                  onClick={() => col.sortable && onSort?.(col.key)}
                  style={{
                    width: col.width,
                    textAlign: col.align,
                  }}
                >
                  <div className={`flex items-center gap-1 ${col.align === "right" ? "justify-end w-full" : col.align === "center" ? "justify-center w-full" : ""}`}>
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
                  <td style={{ color: "var(--text-muted)", padding: "12px 12px", width: "40px" }}>
                    {i + 1}
                  </td>
                  <td style={{ padding: "12px 12px", maxWidth: "280px" }}>
                    <div className="flex flex-col">
                      <a href={video.link} target="_blank" rel="noopener noreferrer"
                        className="font-medium text-sm no-underline hover:underline"
                        style={{ color: "var(--text-primary)" }}>
                        {name}
                      </a>
                      {video.video_description && (
                        <span className="text-xs mt-1 font-medium" style={{ color: "#B3B3B3", lineHeight: "1.5" }}>
                          {video.video_description.substring(0, 60)}...
                        </span>
                      )}
                    </div>
                  </td>
                  <td style={{ padding: "12px 12px" }}>
                    <div className="flex flex-wrap gap-1">
                      {Array.isArray(video.category) ? video.category.map((cat, ci) => (
                        <span key={ci} className="badge badge-category whitespace-nowrap">{cat}</span>
                      )) : (typeof video.category === "string" ? video.category.split("|").map((cat, ci) => (
                        <span key={ci} className="badge badge-category whitespace-nowrap">{cat.trim()}</span>
                      )) : <span className="badge badge-category whitespace-nowrap">—</span>)}
                    </div>
                  </td>
                  <td style={{ padding: "12px 12px", width: columns[3].width }}>
                    <div className="flex items-center gap-2 justify-end w-full">
                      <div className="viral-bar hidden lg:block" style={{ width: "40px", background: "rgba(255, 255, 255, 0.05)" }}>
                        <div className="viral-bar-fill"
                          style={{
                            width: `${Math.min(video.viral_probability || 0, 100)}%`,
                            background: getViralColor(video.viral_probability || 0),
                          }}
                        />
                      </div>
                      <span className="text-sm font-semibold inline-block" style={{
                        color: getViralColor(video.viral_probability || 0),
                        fontVariantNumeric: "tabular-nums",
                        minWidth: "42px",
                        textAlign: "right"
                      }}>
                        {(video.viral_probability || 0).toFixed(1)}%
                      </span>
                    </div>
                  </td>
                  <td style={{ padding: "12px 12px", textAlign: "right", fontVariantNumeric: "tabular-nums", width: columns[4].width }}>
                    <span className="text-sm font-medium inline-block w-full text-right" style={{ color: "var(--text-primary)" }}>
                      {formatNumber(video.viral_velocity || 0)}
                    </span>
                  </td>
                  <td className="text-[15px] font-bold" style={{
                    padding: "12px 12px",
                    textAlign: "right",
                    fontVariantNumeric: "tabular-nums",
                    width: columns[5].width,
                    color: "var(--text-primary)"
                  }}>
                    <span className="inline-block w-full text-right">{formatNumber(video.views)}</span>
                  </td>
                  <td style={{ padding: "12px 12px", textAlign: "right", fontVariantNumeric: "tabular-nums", width: columns[6].width }}>
                    <span className="text-sm font-medium inline-block w-full text-right" style={{ color: (video.engagement_rate > 3 ? "var(--accent-green)" : "var(--text-muted)") }}>
                      {(video.engagement_rate || 0).toFixed(1)}%
                    </span>
                  </td>
                  <td style={{ padding: "12px 12px", textAlign: "center", minWidth: "110px", width: columns[7].width }}>
                    <a href={`/video/${video.video_id}`}
                      className="text-xs font-semibold px-3 py-1.5 rounded-lg no-underline transition-all inline-block whitespace-nowrap"
                      style={{
                        background: "rgba(220, 38, 38, 0.08)",
                        color: "var(--accent-primary)",
                        border: "1px solid rgba(220, 38, 38, 0.15)",
                      }}
                      onMouseEnter={(e) => {
                        e.target.style.background = "rgba(220, 38, 38, 0.2)";
                        e.target.style.borderColor = "rgba(220, 38, 38, 0.4)";
                        e.target.style.boxShadow = "0 0 12px rgba(220, 38, 38, 0.15)";
                      }}
                      onMouseLeave={(e) => {
                        e.target.style.background = "rgba(220, 38, 38, 0.08)";
                        e.target.style.borderColor = "rgba(220, 38, 38, 0.15)";
                        e.target.style.boxShadow = "none";
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
