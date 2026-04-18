"use client";
import { useState, useEffect, useCallback } from "react";
import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import StatCard from "../components/StatCard";
import VideoTable from "../components/VideoTable";
import { getStats, getVideos, getCategories, getKeywords, getSentiments } from "../lib/api";

export default function DashboardPage() {
  const [stats, setStats] = useState(null);
  const [videos, setVideos] = useState([]);
  const [totalVideos, setTotalVideos] = useState(0);
  const [page, setPage] = useState(1);
  const [perPage] = useState(20);
  const [totalPages, setTotalPages] = useState(1);
  const [sortBy, setSortBy] = useState("viral_probability");
  const [sortOrder, setSortOrder] = useState("desc");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [sentimentFilter, setSentimentFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [minViral, setMinViral] = useState(0);
  const [categories, setCategories] = useState([]);
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
        const [s, c, kw, se] = await Promise.all([
          getStats(), getCategories(), getKeywords(20), getSentiments(),
        ]);
        setStats(s);
        setCategories(c || []);
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
        category: categoryFilter, sentiment: sentimentFilter,
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
  }, [page, perPage, sortBy, sortOrder, categoryFilter, sentimentFilter, searchQuery, minViral]);

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
      <main className="w-full pb-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 w-full">
          {/* Header */}
          <div className="mb-8">
            <h1 className="text-3xl font-bold">📊 Dashboard</h1>
            <p className="mt-1" style={{ color: "var(--text-muted)" }}>
              Bảng điều khiển toàn diện — Phân tích xu hướng & dự báo viral
            </p>
          </div>

          {/* Stats Row */}
          {stats && (
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-8">
              <StatCard icon="📹" label="Tổng Video" value={formatBigNumber(stats.total_videos)} delay={0} />
              <StatCard icon="👁️" label="Tổng Views" value={formatBigNumber(stats.total_views)} color="var(--accent-cyan)" delay={50} />
              <StatCard icon="❤️" label="Tổng Likes" value={formatBigNumber(stats.total_likes)} color="var(--accent-pink)" delay={100} />
              <StatCard icon="🔥" label="Video Viral" value={stats.viral_count} color="var(--accent-red)" delay={150} />
              <StatCard icon="📈" label="Avg Engage" value={(stats.avg_engagement || 0).toFixed(1) + "%"} color="var(--accent-green)" delay={200} />
              <StatCard icon="📅" label="Ngày Thu Thập" value={stats.scrape_days} delay={250} />
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            {/* ═══ Sidebar: Filters ═══ */}
            <div className="lg:col-span-1 space-y-5">
              {/* Search */}
              <div className="glass-card p-5">
                <h3 className="text-sm font-semibold mb-3" style={{ color: "var(--text-secondary)" }}>🔍 Tìm Kiếm</h3>
                <form onSubmit={handleSearch}>
                  <input
                    type="text"
                    placeholder="Hashtag, từ khóa..."
                    className="input-dark"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </form>
              </div>

              {/* Category Filter */}
              <div className="glass-card p-5">
                <h3 className="text-sm font-semibold mb-3" style={{ color: "var(--text-secondary)" }}>🏷️ Danh Mục</h3>
                <select className="input-dark"
                  value={categoryFilter}
                  onChange={(e) => { setCategoryFilter(e.target.value); setPage(1); }}>
                  <option value="">Tất cả</option>
                  {categories.map((c, i) => (
                    <option key={i} value={c.category}>{c.category} ({c.count})</option>
                  ))}
                </select>
              </div>

              {/* Sentiment Filter */}
              <div className="glass-card p-5">
                <h3 className="text-sm font-semibold mb-3" style={{ color: "var(--text-secondary)" }}>💭 Cảm Xúc</h3>
                <select className="input-dark"
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
              <div className="glass-card p-5">
                <h3 className="text-sm font-semibold mb-3" style={{ color: "var(--text-secondary)" }}>🔥 Min Viral %</h3>
                <input
                  type="range" min="0" max="100" step="5"
                  value={minViral}
                  onChange={(e) => { setMinViral(Number(e.target.value)); setPage(1); }}
                  className="w-full accent-purple-500"
                />
                <div className="text-center text-sm font-semibold mt-1" style={{ color: "var(--accent-primary)" }}>
                  {minViral}%+
                </div>
              </div>

              {/* Sentiment Distribution */}
              {sentiments.length > 0 && (
                <div className="glass-card p-5">
                  <h3 className="text-sm font-semibold mb-3" style={{ color: "var(--text-secondary)" }}>
                    📊 Phân Bổ Cảm Xúc
                  </h3>
                  {sentiments.map((s, i) => {
                    const total = sentiments.reduce((sum, x) => sum + (x.count || 0), 0);
                    const pct = total > 0 ? ((s.count || 0) / total * 100) : 0;
                    return (
                      <div key={i} className="mb-3">
                        <div className="flex justify-between text-xs mb-1">
                          <span style={{ color: "var(--text-secondary)" }}>{s.video_sentiment}</span>
                          <span style={{ color: sentimentColors[s.video_sentiment] || "var(--text-muted)" }}>
                            {pct.toFixed(0)}%
                          </span>
                        </div>
                        <div className="w-full h-2 rounded-full" style={{ background: "rgba(255,255,255,0.05)" }}>
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
                <div className="glass-card p-5">
                  <h3 className="text-sm font-semibold mb-3" style={{ color: "var(--text-secondary)" }}>
                    ☁️ Từ Khóa Hot
                  </h3>
                  <div className="flex flex-wrap gap-1">
                    {keywords.slice(0, 15).map((kw, i) => (
                      <span key={i} className="keyword-tag cursor-pointer"
                        onClick={() => { setSearchQuery(kw.keyword); setPage(1); }}>
                        {kw.keyword} ({kw.count})
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* ═══ Main Content: Table ═══ */}
            <div className="lg:col-span-3">
              {/* Info bar */}
              <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
                <span className="text-sm" style={{ color: "var(--text-muted)" }}>
                  Hiển thị {videos.length} / {totalVideos} video — Trang {page}/{totalPages}
                </span>
              </div>

              {loading ? (
                <div className="space-y-3">
                  {[...Array(8)].map((_, i) => (
                    <div key={i} className="skeleton h-14 w-full" />
                  ))}
                </div>
              ) : videos.length === 0 ? (
                <div className="glass-card p-12 text-center">
                  <div className="text-4xl mb-4">🔍</div>
                  <p style={{ color: "var(--text-secondary)" }}>Không tìm thấy video nào phù hợp.</p>
                </div>
              ) : (
                <VideoTable
                  videos={videos}
                  sortBy={sortBy}
                  sortOrder={sortOrder}
                  onSort={handleSort}
                />
              )}

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-center gap-2 mt-6">
                  <button
                    onClick={() => setPage(Math.max(1, page - 1))}
                    disabled={page === 1}
                    className="btn-outline text-sm disabled:opacity-30"
                  >
                    ← Trước
                  </button>
                  {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                    let p;
                    if (totalPages <= 5) {
                      p = i + 1;
                    } else if (page <= 3) {
                      p = i + 1;
                    } else if (page >= totalPages - 2) {
                      p = totalPages - 4 + i;
                    } else {
                      p = page - 2 + i;
                    }
                    return (
                      <button
                        key={p}
                        onClick={() => setPage(p)}
                        className="w-9 h-9 rounded-lg text-sm font-semibold transition-all"
                        style={{
                          background: p === page ? "var(--gradient-primary)" : "transparent",
                          color: p === page ? "white" : "var(--text-muted)",
                          border: p === page ? "none" : "1px solid var(--border-color)",
                        }}
                      >
                        {p}
                      </button>
                    );
                  })}
                  <button
                    onClick={() => setPage(Math.min(totalPages, page + 1))}
                    disabled={page === totalPages}
                    className="btn-outline text-sm disabled:opacity-30"
                  >
                    Sau →
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
