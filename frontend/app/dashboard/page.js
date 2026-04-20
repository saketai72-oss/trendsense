"use client";
import { useState, useEffect, useCallback } from "react";
import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import StatCard from "../components/StatCard";
import VideoTable from "../components/VideoTable";
import { getStats, getVideos, getCategories, getKeywords, getSentiments } from "../lib/api";

const STANDARD_CATEGORIES = [
  "🎭 Giải trí", "🎵 Âm nhạc", "🍳 Ẩm thực", "💻 Công nghệ",
  "👗 Thời trang", "📚 Giáo dục", "🏋️ Thể thao", "🐾 Động vật",
  "💄 Làm đẹp", "📰 Tin tức", "💰 Tài chính",
];

function getPaginationPages(current, total) {
  if (total <= 9) return Array.from({ length: total }, (_, i) => i + 1);
  const pages = [];
  if (current <= 5) {
    for (let i = 1; i <= 6; i++) pages.push(i);
    pages.push('...');
    for (let i = total - 1; i <= total; i++) pages.push(i);
  } else if (current >= total - 4) {
    pages.push(1, 2, '...');
    for (let i = total - 5; i <= total; i++) pages.push(i);
  } else {
    pages.push(1, '...');
    for (let i = current - 2; i <= current + 2; i++) pages.push(i);
    pages.push('...', total);
  }
  return pages;
}

export default function DashboardPage() {
  const [stats, setStats] = useState(null);
  const [videos, setVideos] = useState([]);
  const [totalVideos, setTotalVideos] = useState(0);
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(20);
  const [totalPages, setTotalPages] = useState(1);
  const [sortBy, setSortBy] = useState("viral_probability");
  const [sortOrder, setSortOrder] = useState("desc");
  const [selectedCategories, setSelectedCategories] = useState([]);
  const [sentimentFilter, setSentimentFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [minViral, setMinViral] = useState(0);
  const [keywords, setKeywords] = useState([]);
  const [sentiments, setSentiments] = useState([]);
  const [loading, setLoading] = useState(true);

  const formatBigNumber = (n) => {
    if (!n) return "0";
    if (n >= 1_000_000_000) return (n / 1_000_000_000).toFixed(1) + "B";
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
    if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
    return n.toLocaleString();
  };

  // Load sidebar data once
  useEffect(() => {
    async function loadMeta() {
      try {
        const [s, kw, se] = await Promise.all([
          getStats(), getKeywords(20), getSentiments(),
        ]);
        setStats(s);
        setKeywords(kw || []);
        setSentiments(se || []);
      } catch (err) {
        console.error(err);
      }
    }
    loadMeta();
  }, []);

  // Load videos on filter/page change
  const loadVideos = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getVideos({
        page, per_page: perPage,
        sort_by: sortBy, sort_order: sortOrder,
        category: selectedCategories.join(","), sentiment: sentimentFilter,
        search: searchQuery, min_viral: minViral,
      });
      setVideos(data.videos || []);
      setTotalVideos(data.total || 0);
      setTotalPages(data.total_pages || 1);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [page, perPage, sortBy, sortOrder, selectedCategories, sentimentFilter, searchQuery, minViral]);

  useEffect(() => { loadVideos(); }, [loadVideos]);

  const handleSort = (col) => {
    if (sortBy === col) {
      setSortOrder(sortOrder === "desc" ? "asc" : "desc");
    } else {
      setSortBy(col);
      setSortOrder("desc");
    }
    setPage(1);
  };

  const handleSearch = (e) => {
    e.preventDefault();
    setPage(1);
    loadVideos();
  };

  // Sentiment color map
  const sentimentColors = {
    "🟢 TÍCH CỰC": "var(--accent-green)",
    "🔴 TIÊU CỰC": "var(--accent-red)",
    "🟡 TRUNG LẬP": "var(--accent-yellow)",
  };

  return (
    <>
      <Navbar />
      <main className="w-full pb-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 w-full pt-16">
          {/* Header */}
          <div className="mb-12">
            <h1 className="text-4xl font-bold tracking-tight">Dashboard Phân Tích</h1>
            <p className="mt-3 text-lg" style={{ color: "var(--text-muted)" }}>
              Bảng điều khiển toàn diện — Theo dõi siêu hướng & thống kê chi tiết theo thời gian thực
            </p>
          </div>

          {/* Stats Row */}
          {stats && (
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-6 mb-12">
              <StatCard icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m22 8-6 4 6 4V8Z"/><rect width="14" height="12" x="2" y="6" rx="2" ry="2"/></svg>} label="Tổng Video" value={formatBigNumber(stats.total_videos)} delay={0} />
              <StatCard icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0Z"/><circle cx="12" cy="12" r="3"/></svg>} label="Tổng Views" value={formatBigNumber(stats.total_views)} color="var(--accent-cyan)" delay={50} />
              <StatCard icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/></svg>} label="Tổng Likes" value={formatBigNumber(stats.total_likes)} color="var(--accent-pink)" delay={100} />
              <StatCard icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/></svg>} label="Video Viral" value={stats.viral_count} color="var(--accent-red)" delay={150} />
              <StatCard icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>} label="Avg Engage" value={(stats.avg_engagement || 0).toFixed(1) + "%"} color="var(--accent-green)" delay={200} />
              <StatCard icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="18" height="18" x="3" y="4" rx="2" ry="2"/><line x1="16" x2="16" y1="2" y2="6"/><line x1="8" x2="8" y1="2" y2="6"/><line x1="3" x2="21" y1="10" y2="10"/></svg>} label="Ngày Thu Thập" value={stats.scrape_days} delay={250} />
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-4 gap-12">
            {/* ═══ Sidebar: Filters ═══ */}
            <div className="lg:col-span-1 space-y-6 lg:sticky lg:top-24 lg:max-h-[calc(100vh-120px)] lg:overflow-y-auto lg:pr-2 custom-scrollbar">
              {/* Search */}
              <div className="glass-card p-6">
                <h3 className="text-sm font-bold mb-4 flex items-center gap-2" style={{ color: "var(--text-secondary)" }}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
                  TÌM KIẾM
                </h3>
                <form onSubmit={handleSearch}>
                  <input
                    type="text"
                    placeholder="Hashtag, từ khóa..."
                    className="input-dark text-sm border border-[#333]"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </form>
              </div>

              {/* Category Filter */}
              <div className="glass-card p-6">
                <h3 className="text-sm font-bold mb-4 flex items-center gap-2" style={{ color: "var(--text-secondary)" }}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="m9.06 11.9 8.07-8.06a2.85 2.85 0 1 1 4.03 4.03l-8.06 8.08"/><path d="M7.07 14.94c-1.66 0-3 1.35-3 3.02 0 1.33-2.5 1.52-2 2.02 1.08 1.35 2.22 2.02 3 2.02 2.22 0 4.14-1.15 4.14-3.15C9.21 16.9 7.07 17.3 7.07 14.94z"/></svg>
                  DANH MỤC
                </h3>
                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={() => { setSelectedCategories([]); setPage(1); }}
                    className="px-3 py-1.5 rounded-full text-xs font-semibold transition-all"
                    style={{
                      background: selectedCategories.length === 0 ? "var(--accent-primary)" : "rgba(255,255,255,0.05)",
                      color: selectedCategories.length === 0 ? "#fff" : "var(--text-muted)",
                      boxShadow: selectedCategories.length === 0 ? "0 0 12px rgba(220,38,38,0.4)" : "none"
                    }}
                  >
                    Tất cả
                  </button>
                  {STANDARD_CATEGORIES.map((cat, i) => {
                    const isSelected = selectedCategories.includes(cat);
                    return (
                      <button
                        key={i}
                        onClick={() => {
                          if (isSelected) {
                            setSelectedCategories(selectedCategories.filter(c => c !== cat));
                          } else {
                            setSelectedCategories([...selectedCategories, cat]);
                          }
                          setPage(1);
                        }}
                        className="px-3 py-1.5 rounded-full text-xs font-semibold transition-all"
                        style={{
                          background: isSelected ? "var(--gradient-primary)" : "rgba(255,255,255,0.05)",
                          color: isSelected ? "#fff" : "var(--text-muted)",
                          border: isSelected ? "1px solid transparent" : "1px solid var(--border-color)",
                          boxShadow: isSelected ? "0 0 12px rgba(220,38,38,0.4)" : "none"
                        }}
                      >
                        {cat}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Sentiment Filter */}
              <div className="glass-card p-6">
                <h3 className="text-sm font-bold mb-4 flex items-center gap-2" style={{ color: "var(--text-secondary)" }}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                  CẢM XÚC
                </h3>
                <select className="input-dark text-sm"
                  value={sentimentFilter}
                  onChange={(e) => { setSentimentFilter(e.target.value); setPage(1); }}>
                  <option value="">Tất cả</option>
                  {sentiments.map((s, i) => (
                    <option key={i} value={s.video_sentiment}>
                      {s.video_sentiment} ({s.count})
                    </option>
                  ))}
                </select>
              </div>

              {/* Viral Slider */}
              <div className="glass-card p-6">
                <h3 className="text-sm font-bold mb-4 flex items-center gap-2" style={{ color: "var(--text-secondary)" }}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/></svg>
                  MIN VIRAL %
                </h3>
                <input
                  type="range" min="0" max="100" step="5"
                  value={minViral}
                  onChange={(e) => { setMinViral(Number(e.target.value)); setPage(1); }}
                  className="w-full accent-red-500"
                />
                <div className="text-center text-sm font-bold mt-2" style={{ color: "var(--accent-primary)" }}>
                  {minViral}%+
                </div>
              </div>

              {/* Sentiment Distribution */}
              {sentiments.length > 0 && (
                <div className="glass-card p-6">
                  <h3 className="text-sm font-bold mb-4 flex items-center gap-2" style={{ color: "var(--text-secondary)" }}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/></svg>
                    PHÂN BỔ CẢM XÚC
                  </h3>
                  {sentiments.map((s, i) => {
                    const total = sentiments.reduce((sum, x) => sum + (x.count || 0), 0);
                    const pct = total > 0 ? ((s.count || 0) / total * 100) : 0;
                    return (
                      <div key={i} className="mb-4 last:mb-0">
                        <div className="flex justify-between text-xs mb-1.5 font-medium">
                          <span style={{ color: "var(--text-secondary)" }}>{s.video_sentiment}</span>
                          <span style={{ color: sentimentColors[s.video_sentiment] || "var(--text-muted)" }}>
                            {pct.toFixed(0)}%
                          </span>
                        </div>
                        <div className="w-full h-1.5 rounded-full" style={{ background: "rgba(255,255,255,0.08)" }}>
                          <div className="h-full rounded-full transition-all duration-500"
                            style={{
                              width: `${pct}%`,
                              background: sentimentColors[s.video_sentiment] || "var(--text-muted)",
                            }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Top Keywords */}
              {keywords.length > 0 && (
                <div className="glass-card p-6">
                  <h3 className="text-sm font-bold mb-4 flex items-center gap-2" style={{ color: "var(--text-secondary)" }}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"/></svg>
                    TỪ KHÓA HOT
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {keywords.slice(0, 15).map((kw, i) => (
                      <span key={i} className="keyword-tag cursor-pointer px-3 py-1 rounded-md" style={{ background: "rgba(255,255,255,0.05)" }}
                        onClick={() => { setSearchQuery(kw.keyword); setPage(1); }}>
                        {kw.keyword} <span className="opacity-60 ml-0.5 text-[0.65rem]">{kw.count}</span>
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* ═══ Main Content: Table ═══ */}
            <div className="lg:col-span-3">
              {/* Info bar */}
              <div className="glass-card p-4 flex items-center justify-between mb-6 flex-wrap gap-2">
                <span className="text-sm font-medium" style={{ color: "var(--text-muted)" }}>
                  Hiển thị <span className="text-white">{videos.length}</span> trên tổng số <span className="text-white">{formatBigNumber(totalVideos)}</span> video
                </span>
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium" style={{ color: "var(--text-muted)" }}>Số video:</span>
                    <select 
                      className="input-dark text-sm" 
                      style={{ width: "65px", padding: "4px 8px", minHeight: "32px", fontSize: "13px" }} 
                      value={perPage} 
                      onChange={(e) => { setPerPage(Number(e.target.value)); setPage(1); }}
                    >
                      {[5, 10, 20, 50].map(v => <option key={v} value={v}>{v}</option>)}
                    </select>
                  </div>
                  <span className="text-sm font-medium" style={{ color: "var(--text-muted)" }}>
                    Trang <span className="text-white">{page}</span> / {totalPages}
                  </span>
                </div>
              </div>

              {loading ? (
                <div className="space-y-4">
                  {[...Array(8)].map((_, i) => (
                    <div key={i} className="skeleton h-16 w-full rounded-xl" />
                  ))}
                </div>
              ) : videos.length === 0 ? (
                <div className="glass-card p-16 text-center">
                  <div className="text-5xl mb-4 opacity-50">🔍</div>
                  <p className="text-lg font-medium" style={{ color: "var(--text-secondary)" }}>Không tìm thấy video nào phù hợp.</p>
                  <button onClick={() => { setSearchQuery(""); setSelectedCategories([]); setSentimentFilter(""); setMinViral(0); setPage(1); }} className="btn-outline mt-6">
                    Xóa tất cả bộ lọc
                  </button>
                </div>
              ) : (
                <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border-color)", boxShadow: "0 4px 20px rgba(0,0,0,0.4)" }}>
                  <VideoTable
                    videos={videos}
                    sortBy={sortBy}
                    sortOrder={sortOrder}
                    onSort={handleSort}
                  />
                </div>
              )}

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-center gap-2 mt-10">
                  <button
                    onClick={() => setPage(Math.max(1, page - 1))}
                    disabled={page === 1}
                    className="btn-outline text-sm disabled:opacity-30 disabled:cursor-not-allowed"
                  >
                    Trước
                  </button>
                  <div className="flex gap-1.5 hidden sm:flex">
                    {getPaginationPages(page, totalPages).map((p, i) => (
                      p === '...' ? (
                        <span key={`dots-${i}`} className="w-10 h-10 flex items-center justify-center text-sm font-bold"
                          style={{ color: "var(--text-muted)" }}>...</span>
                      ) : (
                        <button
                          key={p}
                          onClick={() => setPage(p)}
                          className={`w-10 h-10 rounded-xl text-sm font-bold transition-all`}
                          style={{
                            background: p === page ? "transparent" : "rgba(255,255,255,0.03)",
                            color: p === page ? "var(--accent-primary)" : "var(--text-muted)",
                            border: p === page ? "1px solid var(--accent-primary)" : "1px solid rgba(255,255,255,0.1)",
                            boxShadow: "none",
                          }}
                        >
                          {p}
                        </button>
                      )
                    ))}
                  </div>
                  <button
                    onClick={() => setPage(Math.min(totalPages, page + 1))}
                    disabled={page === totalPages}
                    className="btn-outline text-sm disabled:opacity-30 disabled:cursor-not-allowed"
                  >
                    Sau
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}
