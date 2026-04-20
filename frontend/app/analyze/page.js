"use client";
import { useState, useEffect, useRef } from "react";
import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import { analyzeVideo, checkAnalysis } from "../lib/api";
import { supabase } from "../lib/supabase";

const STEPS = [
  { key: "user_pending", icon: "📋", label: "Đã tiếp nhận yêu cầu" },
  { key: "downloading", icon: "📥", label: "Đang tải video từ TikTok..." },
  { key: "analyzing", icon: "🔬", label: "AI đang phân tích đa phương thức..." },
  { key: "summarizing", icon: "🧠", label: "Groq AI đang tổng hợp & dự đoán..." },
  { key: "completed", icon: "✅", label: "Hoàn tất!" },
];

function getStepIndex(status) {
  const idx = STEPS.findIndex((s) => s.key === status);
  return idx >= 0 ? idx : 0;
}

export default function AnalyzePage() {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [videoId, setVideoId] = useState(null);
  const [tiktokUrl, setTiktokUrl] = useState("");
  const [result, setResult] = useState(null);
  const [currentStep, setCurrentStep] = useState(0);
  const channelRef = useRef(null);
  const fallbackRef = useRef(null);

  // Supabase Realtime subscription
  useEffect(() => {
    if (!videoId || result) return;

    // Try Supabase Realtime first
    if (supabase) {
      const channel = supabase
        .channel(`video-status-${videoId}`)
        .on(
          "postgres_changes",
          {
            event: "UPDATE",
            schema: "public",
            table: "videos",
            filter: `video_id=eq.${videoId}`,
          },
          (payload) => {
            const newStatus = payload.new?.ai_status;
            if (!newStatus) return;

            const idx = getStepIndex(newStatus);
            setCurrentStep(idx);

            if (newStatus === "completed" || newStatus === "error") {
              // Fetch full result
              checkAnalysis(videoId).then((data) => {
                setResult(data);
                setLoading(false);
              });
              channel.unsubscribe();
            }
          }
        )
        .subscribe();

      channelRef.current = channel;
    }

    // Fallback polling (in case Supabase Realtime is not configured)
    fallbackRef.current = setInterval(async () => {
      try {
        const data = await checkAnalysis(videoId);
        const status = data?.status || data?.video?.ai_status;
        if (status) {
          setCurrentStep(getStepIndex(status));
        }
        if (data.is_done || status === "completed" || status === "error") {
          setResult(data);
          setLoading(false);
          clearInterval(fallbackRef.current);
          if (channelRef.current) channelRef.current.unsubscribe();
        }
      } catch {
        // Keep polling
      }
    }, 8000);

    return () => {
      if (channelRef.current) channelRef.current.unsubscribe();
      if (fallbackRef.current) clearInterval(fallbackRef.current);
    };
  }, [videoId, result]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setResult(null);
    setCurrentStep(0);
    setLoading(true);
    setTiktokUrl(url.trim());

    try {
      const resp = await analyzeVideo(url.trim());
      setVideoId(resp.video_id);
      setCurrentStep(1);
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
  const progressPct = Math.min(((currentStep + 1) / STEPS.length) * 100, 100);

  return (
    <>
      <Navbar />
      <main className="pb-10 min-h-screen w-full">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 w-full">
          {/* Header */}
          <div className="text-center mb-6 mt-4">
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
                  className="input-dark text-base h-[52px]"
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

              <button type="submit" className="btn-primary w-full text-base h-[52px] flex items-center justify-center gap-2" disabled={loading}>
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="animate-spin w-5 h-5" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    AI đang xử lý...
                  </span>
                ) : (
                  "🎯 Phân Tích & Dự Báo"
                )}
              </button>
            </form>
          </div>

          {/* ═══ EMPTY STATE ═══ */}
          {!loading && !result && !error && (
            <div className="w-full rounded-2xl flex flex-col items-center justify-center animate-fadeInUp"
              style={{
                minHeight: "400px",
                border: "1px dashed rgba(255, 255, 255, 0.15)",
                background: "rgba(255, 255, 255, 0.01)"
              }}>
              <div className="w-16 h-16 rounded-full flex items-center justify-center mb-4"
                style={{ background: "rgba(255,255,255,0.03)", color: "var(--text-muted)" }}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
                  <polyline points="7.5 4.21 12 6.81 16.5 4.21"></polyline>
                  <polyline points="7.5 19.79 7.5 14.6 3 12"></polyline>
                  <polyline points="21 12 16.5 14.6 16.5 19.79"></polyline>
                  <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
                  <line x1="12" y1="22.08" x2="12" y2="12"></line>
                </svg>
              </div>
              <h3 className="text-lg font-bold" style={{ color: "#A1A1AA" }}>Kết quả phân tích sẽ hiển thị tại đây</h3>
              <p className="text-sm mt-2 max-w-sm text-center" style={{ color: "var(--text-muted)" }}>
                Hệ thống sẽ bóc tách âm thanh, caption và biểu đồ tăng trưởng để dự báo độ phổ biến.
              </p>
            </div>
          )}

          {/* ═══ PROCESSING: Video Preview + Progress ═══ */}
          {loading && videoId && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8 animate-fadeInUp" style={{ animationFillMode: "forwards" }}>
              {/* TikTok Embed */}
              <div className="glass-card p-5">
                <h3 className="text-sm font-semibold mb-3" style={{ color: "var(--text-secondary)" }}>
                  🎬 Video Đang Phân Tích
                </h3>
                <div className="rounded-xl overflow-hidden" style={{ background: "#000", aspectRatio: "9/16", maxHeight: "480px" }}>
                  <iframe
                    src={`https://www.tiktok.com/embed/v2/${videoId}`}
                    style={{ width: "100%", height: "100%", border: "none" }}
                    allow="encrypted-media"
                    allowFullScreen
                  />
                </div>
              </div>

              {/* Progress Steps */}
              <div className="glass-card p-5">
                <h3 className="text-sm font-semibold mb-4" style={{ color: "var(--text-secondary)" }}>
                  ⏳ Tiến Độ Xử Lý
                </h3>

                {/* Progress bar */}
                <div className="w-full h-3 rounded-full mb-6" style={{ background: "rgba(255,255,255,0.05)" }}>
                  <div
                    className="h-full rounded-full transition-all duration-700"
                    style={{
                      width: `${progressPct}%`,
                      background: "var(--gradient-primary)",
                      boxShadow: "0 0 12px rgba(220, 38, 38, 0.4)",
                    }}
                  />
                </div>
                <div className="text-center text-sm font-semibold mb-6" style={{ color: "var(--accent-primary)" }}>
                  {Math.round(progressPct)}%
                </div>

                {/* Step list */}
                <div className="space-y-4">
                  {STEPS.map((step, i) => {
                    const isDone = i < currentStep;
                    const isActive = i === currentStep;
                    return (
                      <div key={step.key} className="flex items-center gap-3">
                        <div
                          className="w-8 h-8 rounded-full flex items-center justify-center text-sm flex-shrink-0 transition-all duration-300"
                          style={{
                            background: isDone
                              ? "var(--accent-green)"
                              : isActive
                              ? "var(--gradient-primary)"
                              : "rgba(255,255,255,0.05)",
                            color: isDone || isActive ? "#fff" : "var(--text-muted)",
                            boxShadow: isActive ? "0 0 15px rgba(220,38,38,0.4)" : "none",
                          }}
                        >
                          {isDone ? "✓" : step.icon}
                        </div>
                        <span
                          className="text-sm font-medium transition-colors duration-300"
                          style={{
                            color: isDone
                              ? "var(--accent-green)"
                              : isActive
                              ? "var(--text-primary)"
                              : "var(--text-muted)",
                          }}
                        >
                          {step.label}
                        </span>
                        {isActive && (
                          <svg className="animate-spin w-4 h-4 ml-auto" viewBox="0 0 24 24"
                            style={{ color: "var(--accent-primary)" }}>
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                            <path className="opacity-75" fill="currentColor"
                              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                          </svg>
                        )}
                      </div>
                    );
                  })}
                </div>

                <p className="text-xs mt-6 text-center" style={{ color: "var(--text-muted)" }}>
                  💡 Bạn có thể xem video bên cạnh trong lúc chờ AI xử lý.
                </p>
              </div>
            </div>
          )}

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

              {/* 2. Video Description + Small embed */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {video.video_description && (
                  <div className="glass-card p-6 md:col-span-2">
                    <h3 className="text-lg font-bold mb-3">📝 Mô Tả Video</h3>
                    <p style={{ color: "var(--text-secondary)" }}>{video.video_description}</p>
                    <div className="flex items-center gap-3 mt-4 flex-wrap">
                      {Array.isArray(video.category) ? video.category.map((cat, ci) => (
                        <span key={ci} className="badge badge-category">{cat}</span>
                      )) : (typeof video.category === "string" ? video.category.split("|").map((cat, ci) => (
                        <span key={ci} className="badge badge-category">{cat.trim()}</span>
                      )) : <span className="badge badge-category">—</span>)}
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

                {/* Small video embed in results */}
                {tiktokUrl && (
                  <div className="glass-card p-4">
                    <h3 className="text-sm font-semibold mb-2" style={{ color: "var(--text-secondary)" }}>🎬 Video</h3>
                    <div className="rounded-lg overflow-hidden" style={{ background: "#000", aspectRatio: "9/16", maxHeight: "360px" }}>
                      <iframe
                        src={`https://www.tiktok.com/embed/v2/${videoId}`}
                        style={{ width: "100%", height: "100%", border: "none" }}
                        allow="encrypted-media"
                        allowFullScreen
                      />
                    </div>
                  </div>
                )}
              </div>

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
