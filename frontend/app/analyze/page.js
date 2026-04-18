"use client";
import { useState, useEffect, useRef } from "react";
import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import { analyzeVideo, checkAnalysis } from "../lib/api";

export default function AnalyzePage() {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [videoId, setVideoId] = useState(null);
  const [result, setResult] = useState(null);
  const [polling, setPolling] = useState(false);
  const intervalRef = useRef(null);

  // Poll for results after submission
  useEffect(() => {
    if (!videoId || !polling) return;

    intervalRef.current = setInterval(async () => {
      try {
        const data = await checkAnalysis(videoId);
        if (data.is_done || data.status === "completed" || data.status === "error") {
          setResult(data);
          setPolling(false);
          setLoading(false);
          clearInterval(intervalRef.current);
        }
      } catch {
        // Keep polling
      }
    }, 5000);

    return () => clearInterval(intervalRef.current);
  }, [videoId, polling]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setResult(null);
    setLoading(true);

    try {
      const resp = await analyzeVideo(url.trim());
      setVideoId(resp.video_id);
      setPolling(true);
    } catch (err) {
      setError(err.message || "Đã có lỗi xảy ra");
      setLoading(false);
    }
  };

  const getViralLevel = (pct) => {
    if (pct >= 80) return { label: "🔥 ĐỘT PHÁ", color: "var(--accent-red)", bg: "rgba(239,68,68,0.1)" };
    if (pct >= 60) return { label: "🚀 CAO", color: "var(--accent-yellow)", bg: "rgba(245,158,11,0.1)" };
    if (pct >= 35) return { label: "📈 TRUNG BÌNH", color: "var(--accent-blue)", bg: "rgba(59,130,246,0.1)" };
    return { label: "💤 THẤP", color: "var(--text-muted)", bg: "rgba(100,116,139,0.1)" };
  };

  const video = result?.video;
  const recommendations = result?.recommendations;

  return (
    <>
      <Navbar />
      <main className="pb-10 min-h-screen w-full">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 w-full">
          {/* Header */}
          <div className="text-center mb-10 mt-8">
            <span className="text-xs font-semibold tracking-widest uppercase"
              style={{ color: "var(--accent-primary)" }}>PHÂN TÍCH ON-DEMAND</span>
            <h1 className="text-3xl sm:text-4xl font-bold mt-3">
              Dự Báo Video <span className="gradient-text">Của Bạn</span>
            </h1>
            <p className="mt-3 max-w-xl mx-auto" style={{ color: "var(--text-secondary)" }}>
              Dán link TikTok — AI sẽ tải video, phân tích âm thanh + hình ảnh + chữ viết, rồi đưa ra dự báo và đề xuất.
            </p>
          </div>

          {/* ═══ Input Form ═══ */}
          <div className="glass-card neon-border p-8 mb-8">
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="text-sm font-semibold block mb-2" style={{ color: "var(--text-secondary)" }}>
                  🔗 Link Video TikTok
                </label>
                <input
                  type="url"
                  placeholder="https://www.tiktok.com/@username/video/7384..."
                  className="input-dark text-base"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  required
                  disabled={loading}
                />
              </div>

              {error && (
                <div className="rounded-lg p-3 text-sm"
                  style={{ background: "rgba(239,68,68,0.1)", color: "var(--accent-red)", border: "1px solid rgba(239,68,68,0.2)" }}>
                  ⚠️ {error}
                </div>
              )}

              <button type="submit" className="btn-primary w-full text-base" disabled={loading}>
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="animate-spin w-5 h-5" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    AI đang phân tích... (1-3 phút)
                  </span>
                ) : (
                  "🎯 Phân Tích & Dự Báo"
                )}
              </button>
            </form>

            {/* Processing steps */}
            {loading && (
              <div className="mt-6 space-y-3">
                {[
                  { icon: "📥", text: "Đang tải video từ TikTok..." },
                  { icon: "🎧", text: "Whisper đang bóc âm thanh..." },
                  { icon: "👁️", text: "BLIP đang phân tích hình ảnh..." },
                  { icon: "📝", text: "EasyOCR đang đọc chữ trên video..." },
                  { icon: "🧠", text: "Groq AI đang tổng hợp & dự đoán..." },
                ].map((step, i) => (
                  <div key={i} className="flex items-center gap-3 text-sm opacity-0 animate-fadeInUp"
                    style={{
                      color: "var(--text-secondary)",
                      animationDelay: `${i * 600}ms`,
                      animationFillMode: "forwards",
                    }}>
                    <span className="text-lg">{step.icon}</span>
                    {step.text}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* ═══ RESULTS ═══ */}
          {result && video && (
            <div className="space-y-6 animate-fadeInUp" style={{ animationFillMode: "forwards" }}>
              {/* 1. Prediction Score */}
              <div className="glass-card p-8 text-center">
                <h2 className="text-xl font-bold mb-4">🔮 Kết Quả Dự Báo</h2>
                {(() => {
                  const pct = video.viral_probability || 0;
                  const level = getViralLevel(pct);
                  return (
                    <>
                      <div className="w-32 h-32 mx-auto rounded-full flex items-center justify-center mb-4"
                        style={{
                          background: level.bg,
                          border: `3px solid ${level.color}`,
                          boxShadow: `0 0 30px ${level.color}40`,
                        }}>
                        <span className="text-3xl font-black" style={{ color: level.color }}>
                          {pct.toFixed(0)}%
                        </span>
                      </div>
                      <div className="text-lg font-bold" style={{ color: level.color }}>{level.label}</div>
                      <p className="text-sm mt-2" style={{ color: "var(--text-muted)" }}>
                        Xác suất lan truyền dựa trên phân tích AI đa phương thức
                      </p>
                    </>
                  );
                })()}

                {/* Metrics row */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-6">
                  {[
                    { icon: "⚡", label: "View/Giờ", value: (video.views_per_hour || 0).toFixed(0), color: "var(--accent-cyan)" },
                    { icon: "📈", label: "Engagement", value: (video.engagement_rate || 0).toFixed(1) + "%", color: "var(--accent-green)" },
                    { icon: "🚀", label: "Velocity", value: (video.viral_velocity || 0).toFixed(1), color: "var(--accent-pink)" },
                    { icon: "😊", label: "Positive", value: (video.positive_score || 0).toFixed(0) + "%", color: "var(--accent-yellow)" },
                  ].map((m, i) => (
                    <div key={i} className="p-3 rounded-xl" style={{ background: "rgba(255,255,255,0.03)" }}>
                      <div className="text-lg">{m.icon}</div>
                      <div className="text-lg font-bold" style={{ color: m.color }}>{m.value}</div>
                      <div className="text-xs" style={{ color: "var(--text-muted)" }}>{m.label}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* 2. Video Description */}
              {video.video_description && (
                <div className="glass-card p-6">
                  <h3 className="text-lg font-bold mb-3">📝 Mô Tả Video</h3>
                  <p style={{ color: "var(--text-secondary)" }}>{video.video_description}</p>
                  <div className="flex items-center gap-3 mt-4 flex-wrap">
                    {(video.category || "—").split("|").map((cat, ci) => (
                      <span key={ci} className="badge badge-category">{cat.trim()}</span>
                    ))}
                    <span className="badge" style={{
                      background: video.video_sentiment?.includes("TÍCH CỰC") ? "rgba(16,185,129,0.15)" :
                        video.video_sentiment?.includes("TIÊU CỰC") ? "rgba(239,68,68,0.15)" : "rgba(245,158,11,0.15)",
                      color: video.video_sentiment?.includes("TÍCH CỰC") ? "var(--accent-green)" :
                        video.video_sentiment?.includes("TIÊU CỰC") ? "var(--accent-red)" : "var(--accent-yellow)",
                      border: "1px solid currentColor",
                    }}>
                      {video.video_sentiment || "—"}
                    </span>
                  </div>
                  {video.top_keywords && (
                    <div className="mt-4 flex flex-wrap gap-1">
                      {video.top_keywords.split(",").map((kw, i) => (
                        <span key={i} className="keyword-tag">{kw.trim()}</span>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* 3. Recommendations */}
              {recommendations && (
                <div className="glass-card p-6">
                  <h3 className="text-lg font-bold mb-4">💡 Đề Xuất Tối Ưu</h3>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {[
                      { icon: "🎬", title: "Tối Ưu Hook", text: recommendations.hook, color: "var(--accent-red)" },
                      { icon: "🎵", title: "Gợi Ý Âm Thanh", text: recommendations.audio, color: "var(--accent-blue)" },
                      { icon: "#️⃣", title: "Caption & Hashtags", text: recommendations.caption_hashtags, color: "var(--accent-primary)" },
                      { icon: "🎯", title: "Nhịp Độ & CTA", text: recommendations.pacing_cta, color: "var(--accent-green)" },
                    ].map((rec, i) => (
                      <div key={i} className="p-5 rounded-xl opacity-0 animate-fadeInUp"
                        style={{
                          background: "rgba(255,255,255,0.02)",
                          border: `1px solid ${rec.color}22`,
                          animationDelay: `${i * 100}ms`,
                          animationFillMode: "forwards",
                        }}>
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-xl">{rec.icon}</span>
                          <h4 className="font-semibold text-sm" style={{ color: rec.color }}>{rec.title}</h4>
                        </div>
                        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>{rec.text}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* View on TikTok */}
              {video.link && (
                <div className="text-center">
                  <a href={video.link} target="_blank" rel="noopener noreferrer"
                    className="btn-outline inline-flex items-center gap-2 no-underline">
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
