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

          <div className="max-w-7xl mx-auto px-4 sm:px-6 py-28 relative z-10">
            <div className="grid grid-cols-1 md:grid-cols-12 gap-12 items-center">
              {/* Left — Copy */}
              <div className="md:col-start-3 md:col-span-5">
                <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-semibold mb-6"
                  style={{
                    background: "rgba(220, 38, 38, 0.15)",
                    border: "1px solid rgba(220, 38, 38, 0.3)",
                    color: "var(--accent-secondary)",
                  }}>
                  🤖 Powered by Multimodal AI
                </div>

                <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold leading-tight mb-6">
                  Dự Báo{" "}
                  <span className="gradient-text">Xu Hướng TikTok</span>{" "}
                  Với Trí Tuệ Nhân Tạo
                </h1>

                <p className="text-lg mb-8 max-w-lg" style={{ color: "var(--text-secondary)" }}>
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
                <div className="flex items-center gap-6 mt-10 flex-wrap">
                  {["Whisper AI", "BLIP Vision", "Groq LLM", "Random Forest"].map((tech) => (
                    <span key={tech} className="text-xs font-medium px-3 py-1 rounded-lg"
                      style={{
                        background: "rgba(255,255,255,0.05)",
                        border: "1px solid rgba(255,255,255,0.1)",
                        color: "var(--text-muted)",
                      }}>
                      {tech}
                    </span>
                  ))}
                </div>
              </div>

              {/* Right — Floating Stats Preview */}
              <div className="relative hidden md:block md:col-span-4">
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
        <section className="py-28" style={{ background: "var(--bg-secondary)" }}>
          <div className="max-w-7xl mx-auto px-4 sm:px-6">
            <div className="text-center mb-14">
              <span className="text-xs font-semibold tracking-widest uppercase"
                style={{ color: "var(--accent-primary)" }}>QUY TRÌNH</span>
              <h2 className="text-3xl sm:text-4xl font-bold mt-3">
                Cách <span className="gradient-text">TrendSense</span> Hoạt Động
              </h2>
              <p className="mt-4 max-w-2xl mx-auto" style={{ color: "var(--text-secondary)" }}>
                Pipeline tự động từ thu thập dữ liệu đến dự báo bằng AI — Tất cả chạy trên nền tảng đám mây.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              {[
                {
                  icon: "🕷️",
                  title: "Thu Thập Dữ Liệu",
                  desc: "Bot Selenium tự động cào metadata video TikTok mỗi 4 giờ qua GitHub Actions, lọc ngôn ngữ bằng LangDetect.",
                  color: "var(--accent-blue)",
                },
                {
                  icon: "🧠",
                  title: "Phân Tích AI",
                  desc: "Whisper bóc âm thanh, BLIP phân tích hình ảnh, EasyOCR đọc chữ — Groq AI tổng hợp toàn bộ thành nhận định.",
                  color: "var(--accent-primary)",
                },
                {
                  icon: "🔮",
                  title: "Dự Báo Viral",
                  desc: "Random Forest ML model kết hợp Viral Velocity để tính xác suất bùng nổ. Kết quả hiển thị realtime.",
                  color: "var(--accent-pink)",
                },
              ].map((step, i) => (
                <div key={i} className="glass-card neon-border p-8 text-center opacity-0 animate-fadeInUp"
                  style={{ animationDelay: `${i * 150}ms`, animationFillMode: "forwards" }}>
                  <div className="w-16 h-16 rounded-2xl flex items-center justify-center text-3xl mx-auto mb-5"
                    style={{ background: `linear-gradient(135deg, ${step.color}22, ${step.color}11)` }}>
                    {step.icon}
                  </div>
                  <h3 className="text-lg font-bold mb-3">{step.title}</h3>
                  <p className="text-sm" style={{ color: "var(--text-secondary)" }}>{step.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ═══════ STATS OVERVIEW ═══════ */}
        {stats && (
          <section className="py-24">
            <div className="max-w-7xl mx-auto px-4 sm:px-6">
              <div className="text-center mb-10">
                <h2 className="text-3xl font-bold">Tổng Quan <span className="gradient-text">Hệ Thống</span></h2>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
                <StatCard icon="📹" label="Tổng Video" value={formatBigNumber(stats.total_videos)} color="var(--text-primary)" delay={0} />
                <StatCard icon="👁️" label="Tổng Lượt Xem" value={formatBigNumber(stats.total_views)} color="var(--accent-cyan)" delay={100} />
                <StatCard icon="❤️" label="Tổng Lượt Tim" value={formatBigNumber(stats.total_likes)} color="var(--accent-pink)" delay={200} />
                <StatCard icon="🔥" label="Video Viral" value={stats.viral_count || 0} color="var(--accent-red)" delay={300} />
                <StatCard icon="📈" label="Avg Engagement" value={(stats.avg_engagement || 0).toFixed(1) + "%"} color="var(--accent-green)" delay={400} />
                <StatCard icon="⚡" label="Avg View/Giờ" value={formatBigNumber(Math.round(stats.avg_vph || 0))} color="var(--accent-yellow)" delay={500} />
              </div>
            </div>
          </section>
        )}

        {/* ═══════ MARKET TREND LIVE STREAM (Video Table) ═══════ */}
        <section className="py-24" style={{ background: "var(--bg-secondary)" }}>
          <div className="max-w-7xl mx-auto px-4 sm:px-6">
            <div className="flex items-center justify-between mb-8 flex-wrap gap-4">
              <div>
                <h2 className="text-2xl font-bold">🔴 Xu Hướng Trực Tiếp</h2>
                <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
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
              <div className="text-center mb-10">
                <span className="text-xs font-semibold tracking-widest uppercase"
                  style={{ color: "var(--accent-primary)" }}>PHÂN TÍCH</span>
                <h2 className="text-3xl font-bold mt-3">
                  Danh Mục <span className="gradient-text">Nóng Nhất</span>
                </h2>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {categories.slice(0, 6).map((cat, i) => (
                  <div key={i} className="glass-card neon-border p-6 opacity-0 animate-fadeInUp"
                    style={{ animationDelay: `${i * 100}ms`, animationFillMode: "forwards" }}>
                    <div className="flex items-center justify-between mb-4">
                      <span className="text-lg font-semibold">{cat.category || "—"}</span>
                      <span className="badge badge-viral">{cat.count} video</span>
                    </div>
                    <div className="grid grid-cols-3 gap-3 text-center">
                      <div>
                        <div className="text-lg font-bold" style={{ color: "var(--accent-cyan)" }}>
                          {(cat.avg_velocity || 0).toFixed(0)}
                        </div>
                        <div className="text-xs" style={{ color: "var(--text-muted)" }}>Velocity</div>
                      </div>
                      <div>
                        <div className="text-lg font-bold" style={{ color: "var(--accent-pink)" }}>
                          {(cat.avg_viral || 0).toFixed(0)}%
                        </div>
                        <div className="text-xs" style={{ color: "var(--text-muted)" }}>Viral</div>
                      </div>
                      <div>
                        <div className="text-lg font-bold" style={{ color: "var(--accent-green)" }}>
                          {(cat.avg_engagement || 0).toFixed(0)}%
                        </div>
                        <div className="text-xs" style={{ color: "var(--text-muted)" }}>Engage</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>
        )}

        {/* ═══════ CTA SECTION ═══════ */}
        <section className="py-28 relative overflow-hidden"
          style={{ background: "linear-gradient(135deg, #1a0505 0%, #000000 100%)" }}>
          <div className="bg-orb" style={{
            width: "400px", height: "400px", top: "-100px", left: "50%",
            background: "var(--accent-primary)", transform: "translateX(-50%)",
          }} />
          <div className="max-w-3xl mx-auto px-4 text-center relative z-10">
            <h2 className="text-3xl sm:text-4xl font-bold mb-5">
              Muốn Biết Video Của Bạn{" "}
              <span className="gradient-text">Có Viral Không?</span>
            </h2>
            <p className="text-lg mb-8" style={{ color: "var(--text-secondary)" }}>
              Dán link TikTok hoặc upload video — AI sẽ phân tích toàn diện và đưa ra dự báo + đề xuất tối ưu nội dung.
            </p>
            <Link href="/analyze" className="btn-primary text-lg no-underline inline-flex items-center gap-2">
              🎯 Phân Tích Video Ngay
            </Link>
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
