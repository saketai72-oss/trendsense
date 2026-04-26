"use client";
import { useState, useEffect, useRef } from "react";
import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import { analyzeVideo, checkAnalysis } from "../lib/api";
import { supabase } from "../lib/supabase";

const STEPS = [
  { key: "user_pending", icon: "📋", label: "Đã tiếp nhận yêu cầu" },
  { key: "downloading", icon: "📥", label: "Đang xử lý video..." },
  { key: "analyzing", icon: "🔬", label: "AI đang phân tích đa phương thức..." },
  { key: "summarizing", icon: "🧠", label: "Groq AI đang tổng hợp & dự đoán..." },
  { key: "completed", icon: "✅", label: "Hoàn tất!" },
];

function getStepIndex(status) {
  const idx = STEPS.findIndex((s) => s.key === status);
  return idx >= 0 ? idx : 0;
}

export default function AnalyzePage() {
  const [videoFile, setVideoFile] = useState(null);
  const [videoPreview, setVideoPreview] = useState(null);
  const [caption, setCaption] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [videoId, setVideoId] = useState(null);
  const [result, setResult] = useState(null);
  const [currentStep, setCurrentStep] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef(null);
  const channelRef = useRef(null);
  const fallbackRef = useRef(null);

  useEffect(() => {
    if (!videoId || result) return;
    if (supabase) {
      const channel = supabase
        .channel(`video-status-${videoId}`)
        .on("postgres_changes", { event: "UPDATE", schema: "public", table: "videos", filter: `video_id=eq.${videoId}` },
          (payload) => {
            const newStatus = payload.new?.ai_status;
            if (!newStatus) return;
            setCurrentStep(getStepIndex(newStatus));
            if (newStatus === "completed" || newStatus === "error") {
              checkAnalysis(videoId).then((data) => { setResult(data); setLoading(false); });
              channel.unsubscribe();
            }
          }
        ).subscribe();
      channelRef.current = channel;
    }
    fallbackRef.current = setInterval(async () => {
      try {
        const data = await checkAnalysis(videoId);
        const status = data?.status || data?.video?.ai_status;
        if (status) setCurrentStep(getStepIndex(status));
        if (data.is_done || status === "completed" || status === "error") {
          setResult(data); setLoading(false);
          clearInterval(fallbackRef.current);
          if (channelRef.current) channelRef.current.unsubscribe();
        }
      } catch { /* keep polling */ }
    }, 8000);
    return () => {
      if (channelRef.current) channelRef.current.unsubscribe();
      if (fallbackRef.current) clearInterval(fallbackRef.current);
    };
  }, [videoId, result]);

  const handleFileSelect = (file) => {
    if (!file) return;
    const allowed = ["video/mp4", "video/quicktime", "video/x-msvideo", "video/webm", "video/x-matroska"];
    if (!allowed.includes(file.type)) {
      setError("Định dạng không hỗ trợ. Chấp nhận: MP4, MOV, AVI, WebM, MKV.");
      return;
    }
    if (file.size > 100 * 1024 * 1024) {
      setError("Video quá lớn. Tối đa 100 MB.");
      return;
    }
    setError("");
    setVideoFile(file);
    setVideoPreview(URL.createObjectURL(file));
  };

  const handleDrop = (e) => {
    e.preventDefault(); setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFileSelect(file);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!videoFile) { setError("Vui lòng chọn video để phân tích."); return; }
    setError(""); setResult(null); setCurrentStep(0); setLoading(true);
    try {
      const resp = await analyzeVideo(videoFile, caption);
      setVideoId(resp.video_id);
      setCurrentStep(1);
    } catch (err) {
      setError(err.message || "Đã có lỗi xảy ra");
      setLoading(false);
    }
  };

  const resetForm = () => {
    setVideoFile(null); setVideoPreview(null); setCaption("");
    setResult(null); setVideoId(null); setError(""); setCurrentStep(0);
  };

  const getViralLevel = (pct) => {
    if (pct >= 80) return { label: "🔥 ĐỘT PHÁ", color: "var(--accent-red)", bg: "rgba(239,68,68,0.1)" };
    if (pct >= 60) return { label: "🚀 CAO", color: "var(--accent-yellow)", bg: "rgba(245,158,11,0.1)" };
    if (pct >= 35) return { label: "📈 TRUNG BÌNH", color: "var(--accent-blue)", bg: "rgba(59,130,246,0.1)" };
    return { label: "💤 THẤP", color: "var(--text-muted)", bg: "rgba(100,116,139,0.1)" };
  };

  const getTrendLevel = (score) => {
    if (score >= 80) return { label: "🔥 Rất bám trend", color: "var(--accent-red)", bg: "rgba(239,68,68,0.1)" };
    if (score >= 60) return { label: "🚀 Khá tốt", color: "var(--accent-yellow)", bg: "rgba(245,158,11,0.1)" };
    if (score >= 40) return { label: "📊 Trung bình", color: "var(--accent-blue)", bg: "rgba(59,130,246,0.1)" };
    return { label: "💤 Chưa bám trend", color: "var(--text-muted)", bg: "rgba(100,116,139,0.1)" };
  };

  const video = result?.video;
  const recommendations = result?.recommendations;
  const progressPct = Math.min(((currentStep + 1) / STEPS.length) * 100, 100);
  const fileSizeMB = videoFile ? (videoFile.size / 1024 / 1024).toFixed(1) : 0;

  return (
    <>
      <Navbar />
      <main className="pb-10 min-h-screen w-full">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 w-full">
          {/* Header */}
          <div className="text-center mb-6 mt-4">
            <span className="text-xs font-semibold tracking-widest uppercase" style={{ color: "var(--accent-primary)" }}>PHÂN TÍCH ON-DEMAND</span>
            <h1 className="text-3xl sm:text-4xl font-bold mt-3">
              Dự Báo Video <span className="gradient-text">Của Bạn</span>
            </h1>
            <p className="mt-3 max-w-xl mx-auto" style={{ color: "var(--text-secondary)" }}>
              Tải lên video — AI sẽ phân tích âm thanh + hình ảnh + chữ viết, rồi đưa ra dự báo và đề xuất.
            </p>
          </div>

          {/* ═══ Input Form ═══ */}
          <div className="glass-card neon-border p-8 mb-8">
            <form onSubmit={handleSubmit} className="space-y-5">
              {/* Video Upload Zone */}
              <div>
                <label className="text-sm font-semibold block mb-2" style={{ color: "var(--text-secondary)" }}>
                  🎬 Video
                </label>
                <div
                  onClick={() => !loading && fileInputRef.current?.click()}
                  onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                  onDragLeave={() => setIsDragging(false)}
                  onDrop={handleDrop}
                  className="relative rounded-2xl transition-all duration-300 cursor-pointer"
                  style={{
                    border: isDragging ? "2px solid var(--accent-primary)" : videoFile ? "2px solid rgba(52,211,153,0.5)" : "2px dashed rgba(255,255,255,0.15)",
                    background: isDragging ? "rgba(220,38,38,0.08)" : videoFile ? "rgba(52,211,153,0.05)" : "rgba(255,255,255,0.02)",
                    minHeight: videoFile ? "auto" : "180px",
                    boxShadow: isDragging ? "0 0 30px rgba(220,38,38,0.15)" : "none",
                  }}
                >
                  <input ref={fileInputRef} type="file" accept="video/mp4,video/quicktime,video/x-msvideo,video/webm,video/x-matroska" className="hidden" disabled={loading}
                    onChange={(e) => handleFileSelect(e.target.files?.[0])} />

                  {!videoFile ? (
                    <div className="flex flex-col items-center justify-center py-10 px-4">
                      <div className="w-16 h-16 rounded-full flex items-center justify-center mb-4" style={{ background: "rgba(220,38,38,0.1)" }}>
                        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--accent-primary)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" />
                        </svg>
                      </div>
                      <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Kéo thả video vào đây hoặc nhấn để chọn</p>
                      <p className="text-xs mt-2" style={{ color: "var(--text-muted)" }}>MP4, MOV, AVI, WebM, MKV — Tối đa 100 MB</p>
                    </div>
                  ) : (
                    <div className="p-4">
                      <div className="flex items-start gap-4">
                        <div className="rounded-xl overflow-hidden flex-shrink-0" style={{ width: "160px", background: "#000" }}>
                          <video src={videoPreview} className="w-full" style={{ maxHeight: "200px", objectFit: "cover" }} muted />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-2">
                            <span className="text-lg">✅</span>
                            <span className="text-sm font-bold" style={{ color: "var(--accent-green)" }}>Video đã chọn</span>
                          </div>
                          <p className="text-sm truncate" style={{ color: "var(--text-primary)" }}>{videoFile.name}</p>
                          <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>{fileSizeMB} MB</p>
                          {!loading && (
                            <button type="button" onClick={(e) => { e.stopPropagation(); resetForm(); }}
                              className="text-xs mt-3 px-3 py-1.5 rounded-lg transition-all" style={{ color: "var(--accent-red)", background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.2)" }}>
                              ✕ Chọn lại
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Caption Input */}
              <div>
                <label className="text-sm font-semibold block mb-2" style={{ color: "var(--text-secondary)" }}>
                  ✍️ Caption / Mô tả video <span className="font-normal" style={{ color: "var(--text-muted)" }}>(tùy chọn)</span>
                </label>
                <textarea
                  placeholder="Nhập caption, hashtag hoặc mô tả ngắn về video của bạn..."
                  className="input-dark text-sm resize-none"
                  style={{ minHeight: "80px" }}
                  value={caption}
                  onChange={(e) => setCaption(e.target.value)}
                  disabled={loading}
                  maxLength={500}
                />
                <div className="text-right text-xs mt-1" style={{ color: "var(--text-muted)" }}>{caption.length}/500</div>
              </div>

              {error && (
                <div className="rounded-lg p-3 text-sm" style={{ background: "rgba(239,68,68,0.1)", color: "var(--accent-red)", border: "1px solid rgba(239,68,68,0.2)" }}>
                  ⚠️ {error}
                </div>
              )}

              <button type="submit" className="btn-primary w-full text-base h-[52px] flex items-center justify-center gap-2" disabled={loading || !videoFile}>
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="animate-spin w-5 h-5" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" /></svg>
                    AI đang xử lý...
                  </span>
                ) : "🎯 Phân Tích & Dự Báo"}
              </button>
            </form>
          </div>

          {/* ═══ EMPTY STATE ═══ */}
          {!loading && !result && !error && (
            <div className="w-full rounded-2xl flex flex-col items-center justify-center animate-fadeInUp"
              style={{ minHeight: "400px", border: "1px dashed rgba(255, 255, 255, 0.15)", background: "rgba(255, 255, 255, 0.01)" }}>
              <div className="w-16 h-16 rounded-full flex items-center justify-center mb-4" style={{ background: "rgba(255,255,255,0.03)", color: "var(--text-muted)" }}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
                  <polyline points="7.5 4.21 12 6.81 16.5 4.21"></polyline><polyline points="7.5 19.79 7.5 14.6 3 12"></polyline>
                  <polyline points="21 12 16.5 14.6 16.5 19.79"></polyline><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
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
              <div className="glass-card p-5">
                <h3 className="text-sm font-semibold mb-3" style={{ color: "var(--text-secondary)" }}>🎬 Video Đang Phân Tích</h3>
                <div className="rounded-xl overflow-hidden" style={{ background: "#000", maxHeight: "480px" }}>
                  {videoPreview && <video src={videoPreview} controls className="w-full" style={{ maxHeight: "480px", objectFit: "contain" }} />}
                </div>
                {caption && <p className="text-xs mt-3 px-1" style={{ color: "var(--text-muted)" }}>📝 {caption}</p>}
              </div>
              <div className="glass-card p-5">
                <h3 className="text-sm font-semibold mb-4" style={{ color: "var(--text-secondary)" }}>⏳ Tiến Độ Xử Lý</h3>
                <div className="w-full h-3 rounded-full mb-6" style={{ background: "rgba(255,255,255,0.05)" }}>
                  <div className="h-full rounded-full transition-all duration-700" style={{ width: `${progressPct}%`, background: "var(--gradient-primary)", boxShadow: "0 0 12px rgba(220, 38, 38, 0.4)" }} />
                </div>
                <div className="text-center text-sm font-semibold mb-6" style={{ color: "var(--accent-primary)" }}>{Math.round(progressPct)}%</div>
                <div className="space-y-4">
                  {STEPS.map((step, i) => {
                    const isDone = i < currentStep, isActive = i === currentStep;
                    return (
                      <div key={step.key} className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full flex items-center justify-center text-sm flex-shrink-0 transition-all duration-300"
                          style={{ background: isDone ? "var(--accent-green)" : isActive ? "var(--gradient-primary)" : "rgba(255,255,255,0.05)", color: isDone || isActive ? "#fff" : "var(--text-muted)", boxShadow: isActive ? "0 0 15px rgba(220,38,38,0.4)" : "none" }}>
                          {isDone ? "✓" : step.icon}
                        </div>
                        <span className="text-sm font-medium transition-colors duration-300" style={{ color: isDone ? "var(--accent-green)" : isActive ? "var(--text-primary)" : "var(--text-muted)" }}>{step.label}</span>
                        {isActive && (<svg className="animate-spin w-4 h-4 ml-auto" viewBox="0 0 24 24" style={{ color: "var(--accent-primary)" }}><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" /></svg>)}
                      </div>
                    );
                  })}
                </div>
                <p className="text-xs mt-6 text-center" style={{ color: "var(--text-muted)" }}>💡 Bạn có thể xem video bên cạnh trong lúc chờ AI xử lý.</p>
              </div>
            </div>
          )}

          {/* ═══ RESULTS ═══ */}
          {result && video && (
            <div className="space-y-6 animate-fadeInUp" style={{ animationFillMode: "forwards" }}>
              {/* 1. Score & Metrics */}
              {result.analysis_type === "content_based" ? (
                <div className="glass-card p-8">
                  <h2 className="text-xl font-bold mb-6 text-center">🎯 Điểm Bám Trend (Trend Alignment)</h2>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-8 items-center">
                    {/* Circle Score */}
                    <div className="text-center md:col-span-1">
                      {(() => {
                        const score = video.trend_alignment_score || 0;
                        const level = getTrendLevel(score);
                        return (<>
                          <div className="w-40 h-40 mx-auto rounded-full flex flex-col items-center justify-center mb-4 transition-all duration-500" style={{ background: level.bg, border: `4px solid ${level.color}`, boxShadow: `0 0 40px ${level.color}40` }}>
                            <span className="text-4xl font-black" style={{ color: level.color }}>{score.toFixed(1)}</span>
                            <span className="text-sm font-bold mt-1" style={{ color: level.color }}>/ 100</span>
                          </div>
                          <div className="text-xl font-bold" style={{ color: level.color }}>{level.label}</div>
                          <p className="text-xs mt-2" style={{ color: "var(--text-muted)" }}>Đánh giá dựa trên xu hướng nội dung hiện tại</p>
                        </>);
                      })()}
                    </div>
                    {/* Breakdown Progress Bars */}
                    <div className="md:col-span-2 space-y-4">
                      {(() => {
                        const breakdown = result.trend_insights?.breakdown || {};
                        const items = [
                          { key: "category", icon: "🏷️", label: "Danh mục" },
                          { key: "content", icon: "📝", label: "Nội dung" },
                          { key: "audio", icon: "🎵", label: "Âm thanh" },
                          { key: "duration", icon: "⏱️", label: "Thời lượng" },
                          { key: "format", icon: "📐", label: "Định dạng" },
                        ];
                        return items.map((item) => {
                          const data = breakdown[item.key];
                          if (!data) return null;
                          return (
                            <div key={item.key} className="space-y-1">
                              <div className="flex justify-between text-sm">
                                <span className="font-medium" style={{ color: "var(--text-secondary)" }}>{item.icon} {item.label}</span>
                                <span className="font-bold text-xs" style={{ color: "var(--text-primary)" }}>{data.score} / {data.max}</span>
                              </div>
                              <div className="w-full h-2 rounded-full" style={{ background: "rgba(255,255,255,0.1)" }}>
                                <div className="h-full rounded-full transition-all duration-1000" style={{ width: `${data.pct}%`, background: "var(--gradient-primary)" }}></div>
                              </div>
                              <div className="text-xs text-right" style={{ color: "var(--text-muted)" }}>{data.label}</div>
                            </div>
                          );
                        });
                      })()}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="glass-card p-8 text-center">
                  <h2 className="text-xl font-bold mb-4">🔮 Kết Quả Dự Báo</h2>
                  {(() => {
                    const pct = video.viral_probability || 0;
                    const level = getViralLevel(pct);
                    return (<>
                      <div className="w-32 h-32 mx-auto rounded-full flex items-center justify-center mb-4" style={{ background: level.bg, border: `3px solid ${level.color}`, boxShadow: `0 0 30px ${level.color}40` }}>
                        <span className="text-3xl font-black" style={{ color: level.color }}>{pct.toFixed(0)}%</span>
                      </div>
                      <div className="text-lg font-bold" style={{ color: level.color }}>{level.label}</div>
                      <p className="text-sm mt-2" style={{ color: "var(--text-muted)" }}>Xác suất lan truyền dựa trên phân tích AI đa phương thức</p>
                    </>);
                  })()}
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
              )}

              {/* 2. Video Description + Preview */}
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
                        background: video.video_sentiment?.includes("TÍCH CỰC") ? "rgba(16,185,129,0.15)" : video.video_sentiment?.includes("TIÊU CỰC") ? "rgba(239,68,68,0.15)" : "rgba(245,158,11,0.15)",
                        color: video.video_sentiment?.includes("TÍCH CỰC") ? "var(--accent-green)" : video.video_sentiment?.includes("TIÊU CỰC") ? "var(--accent-red)" : "var(--accent-yellow)",
                        border: "1px solid currentColor",
                      }}>{video.video_sentiment || "—"}</span>
                    </div>
                    {video.top_keywords && (
                      <div className="mt-4 flex flex-wrap gap-1">
                        {video.top_keywords.split(",").map((kw, i) => (<span key={i} className="keyword-tag">{kw.trim()}</span>))}
                      </div>
                    )}
                  </div>
                )}
                {videoPreview && (
                  <div className="glass-card p-4">
                    <h3 className="text-sm font-semibold mb-2" style={{ color: "var(--text-secondary)" }}>🎬 Video</h3>
                    <div className="rounded-lg overflow-hidden" style={{ background: "#000", maxHeight: "360px" }}>
                      <video src={videoPreview} controls className="w-full" style={{ maxHeight: "360px", objectFit: "contain" }} />
                    </div>
                  </div>
                )}
              </div>

              {/* 3. Recommendations / Insights */}
              {result.analysis_type === "content_based" && result.trend_insights?.overall_comment ? (
                <div className="glass-card p-6">
                  <h3 className="text-lg font-bold mb-4">🤖 Nhận Xét Từ AI</h3>
                  <div className="mb-6 p-4 rounded-xl" style={{ background: "rgba(255,255,255,0.03)", borderLeft: "4px solid var(--accent-primary)" }}>
                    <p className="text-sm leading-relaxed" style={{ color: "var(--text-primary)" }}>{result.trend_insights.overall_comment}</p>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="p-5 rounded-xl" style={{ background: "rgba(16,185,129,0.05)", border: "1px solid rgba(16,185,129,0.2)" }}>
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-xl">💪</span>
                        <h4 className="font-semibold text-sm" style={{ color: "var(--accent-green)" }}>Điểm Mạnh</h4>
                      </div>
                      <p className="text-sm" style={{ color: "var(--text-secondary)" }}>{result.trend_insights.top_strength}</p>
                    </div>
                    <div className="p-5 rounded-xl" style={{ background: "rgba(245,158,11,0.05)", border: "1px solid rgba(245,158,11,0.2)" }}>
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-xl">🎯</span>
                        <h4 className="font-semibold text-sm" style={{ color: "var(--accent-yellow)" }}>Đề Xuất Cải Thiện</h4>
                      </div>
                      <p className="text-sm" style={{ color: "var(--text-secondary)" }}>{result.trend_insights.top_improvement}</p>
                    </div>
                  </div>
                </div>
              ) : recommendations ? (
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
                        style={{ background: "rgba(255,255,255,0.02)", border: `1px solid ${rec.color}22`, animationDelay: `${i * 100}ms`, animationFillMode: "forwards" }}>
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-xl">{rec.icon}</span>
                          <h4 className="font-semibold text-sm" style={{ color: rec.color }}>{rec.title}</h4>
                        </div>
                        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>{rec.text}</p>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              {/* Analyze Another */}
              <div className="text-center">
                <button onClick={resetForm} className="btn-outline inline-flex items-center gap-2">🔄 Phân Tích Video Khác</button>
              </div>
            </div>
          )}
        </div>
      </main>
      <Footer />
    </>
  );
}
