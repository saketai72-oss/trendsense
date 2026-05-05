"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import { useAuth } from "../lib/AuthContext";
import { getMyVideos, deleteMyVideo } from "../lib/api";

const STATUS_MAP = {
  completed: { label: "Hoàn thành", color: "var(--accent-green)", bg: "rgba(52,211,153,0.12)" },
  analyzing: { label: "Đang phân tích", color: "var(--accent-yellow)", bg: "rgba(245,158,11,0.12)" },
  downloading: { label: "Đang tải", color: "var(--accent-blue)", bg: "rgba(59,130,246,0.12)" },
  summarizing: { label: "Đang tổng hợp", color: "var(--accent-cyan)", bg: "rgba(6,182,212,0.12)" },
  pending: { label: "Chờ xử lý", color: "var(--text-muted)", bg: "rgba(107,114,128,0.12)" },
  user_pending: { label: "Chờ xử lý", color: "var(--text-muted)", bg: "rgba(107,114,128,0.12)" },
  failed: { label: "Thất bại", color: "var(--accent-red)", bg: "rgba(239,68,68,0.12)" },
};

function fmtDate(d) {
  if (!d) return "—";
  return new Date(d).toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function ScoreCircle({ value, size = 64 }) {
  if (value == null) return null;
  const pct = Math.round(value * 100);
  const r = (size - 8) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ - (pct / 100) * circ;
  let color = "var(--accent-red)";
  if (pct >= 70) color = "var(--accent-green)";
  else if (pct >= 40) color = "var(--accent-yellow)";
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="5" />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth="5"
          strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round" />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-base font-bold" style={{ color }}>{pct}</span>
        <span className="text-[8px]" style={{ color: "var(--text-muted)" }}>%</span>
      </div>
    </div>
  );
}

function Bar({ label, pct, color }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[11px] w-24 shrink-0 truncate" style={{ color: "var(--text-muted)" }}>{label}</span>
      <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.06)" }}>
        <div className="h-full rounded-full" style={{ width: `${Math.min(pct, 100)}%`, background: color }} />
      </div>
      <span className="text-[11px] font-mono w-8 text-right" style={{ color: "var(--text-secondary)" }}>{Math.round(pct)}%</span>
    </div>
  );
}

/* ─── Single Analysis Card ─── */
function AnalysisCard({ v, onDelete }) {
  const [expanded, setExpanded] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const status = STATUS_MAP[v.ai_status] || STATUS_MAP.pending;
  const ti = v.trend_insights;
  const breakdown = ti?.breakdown || {};
  const scorePct = v.trend_alignment_score != null ? Math.round(v.trend_alignment_score) : null;

  const handleDelete = async (e) => {
    e.stopPropagation();
    if (!confirm("Bạn có chắc muốn xóa phân tích này?")) return;
    setDeleting(true);
    try {
      await deleteMyVideo(v.video_id);
      onDelete(v.video_id);
    } catch (err) {
      alert("Xóa thất bại: " + (err.message || "Lỗi không xác định"));
      setDeleting(false);
    }
  };

  return (
    <div className="rounded-xl overflow-hidden" style={{ background: "var(--bg-card)", border: "1px solid var(--border-color)" }}>

      {/* ── Header row ── */}
      <div className="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4">
        {/* Thumbnail */}
        {v.video_url ? (
          <video src={v.video_url} muted preload="metadata"
            className="w-full sm:w-28 h-16 sm:h-16 object-cover rounded-lg shrink-0 bg-black cursor-pointer"
            onClick={() => setExpanded(!expanded)} />
        ) : (
          <div className="w-full sm:w-28 h-16 sm:h-16 rounded-lg shrink-0 flex items-center justify-center text-2xl cursor-pointer"
            style={{ background: "rgba(255,255,255,0.04)" }} onClick={() => setExpanded(!expanded)}>🎬</div>
        )}

        {/* Info */}
        <button onClick={() => setExpanded(!expanded)}
          className="flex-1 min-w-0 text-left cursor-pointer bg-transparent border-none p-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className="px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider"
              style={{ background: status.bg, color: status.color }}>{status.label}</span>
            {v.category?.length > 0 && v.category.slice(0, 2).map((c, i) => (
              <span key={i} className="px-2 py-0.5 rounded-md text-[10px] font-medium"
                style={{ background: "rgba(255,255,255,0.05)", color: "var(--text-muted)" }}>{c}</span>
            ))}
          </div>
          <p className="text-sm font-medium truncate max-w-lg" style={{ color: "var(--text-primary)" }}>
            {v.caption || v.video_description || v.video_id}
          </p>
          <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
            {fmtDate(v.analyzed_at || v.scrape_date)}
            {v.video_duration && <><span className="mx-1.5">·</span>{Math.round(v.video_duration)}s</>}
            <span className="mx-1.5">·</span>
            <span className="font-mono text-[10px]">{v.video_id}</span>
          </p>
        </button>

        {/* Scores + actions */}
        <div className="flex items-center gap-3 shrink-0">
          {scorePct != null && (
            <div className="text-center">
              <ScoreCircle value={v.trend_alignment_score / 100} />
              <span className="text-[9px] block mt-0.5" style={{ color: "var(--text-muted)" }}>Trend</span>
            </div>
          )}
          {v.positive_score != null && (
            <div className="text-center">
              <ScoreCircle value={v.positive_score / 100} />
              <span className="text-[9px] block mt-0.5" style={{ color: "var(--text-muted)" }}>Positive</span>
            </div>
          )}

          {/* Expand toggle */}
          <button onClick={() => setExpanded(!expanded)}
            className="w-8 h-8 rounded-lg flex items-center justify-center cursor-pointer transition-colors"
            style={{ background: "rgba(255,255,255,0.04)", border: "none", color: "var(--text-muted)" }}
            onMouseEnter={(e) => e.currentTarget.style.background = "rgba(255,255,255,0.08)"}
            onMouseLeave={(e) => e.currentTarget.style.background = "rgba(255,255,255,0.04)"}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
              style={{ transform: expanded ? "rotate(180deg)" : "none", transition: "transform 0.2s" }}>
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </button>

          {/* Delete */}
          <button onClick={handleDelete} disabled={deleting}
            className="w-8 h-8 rounded-lg flex items-center justify-center cursor-pointer transition-colors disabled:opacity-40"
            style={{ background: "rgba(239,68,68,0.08)", border: "none", color: "var(--accent-red)" }}
            onMouseEnter={(e) => e.currentTarget.style.background = "rgba(239,68,68,0.15)"}
            onMouseLeave={(e) => e.currentTarget.style.background = "rgba(239,68,68,0.08)"}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="3 6 5 6 21 6" /><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
            </svg>
          </button>
        </div>
      </div>

      {/* ── Expanded details ── */}
      {expanded && (
        <div className="px-4 sm:px-5 pb-5 border-t" style={{ borderColor: "rgba(255,255,255,0.06)" }}>

          {/* Video player */}
          {v.video_url && (
            <div className="mt-4 mb-5">
              <video src={v.video_url} controls preload="metadata"
                className="w-full max-w-lg rounded-xl bg-black" style={{ maxHeight: 360 }} />
            </div>
          )}

          {/* Metric cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
            {v.video_duration != null && (
              <div className="p-3 rounded-xl text-center" style={{ background: "rgba(255,255,255,0.03)" }}>
                <span className="text-xl font-bold" style={{ color: "var(--accent-cyan)" }}>{Math.round(v.video_duration)}s</span>
                <span className="text-[10px] block mt-0.5" style={{ color: "var(--text-muted)" }}>Thời lượng</span>
              </div>
            )}
            {v.video_orientation && (
              <div className="p-3 rounded-xl text-center" style={{ background: "rgba(255,255,255,0.03)" }}>
                <span className="text-xl font-bold" style={{ color: "var(--accent-pink)" }}>{v.video_orientation}</span>
                <span className="text-[10px] block mt-0.5" style={{ color: "var(--text-muted)" }}>Hướng video</span>
              </div>
            )}
            {v.scene_cut_count != null && (
              <div className="p-3 rounded-xl text-center" style={{ background: "rgba(255,255,255,0.03)" }}>
                <span className="text-xl font-bold" style={{ color: "var(--accent-yellow)" }}>{v.scene_cut_count}</span>
                <span className="text-[10px] block mt-0.5" style={{ color: "var(--text-muted)" }}>Cắt cảnh</span>
              </div>
            )}
            <div className="p-3 rounded-xl text-center" style={{ background: "rgba(255,255,255,0.03)" }}>
              <span className="text-xl font-bold" style={{ color: "var(--accent-green)" }}>
                {v.video_sentiment || "—"}
              </span>
              <span className="text-[10px] block mt-0.5" style={{ color: "var(--text-muted)" }}>Cảm xúc</span>
            </div>
          </div>

          {/* Breakdown bars */}
          {Object.keys(breakdown).length > 0 && (
            <div className="mb-5 p-4 rounded-xl" style={{ background: "rgba(255,255,255,0.02)" }}>
              <h4 className="text-[11px] font-semibold uppercase tracking-wider mb-3" style={{ color: "var(--text-muted)" }}>
                Phân tích chi tiết
              </h4>
              <div className="space-y-2">
                {Object.entries(breakdown).map(([key, item]) => (
                  <Bar key={key} label={item.label || key} pct={item.pct || 0}
                    color={item.pct >= 70 ? "var(--accent-green)" : item.pct >= 40 ? "var(--accent-yellow)" : "var(--accent-red)"} />
                ))}
              </div>
            </div>
          )}

          {/* Description + Keywords side by side */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-5">
            {v.video_description && (
              <div className="p-4 rounded-xl" style={{ background: "rgba(255,255,255,0.02)" }}>
                <h4 className="text-[11px] font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--text-muted)" }}>Mô tả</h4>
                <p className="text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>{v.video_description}</p>
              </div>
            )}
            {v.top_keywords && (
              <div className="p-4 rounded-xl" style={{ background: "rgba(255,255,255,0.02)" }}>
                <h4 className="text-[11px] font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--text-muted)" }}>Từ khóa</h4>
                <div className="flex flex-wrap gap-1.5">
                  {v.top_keywords.split(",").map((kw, i) => (
                    <span key={i} className="px-2 py-0.5 rounded-md text-[11px]"
                      style={{ background: "rgba(255,255,255,0.06)", color: "var(--text-secondary)" }}>{kw.trim()}</span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* AI Insights */}
          {ti && (ti.overall_comment || ti.top_strength || ti.top_improvement) && (
            <div className="p-4 rounded-xl mb-4" style={{ background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.15)" }}>
              <h4 className="text-[11px] font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--accent-primary)" }}>🤖 AI Insights</h4>
              {ti.overall_comment && <p className="text-sm leading-relaxed mb-3" style={{ color: "var(--text-secondary)" }}>{ti.overall_comment}</p>}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {ti.top_strength && (
                  <div className="p-3 rounded-lg" style={{ background: "rgba(52,211,153,0.06)" }}>
                    <p className="text-[10px] font-semibold uppercase mb-1" style={{ color: "var(--accent-green)" }}>✅ Điểm mạnh</p>
                    <p className="text-xs" style={{ color: "var(--text-secondary)" }}>{ti.top_strength}</p>
                  </div>
                )}
                {ti.top_improvement && (
                  <div className="p-3 rounded-lg" style={{ background: "rgba(245,158,11,0.06)" }}>
                    <p className="text-[10px] font-semibold uppercase mb-1" style={{ color: "var(--accent-yellow)" }}>⚡ Cần cải thiện</p>
                    <p className="text-xs" style={{ color: "var(--text-secondary)" }}>{ti.top_improvement}</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Audio Transcript */}
          {(() => {
            const transcript = v.audio_transcript?.trim();
            const isUnavailable = !transcript
              || transcript === "Lỗi trích xuất âm thanh."
              || transcript === "Không nghe được tiếng."
              || transcript === "Không có âm thanh."
              || transcript === "Lỗi trích xuất âm thanh";
            return (
              <div className="p-4 rounded-xl" style={{ background: "rgba(255,255,255,0.02)" }}>
                <h4 className="text-[11px] font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--text-muted)" }}>🎙️ Audio Transcript</h4>
                {isUnavailable ? (
                  <p className="text-sm italic" style={{ color: "var(--text-muted)" }}>
                    Âm thanh của video này không hỗ trợ phân tích (có thể chỉ có nhạc nền hoặc không có lời thoại).
                  </p>
                ) : (
                  <p className="text-sm leading-relaxed max-h-32 overflow-y-auto whitespace-pre-wrap" style={{ color: "var(--text-secondary)" }}>
                    {transcript}
                  </p>
                )}
              </div>
            );
          })()}
        </div>
      )}
    </div>
  );
}

/* ─── Main Page ─── */
export default function HistoryPage() {
  const router = useRouter();
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [videos, setVideos] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const perPage = 10;

  useEffect(() => {
    if (authLoading) return;
    if (!isAuthenticated) { router.replace("/login"); return; }
    loadVideos(page);
  }, [isAuthenticated, authLoading, page]);

  async function loadVideos(p) {
    setLoading(true);
    try {
      const data = await getMyVideos(p, perPage);
      setVideos(data.videos || []);
      setTotal(data.total || 0);
      setTotalPages(data.total_pages || 1);
    } catch (err) {
      console.error("Failed to load history:", err);
    } finally {
      setLoading(false);
    }
  }

  function handleDelete(videoId) {
    setVideos((prev) => prev.filter((v) => v.video_id !== videoId));
    setTotal((prev) => Math.max(0, prev - 1));
  }

  if (authLoading) {
    return (
      <>
        <Navbar />
        <main className="min-h-screen flex items-center justify-center" style={{ background: "var(--bg-primary)" }}>
          <div className="w-8 h-8 border-2 border-t-transparent rounded-full animate-spin"
            style={{ borderColor: "var(--accent-primary)", borderTopColor: "transparent" }} />
        </main>
      </>
    );
  }

  return (
    <>
      <Navbar />
      <main className="min-h-screen pt-24 sm:pt-28 pb-16 px-4" style={{ background: "var(--bg-primary)" }}>
        <div className="max-w-4xl mx-auto">
          {/* Header */}
          <div className="mb-8">
            <h1 className="text-2xl sm:text-3xl font-bold mb-2" style={{ color: "var(--text-primary)" }}>
              📋 Lịch sử phân tích
            </h1>
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>
              {total > 0 ? `Bạn đã phân tích ${total} video` : "Bạn chưa phân tích video nào"}
            </p>
          </div>

          {/* Empty state */}
          {!loading && videos.length === 0 && (
            <div className="flex flex-col items-center justify-center py-20 rounded-2xl"
              style={{ background: "var(--bg-card)", border: "1px solid var(--border-color)" }}>
              <div className="text-5xl mb-4">🎬</div>
              <p className="text-lg font-semibold mb-2" style={{ color: "var(--text-primary)" }}>Chưa có phân tích nào</p>
              <p className="text-sm mb-6" style={{ color: "var(--text-muted)" }}>Hãy upload video để bắt đầu phân tích xu hướng</p>
              <Link href="/analyze" className="btn-primary text-sm no-underline px-6 py-3">Phân tích video ngay</Link>
            </div>
          )}

          {/* Loading skeleton */}
          {loading && (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="h-24 rounded-xl animate-pulse" style={{ background: "var(--bg-card)" }} />
              ))}
            </div>
          )}

          {/* Video list */}
          {!loading && videos.length > 0 && (
            <>
              <div className="space-y-3">
                {videos.map((v) => <AnalysisCard key={v.video_id} v={v} onDelete={handleDelete} />)}
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-center gap-2 mt-8">
                  <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page <= 1}
                    className="px-3 py-2 rounded-lg text-sm font-medium cursor-pointer disabled:opacity-30"
                    style={{ background: "var(--bg-card)", border: "1px solid var(--border-color)", color: "var(--text-secondary)" }}>
                    ‹ Trước
                  </button>
                  {Array.from({ length: totalPages }, (_, i) => i + 1)
                    .filter((p) => p === 1 || p === totalPages || Math.abs(p - page) <= 2)
                    .reduce((acc, p, i, arr) => { if (i > 0 && p - arr[i - 1] > 1) acc.push("..."); acc.push(p); return acc; }, [])
                    .map((p, i) => p === "..." ? (
                      <span key={`e${i}`} className="px-2 text-sm" style={{ color: "var(--text-muted)" }}>…</span>
                    ) : (
                      <button key={p} onClick={() => setPage(p)}
                        className="w-9 h-9 rounded-lg text-sm font-medium cursor-pointer"
                        style={{ background: p === page ? "var(--gradient-primary)" : "var(--bg-card)", border: p === page ? "none" : "1px solid var(--border-color)", color: p === page ? "white" : "var(--text-secondary)" }}>
                        {p}
                      </button>
                    ))}
                  <button onClick={() => setPage(Math.min(totalPages, page + 1))} disabled={page >= totalPages}
                    className="px-3 py-2 rounded-lg text-sm font-medium cursor-pointer disabled:opacity-30"
                    style={{ background: "var(--bg-card)", border: "1px solid var(--border-color)", color: "var(--text-secondary)" }}>
                    Sau ›
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </main>
      <Footer />
    </>
  );
}
