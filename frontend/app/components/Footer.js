export default function Footer() {
  return (
    <footer className="border-t mt-24" style={{ borderColor: "var(--border-color)", background: "var(--bg-secondary)" }}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-16">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-12">
          {/* Brand */}
          <div>
            <div className="flex items-center gap-2 mb-4">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center text-sm"
                style={{ background: "var(--gradient-primary)" }}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10"/>
                  <circle cx="12" cy="12" r="6"/>
                  <circle cx="12" cy="12" r="2"/>
                </svg>
              </div>
              <span className="font-bold text-lg gradient-text" style={{ letterSpacing: "-0.01em" }}>TrendSense</span>
            </div>
            <p className="text-sm leading-relaxed" style={{ color: "var(--text-muted)", opacity: 0.8 }}>
              Hệ thống AI phân tích xu hướng và dự báo viral TikTok. Pipeline: Selenium → Supabase → Modal AI → React.
            </p>
          </div>

          {/* Links */}
          <div>
            <h4 className="font-semibold mb-4 text-sm tracking-wide uppercase" style={{ color: "var(--text-secondary)" }}>Liên Kết</h4>
            <div className="flex flex-col gap-3">
              {[
                { href: "/", label: "Trang Chủ" },
                { href: "/dashboard", label: "Dashboard" },
                { href: "/analyze", label: "Phân Tích Video" },
              ].map((item) => (
                <a key={item.href} href={item.href}
                  className="text-sm transition-colors no-underline font-medium"
                  style={{ color: "var(--text-muted)", opacity: 0.85 }}
                  onMouseEnter={(e) => {
                    e.target.style.color = "var(--accent-primary)";
                    e.target.style.opacity = "1";
                  }}
                  onMouseLeave={(e) => {
                    e.target.style.color = "var(--text-muted)";
                    e.target.style.opacity = "0.85";
                  }}>
                  {item.label}
                </a>
              ))}
            </div>
          </div>

          {/* Tech Stack */}
          <div>
            <h4 className="font-semibold mb-4 text-sm tracking-wide uppercase" style={{ color: "var(--text-secondary)" }}>Công Nghệ</h4>
            <div className="flex flex-wrap gap-2">
              {["Next.js", "FastAPI", "Supabase", "Modal", "Groq", "Whisper", "BLIP"].map((tech) => (
                <span key={tech} className="tech-tag">{tech}</span>
              ))}
            </div>
          </div>
        </div>

        <div className="border-t mt-12 pt-8 text-center" style={{ borderColor: "rgba(255,255,255,0.06)" }}>
          <p className="text-xs font-medium" style={{ color: "var(--text-muted)", opacity: 0.6 }}>
            © 2026 TrendSense — AI-Powered Viral Prediction System
          </p>
        </div>
      </div>
    </footer>
  );
}
