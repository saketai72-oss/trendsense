"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import Navbar from "./components/Navbar";
import Footer from "./components/Footer";
import StatCard from "./components/StatCard";
import VideoTable from "./components/VideoTable";
import { getStats, getVideos, getCategories } from "./lib/api";

export default function HomePage() {
  const [stats, setStats] = useState(null);
  const [videos, setVideos] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [s, v, c] = await Promise.all([
          getStats(),
          getVideos({ per_page: 10, sort_by: "viral_probability", sort_order: "desc" }),
          getCategories(),
        ]);
        setStats(s);
        setVideos(v.videos || []);
        setCategories(c || []);
      } catch (err) {
        console.error("Failed to load data:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const formatBigNumber = (n) => {
    if (!n) return "0";
    if (n >= 1_000_000_000) return (n / 1_000_000_000).toFixed(1) + "B";
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
    if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
    return n.toLocaleString();
  };

  return (
    <>
      <Navbar />
      <main className="w-full">
        {/* ═══════ HERO SECTION ═══════ */}
        <section className="relative min-h-screen flex items-center overflow-hidden w-full"
          style={{ background: "var(--gradient-hero)" }}>
          {/* Background Orbs */}
          <div className="bg-orb" style={{
            width: "500px", height: "500px", top: "-100px", right: "-100px",
            background: "var(--accent-primary)",
          }} />
          <div className="bg-orb" style={{
            width: "400px", height: "400px", bottom: "-50px", left: "-100px",
            background: "var(--accent-blue)", animationDelay: "3s",
          }} />
          <div className="bg-orb" style={{
            width: "300px", height: "300px", top: "30%", right: "20%",
            background: "var(--accent-pink)", animationDelay: "5s",
          }} />

          <div className="max-w-7xl mx-auto px-4 sm:px-6 py-32 sm:py-40 relative z-10">
            <div className="flex flex-col lg:flex-row items-center justify-center gap-16 lg:gap-20 w-full max-w-6xl mx-auto mt-10 md:mt-16">
              {/* Left — Copy */}
              <div className="flex-1 w-full max-w-2xl text-left">
                <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs font-semibold mb-8"
                  style={{
                    background: "rgba(220, 38, 38, 0.15)",
                    border: "1px solid rgba(220, 38, 38, 0.3)",
                    color: "var(--accent-secondary)",
                  }}>
                  🤖 Powered by Multimodal AI
                </div>

                <h1 className="hero-title text-4xl sm:text-5xl lg:text-6xl xl:text-7xl mb-8">
                  Dự Báo{" "}
                  <span className="gradient-text">Xu Hướng TikTok</span>{" "}
                  Với Trí Tuệ Nhân Tạo
                </h1>

                <p className="hero-subtitle text-lg sm:text-xl mb-10 max-w-lg">
                  Phân tích video đa phương thức (hình ảnh, âm thanh, chữ viết) và dự đoán khả năng bùng nổ bằng Machine Learning — Nhanh, chính xác, miễn phí.
                </p>

                <div className="flex flex-wrap gap-4">
                  <Link href="/analyze" className="btn-primary text-base no-underline flex items-center gap-2">
                    🚀 Dự Báo Video
                  </Link>
                  <Link href="/dashboard" className="btn-outline text-base no-underline flex items-center gap-2">
                    📊 Xem Dashboard
                  </Link>
                </div>

                {/* Trust badges */}
                <div className="flex items-center gap-4 mt-12 flex-wrap">
                  {["Whisper AI", "BLIP Vision", "Groq LLM", "Random Forest"].map((tech) => (
                    <span key={tech} className="text-xs font-medium px-3 py-1.5 rounded-lg"
                      style={{
                        background: "rgba(255,255,255,0.04)",
                        border: "1px solid rgba(255,255,255,0.08)",
                        color: "var(--text-muted)",
                      }}>
                      {tech}
                    </span>
                  ))}
                </div>
              </div>

              {/* Right — Floating Stats Preview */}
              <div className="flex-1 w-full max-w-lg hidden lg:block mx-auto relative">
                <div className="animate-float">
                  <div className="glass-card p-6 mb-4"
                    style={{ background: "rgba(21, 23, 51, 0.9)" }}>
                    <div className="text-sm font-semibold mb-4" style={{ color: "var(--text-secondary)" }}>
                      📊 Thống Kê Realtime
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <div className="text-2xl font-bold gradient-text">
                          {loading ? "..." : formatBigNumber(stats?.total_views)}
                        </div>
                        <div className="text-xs" style={{ color: "var(--text-muted)" }}>Tổng Lượt Xem</div>
                      </div>
                      <div>
                        <div className="text-2xl font-bold" style={{ color: "var(--accent-green)" }}>
                          {loading ? "..." : stats?.viral_count || 0}
                        </div>
                        <div className="text-xs" style={{ color: "var(--text-muted)" }}>Video Viral</div>
                      </div>
                      <div>
                        <div className="text-2xl font-bold" style={{ color: "var(--accent-cyan)" }}>
                          {loading ? "..." : formatBigNumber(stats?.total_likes)}
                        </div>
                        <div className="text-xs" style={{ color: "var(--text-muted)" }}>Tổng Lượt Tim</div>
                      </div>
                      <div>
                        <div className="text-2xl font-bold" style={{ color: "var(--accent-yellow)" }}>
                          {loading ? "..." : (stats?.avg_engagement || 0).toFixed(1) + "%"}
                        </div>
                        <div className="text-xs" style={{ color: "var(--text-muted)" }}>Avg Engagement</div>
                      </div>
                    </div>
                  </div>

                  {/* Mini trending card */}
                  <div className="glass-card p-4"
                    style={{ background: "rgba(21, 23, 51, 0.9)", marginLeft: "40px" }}>
                    <div className="text-xs font-semibold mb-3" style={{ color: "var(--accent-pink)" }}>
                      🔥 Top Viral Hiện Tại
                    </div>
                    {videos.slice(0, 3).map((v, i) => (
                      <div key={i} className="flex items-center justify-between py-1.5 border-b"
                        style={{ borderColor: "rgba(255,255,255,0.05)" }}>
                        <span className="text-xs truncate max-w-[180px]" style={{ color: "var(--text-secondary)" }}>
                          {v.caption?.substring(0, 30) || `Video ${v.video_id?.substring(0, 8)}`}
                        </span>
                        <span className="text-xs font-bold"
                          style={{ color: v.viral_probability > 50 ? "var(--accent-red)" : "var(--accent-green)" }}>
                          {(v.viral_probability || 0).toFixed(0)}%
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ═══════ HOW IT WORKS ═══════ */}
        <section className="py-32" style={{ background: "var(--bg-secondary)" }}>
          <div className="max-w-7xl mx-auto px-4 sm:px-6">
            <div className="text-center mb-16">
              <span className="text-xs font-semibold tracking-widest uppercase"
                style={{ color: "var(--accent-primary)" }}>QUY TRÌNH</span>
              <h2 className="text-3xl sm:text-4xl font-bold mt-4">
                Cách <span className="gradient-text">TrendSense</span> Hoạt Động
              </h2>
              <p className="mt-4 max-w-2xl mx-auto font-medium" style={{ color: "#B3B3B3" }}>
                Pipeline tự động từ thu thập dữ liệu đến dự báo bằng AI — Tất cả chạy trên nền tảng đám mây.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              {[
                {
                  icon: (
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 12a9 9 0 0 1-9 9m9-9a9 9 0 0 0-9-9m9 9H3m9 9a9 9 0 0 1-9-9m9 9c1.66 0 3-4.03 3-9s-1.34-9-3-9m0 18c-1.66 0-3-4.03-3-9s1.34-9 3-9m-9 9a9 9 0 0 1 9-9"/>
                    </svg>
                  ),
                  title: "Thu Thập Dữ Liệu",
                  desc: "Bot Selenium tự động cào metadata video TikTok mỗi 4 giờ qua GitHub Actions, lọc ngôn ngữ bằng LangDetect.",
                  color: "var(--accent-blue)",
                },
                {
                  icon: (
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M12 2a4 4 0 0 1 4 4c0 1.95-1.4 3.58-3.25 3.93"/>
                      <path d="M12 2a4 4 0 0 0-4 4c0 1.95 1.4 3.58 3.25 3.93"/>
                      <path d="M12 10v2"/>
                      <path d="M8 22v-2a4 4 0 0 1 4-4 4 4 0 0 1 4 4v2"/>
                      <path d="M7 12H5a2 2 0 0 0-2 2v1"/>
                      <path d="M17 12h2a2 2 0 0 1 2 2v1"/>
                    </svg>
                  ),
                  title: "Phân Tích AI",
                  desc: "Whisper bóc âm thanh, BLIP phân tích hình ảnh, EasyOCR đọc chữ — Groq AI tổng hợp toàn bộ thành nhận định.",
                  color: "var(--accent-primary)",
                },
                {
                  icon: (
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
                    </svg>
                  ),
                  title: "Dự Báo Viral",
                  desc: "Random Forest ML model kết hợp Viral Velocity để tính xác suất bùng nổ. Kết quả hiển thị realtime.",
                  color: "var(--accent-pink)",
                },
              ].map((step, i) => (
                <div key={i} className="glass-card neon-border step-card p-8 text-center opacity-0 animate-fadeInUp"
                  style={{ 
                    animationDelay: `${i * 150}ms`, 
                    animationFillMode: "forwards",
                    border: "1px solid rgba(255, 255, 255, 0.1)"
                  }}>
                  <div className="step-icon"
                    style={{
                      background: `linear-gradient(135deg, ${step.color}22, ${step.color}11)`,
                      color: step.color,
                    }}>
                    {step.icon}
                  </div>
                  <h3 className="step-title">{step.title}</h3>
                  <p className="step-desc font-medium" style={{ color: "#B3B3B3" }}>{step.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ═══════ STATS OVERVIEW ═══════ */}
        {stats && (
          <section className="py-24">
            <div className="max-w-7xl mx-auto px-4 sm:px-6">
              <div className="text-center mb-12">
                <h2 className="text-3xl font-bold">Tổng Quan <span className="gradient-text">Hệ Thống</span></h2>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
                <StatCard icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m22 8-6 4 6 4V8Z"/><rect width="14" height="12" x="2" y="6" rx="2" ry="2"/></svg>} label="Tổng Video" value={formatBigNumber(stats.total_videos)} color="var(--text-primary)" delay={0} />
                <StatCard icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0Z"/><circle cx="12" cy="12" r="3"/></svg>} label="Tổng Lượt Xem" value={formatBigNumber(stats.total_views)} color="var(--accent-cyan)" delay={100} />
                <StatCard icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/></svg>} label="Tổng Lượt Tim" value={formatBigNumber(stats.total_likes)} color="var(--accent-pink)" delay={200} />
                <StatCard icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/></svg>} label="Video Viral" value={stats.viral_count || 0} color="var(--accent-red)" delay={300} />
                <StatCard icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>} label="Avg Engagement" value={(stats.avg_engagement || 0).toFixed(1) + "%"} color="var(--accent-green)" delay={400} />
                <StatCard icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>} label="Avg View/Giờ" value={formatBigNumber(Math.round(stats.avg_vph || 0))} color="var(--accent-yellow)" delay={500} />
              </div>
            </div>
          </section>
        )}

        {/* ═══════ MARKET TREND LIVE STREAM (Video Table) ═══════ */}
        <section className="py-24" style={{ background: "var(--bg-secondary)" }}>
          <div className="max-w-7xl mx-auto px-4 sm:px-6">
            <div className="flex items-center justify-between mb-10 flex-wrap gap-4">
              <div>
                <h2 className="text-2xl font-bold">🔴 Xu Hướng Trực Tiếp</h2>
                <p className="text-sm mt-2" style={{ color: "var(--text-muted)" }}>
                  Top 10 video nóng nhất — Cập nhật mỗi 4 giờ
                </p>
              </div>
              <Link href="/dashboard"
                className="btn-outline text-sm no-underline">
                Xem Tất Cả →
              </Link>
            </div>

            {loading ? (
              <div className="space-y-3">
                {[...Array(5)].map((_, i) => (
                  <div key={i} className="skeleton h-14 w-full" />
                ))}
              </div>
            ) : (
              <VideoTable videos={videos} />
            )}
          </div>
        </section>

        {/* ═══════ CATEGORY RANKING ═══════ */}
        {categories.length > 0 && (
          <section className="py-24">
            <div className="max-w-7xl mx-auto px-4 sm:px-6">
              <div className="text-center mb-12">
                <span className="text-xs font-semibold tracking-widest uppercase"
                  style={{ color: "var(--accent-primary)" }}>PHÂN TÍCH</span>
                <h2 className="text-3xl font-bold mt-4">
                  Danh Mục <span className="gradient-text">Nóng Nhất</span>
                </h2>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {(() => {
                  const uniqueCategories = [];
                  const seen = new Set();
                  for (const cat of categories) {
                    const mainCategory = (cat.category || "—").split(",")[0].split("|")[0].trim();
                    if (!seen.has(mainCategory)) {
                      seen.add(mainCategory);
                      uniqueCategories.push({ ...cat, mainCategory });
                    }
                  }
                  
                  const displayLimit = uniqueCategories.length >= 6 ? 6 : (uniqueCategories.length >= 3 ? 3 : uniqueCategories.length);
                  const displayCats = uniqueCategories.slice(0, displayLimit);
                  
                  return displayCats.map((cat, i) => {
                    const primaryMetric = (cat.avg_viral || 0).toFixed(0);
                    const isZero = primaryMetric === "0" || !cat.avg_viral;
                    
                    return (
                      <div key={i} className="glass-card neon-border category-card p-6 opacity-0 animate-fadeInUp"
                        style={{ animationDelay: `${i * 100}ms`, animationFillMode: "forwards" }}>
                        <div className="flex items-center justify-between mb-4">
                          <span className="text-lg font-bold truncate pr-3">{cat.mainCategory}</span>
                          <span className="badge badge-viral">{cat.count} video</span>
                        </div>

                      {/* Primary metric — always visible */}
                      <div className="flex items-baseline gap-2">
                        <span className="text-3xl font-black" style={{ color: isZero ? "rgba(255, 255, 255, 0.2)" : "var(--accent-green)" }}>
                          {primaryMetric}%
                        </span>
                        <span className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>
                          Avg Viral
                        </span>
                      </div>

                      {/* Secondary metrics — reveal on hover */}
                      <div className="secondary-metrics">
                        <div className="grid grid-cols-2 gap-4 pt-4" style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}>
                          <div>
                            <div className="text-lg font-bold" style={{ color: "var(--text-primary)" }}>
                              {cat.avg_velocity >= 1000 ? (cat.avg_velocity / 1000).toFixed(1) + "K" : (cat.avg_velocity || 0).toFixed(0)}
                            </div>
                            <div className="text-xs" style={{ color: "var(--text-muted)" }}>Velocity</div>
                          </div>
                          <div>
                            <div className="text-lg font-bold" style={{ color: cat.avg_engagement > 0 ? "var(--accent-green)" : "var(--text-muted)" }}>
                              {(cat.avg_engagement || 0).toFixed(1)}%
                            </div>
                            <div className="text-xs" style={{ color: "var(--text-muted)" }}>Engage</div>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                  });
                })()}
              </div>
            </div>
          </section>
        )}

        {/* ═══════ CTA SECTION ═══════ */}
        <section className="py-32 relative overflow-hidden"
          style={{ background: "linear-gradient(135deg, #1a0505 0%, #000000 100%)" }}>
          <div className="bg-orb" style={{
            width: "400px", height: "400px", top: "-100px", left: "50%",
            background: "var(--accent-primary)", transform: "translateX(-50%)",
          }} />
          <div className="max-w-3xl mx-auto px-4 text-center relative z-10">
            <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold mb-6 leading-tight">
              Muốn Biết Video Của Bạn{" "}
              <span className="gradient-text">Có Viral Không?</span>
            </h2>
            <p className="text-lg mb-10" style={{ color: "var(--text-muted)", opacity: 0.8 }}>
              Dán link TikTok hoặc upload video — AI sẽ phân tích toàn diện và đưa ra dự báo + đề xuất tối ưu nội dung.
            </p>
            <Link href="/analyze" className="btn-primary text-lg no-underline inline-flex items-center justify-center gap-2 px-12 py-4">
              🎯 Phân Tích Video Ngay
            </Link>
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
