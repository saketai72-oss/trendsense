export default function Footer() {
  return (
    <footer className="border-t mt-20" style={{ borderColor: "var(--border-color)", background: "var(--bg-secondary)" }}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-12">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {/* Brand */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center text-sm"
                style={{ background: "var(--gradient-primary)" }}>
                🎯
              </div>
              <span className="font-bold text-lg gradient-text">TrendSense</span>
            </div>
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>
              Hệ thống AI phân tích xu hướng và dự báo viral TikTok. Pipeline: Selenium → Supabase → Modal AI → React.
            </p>
          </div>

          {/* Links */}
          <div>
            <h4 className="font-semibold mb-3 text-sm" style={{ color: "var(--text-secondary)" }}>Liên Kết</h4>
            <div className="flex flex-col gap-2">
              {[
                { href: "/", label: "Trang Chủ" },
                { href: "/dashboard", label: "Dashboard" },
                { href: "/analyze", label: "Phân Tích Video" },
              ].map((item) => (
                <a key={item.href} href={item.href}
                  className="text-sm transition-colors no-underline"
                  style={{ color: "var(--text-muted)" }}
                  onMouseEnter={(e) => e.target.style.color = "var(--accent-primary)"}
                  onMouseLeave={(e) => e.target.style.color = "var(--text-muted)"}>
                  {item.label}
                </a>
              ))}
            </div>
          </div>

          {/* Tech Stack */}
          <div>
            <h4 className="font-semibold mb-3 text-sm" style={{ color: "var(--text-secondary)" }}>Công Nghệ</h4>
            <div className="flex flex-wrap gap-2">
              {["Next.js", "FastAPI", "Supabase", "Modal", "Groq", "Whisper", "BLIP"].map((tech) => (
                <span key={tech} className="keyword-tag">{tech}</span>
              ))}
            </div>
          </div>
        </div>

        <div className="border-t mt-8 pt-6 text-center" style={{ borderColor: "var(--border-color)" }}>
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            © 2026 TrendSense — AI-Powered Viral Prediction System
          </p>
        </div>
      </div>
    </footer>
  );
}
