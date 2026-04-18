"use client";
import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import Navbar from "../../components/Navbar";
import Footer from "../../components/Footer";
import { checkAnalysis } from "../../lib/api";

export default function VideoDetailPage() {
  const params = useParams();
  const videoId = params.id;
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const res = await checkAnalysis(videoId);
        setData(res);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    if (videoId) load();
  }, [videoId]);

  const video = data?.video;

  const getViralColor = (pct) => {
    if (pct >= 70) return "var(--accent-red)";
    if (pct >= 40) return "var(--accent-yellow)";
    return "var(--accent-green)";
  };

  const formatNumber = (n) => {
    if (!n) return "0";
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
    if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
    return n.toLocaleString();
  };

  return (
    <>
      <Navbar />
      <main className="pt-20 pb-10 min-h-screen">
        <div className="max-w-4xl mx-auto px-4 sm:px-6">
          {loading ? (
            <div className="space-y-4 mt-10">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="skeleton h-24 w-full" />
              ))}
            </div>
          ) : !video ? (
            <div className="glass-card p-12 text-center mt-10">
              <div className="text-4xl mb-4">😢</div>
              <p className="text-lg font-semibold">Video không tìm thấy</p>
              <p className="text-sm mt-2" style={{ color: "var(--text-muted)" }}>
                Video ID: {videoId}
              </p>
            </div>
          ) : (
            <div className="space-y-6 mt-8 animate-fadeInUp" style={{ animationFillMode: "forwards" }}>
              {/* Title Card */}
              <div className="glass-card p-6">
                <div className="flex items-start justify-between gap-4 flex-wrap">
                  <div className="flex-1">
                    <h1 className="text-2xl font-bold mb-2">
                      {video.caption || `Video ${videoId.substring(0, 12)}...`}
                    </h1>
                    {video.video_description && (
                      <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
                        {video.video_description}
                      </p>
                    )}
                    <div className="flex items-center gap-3 mt-3 flex-wrap">
                      {(video.category || "—").split("|").map((cat, ci) => (
                        <span key={ci} className="badge badge-category">{cat.trim()}</span>
                      ))}
                      <span className="badge" style={{
                        background: video.video_sentiment?.includes("TÍCH CỰC") ? "rgba(16,185,129,0.15)" :
                          video.video_sentiment?.includes("TIÊU CỰC") ? "rgba(239,68,68,0.15)" : "rgba(245,158,11,0.15)",
                        color: video.video_sentiment?.includes("TÍCH CỰC") ? "var(--accent-green)" :
                          video.video_sentiment?.includes("TIÊU CỰC") ? "var(--accent-red)" : "var(--accent-yellow)",
                      }}>
                        {video.video_sentiment || "—"}
                      </span>
                      <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                        📅 {video.scrape_date || "N/A"}
                      </span>
                    </div>
                  </div>
                  {/* Viral Score */}
                  <div className="text-center">
                    <div className="w-20 h-20 rounded-full flex items-center justify-center"
                      style={{
                        border: `3px solid ${getViralColor(video.viral_probability || 0)}`,
                        boxShadow: `0 0 20px ${getViralColor(video.viral_probability || 0)}30`,
                      }}>
                      <span className="text-2xl font-black" style={{ color: getViralColor(video.viral_probability || 0) }}>
                        {(video.viral_probability || 0).toFixed(0)}%
                      </span>
                    </div>
                    <span className="text-xs mt-1 block" style={{ color: "var(--text-muted)" }}>Viral</span>
                  </div>
                </div>
              </div>

              {/* Metrics Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
                {[
                  { icon: "👁️", label: "Views", value: formatNumber(video.views), color: "var(--text-primary)" },
                  { icon: "❤️", label: "Likes", value: formatNumber(video.likes), color: "var(--accent-pink)" },
                  { icon: "💬", label: "Comments", value: formatNumber(video.comments), color: "var(--accent-blue)" },
                  { icon: "🔄", label: "Shares", value: formatNumber(video.shares), color: "var(--accent-cyan)" },
                  { icon: "🔖", label: "Saves", value: formatNumber(video.saves), color: "var(--accent-green)" },
                  { icon: "⚡", label: "View/h", value: (video.views_per_hour || 0).toFixed(0), color: "var(--accent-yellow)" },
                ].map((m, i) => (
                  <div key={i} className="glass-card p-4 text-center">
                    <div className="text-xl mb-1">{m.icon}</div>
                    <div className="text-xl font-bold" style={{ color: m.color }}>{m.value}</div>
                    <div className="text-xs" style={{ color: "var(--text-muted)" }}>{m.label}</div>
                  </div>
                ))}
              </div>

              {/* Performance Metrics */}
              <div className="glass-card p-6">
                <h3 className="font-bold mb-4">📊 Chỉ Số Hiệu Suất</h3>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
                  {[
                    { label: "Engagement Rate", value: video.engagement_rate, unit: "%", max: 50, color: "var(--accent-green)" },
                    { label: "Viral Velocity", value: video.viral_velocity, unit: "", max: 5000, color: "var(--accent-cyan)" },
                    { label: "Positive Score", value: video.positive_score, unit: "%", max: 100, color: "var(--accent-yellow)" },
                  ].map((m, i) => {
                    const pct = Math.min(((m.value || 0) / m.max) * 100, 100);
                    return (
                      <div key={i}>
                        <div className="flex justify-between text-sm mb-2">
                          <span style={{ color: "var(--text-secondary)" }}>{m.label}</span>
                          <span className="font-semibold" style={{ color: m.color }}>
                            {(m.value || 0).toFixed(1)}{m.unit}
                          </span>
                        </div>
                        <div className="w-full h-2 rounded-full" style={{ background: "rgba(255,255,255,0.05)" }}>
                          <div className="h-full rounded-full transition-all duration-700"
                            style={{ width: `${pct}%`, background: m.color }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Comments */}
              <div className="glass-card p-6">
                <h3 className="font-bold mb-4">💬 Top Bình Luận</h3>
                <div className="space-y-3">
                  {[1, 2, 3, 4, 5].map((i) => {
                    const cmt = video[`top${i}_cmt`];
                    const likes = video[`top${i}_likes`];
                    if (!cmt || cmt === "None") return null;
                    return (
                      <div key={i} className="p-4 rounded-xl" style={{ background: "rgba(255,255,255,0.02)" }}>
                        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>💬 {cmt}</p>
                        {likes > 0 && (
                          <span className="text-xs mt-1 inline-block" style={{ color: "var(--accent-pink)" }}>
                            ❤️ {formatNumber(likes)} likes
                          </span>
                        )}
                      </div>
                    );
                  }).filter(Boolean)}
                </div>
              </div>

              {/* Keywords */}
              {video.top_keywords && (
                <div className="glass-card p-6">
                  <h3 className="font-bold mb-3">🏷️ Từ Khóa</h3>
                  <div className="flex flex-wrap gap-2">
                    {video.top_keywords.split(",").map((kw, i) => (
                      <span key={i} className="keyword-tag">{kw.trim()}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* TikTok Link */}
              {video.link && (
                <div className="text-center">
                  <a href={video.link} target="_blank" rel="noopener noreferrer"
                    className="btn-primary inline-flex items-center gap-2 no-underline">
                    🔗 Xem Trên TikTok
                  </a>
                </div>
              )}
            </div>
          )}
        </div>
      </main>
      <Footer />
    </>
  );
}
