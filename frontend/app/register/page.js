"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import { useAuth } from "../lib/AuthContext";

export default function RegisterPage() {
  const router = useRouter();
  const { register, loginWithGoogle, loginWithGithub, isAuthenticated } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (typeof window !== "undefined" && isAuthenticated) {
    router.replace("/analyze");
    return null;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    if (!email || !password) {
      setError("Vui lòng nhập email và mật khẩu.");
      return;
    }
    if (password.length < 8) {
      setError("Mật khẩu phải có ít nhất 8 ký tự.");
      return;
    }
    if (!/[A-Za-z]/.test(password) || !/\d/.test(password)) {
      setError("Mật khẩu phải chứa ít nhất 1 chữ cái và 1 chữ số.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Mật khẩu xác nhận không khớp.");
      return;
    }

    setLoading(true);
    try {
      await register(email, password, displayName || null);
      router.push("/analyze");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Navbar />
      <main className="pb-10 min-h-screen w-full flex items-center justify-center">
        <div className="w-full max-w-md mx-auto px-4">
          {/* Header */}
          <div className="text-center mb-8">
            <div className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4"
              style={{ background: "var(--gradient-primary)", boxShadow: "0 4px 20px rgba(220, 38, 38, 0.3)" }}>
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="8.5" cy="7" r="4" /><line x1="20" y1="8" x2="20" y2="14" /><line x1="23" y1="11" x2="17" y2="11" />
              </svg>
            </div>
            <h1 className="text-2xl font-bold">Tạo Tài Khoản</h1>
            <p className="text-sm mt-2" style={{ color: "var(--text-muted)" }}>
              Đăng ký để lưu và theo dõi các video phân tích của bạn.
            </p>
          </div>

          {/* Register Form */}
          <div className="glass-card neon-border p-8">
            <form onSubmit={handleSubmit} className="space-y-5">
              {/* Display Name */}
              <div>
                <label className="text-sm font-semibold block mb-2" style={{ color: "var(--text-secondary)" }}>
                  👤 Tên hiển thị <span className="font-normal" style={{ color: "var(--text-muted)" }}>(tùy chọn)</span>
                </label>
                <input
                  type="text"
                  className="input-dark"
                  placeholder="Nguyễn Văn A"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  disabled={loading}
                  maxLength={100}
                />
              </div>

              {/* Email */}
              <div>
                <label className="text-sm font-semibold block mb-2" style={{ color: "var(--text-secondary)" }}>
                  📧 Email
                </label>
                <input
                  type="email"
                  className="input-dark"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={loading}
                  autoComplete="email"
                />
              </div>

              {/* Password */}
              <div>
                <label className="text-sm font-semibold block mb-2" style={{ color: "var(--text-secondary)" }}>
                  🔒 Mật khẩu
                </label>
                <input
                  type="password"
                  className="input-dark"
                  placeholder="Ít nhất 8 ký tự, có chữ và số"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={loading}
                  autoComplete="new-password"
                />
              </div>

              {/* Confirm Password */}
              <div>
                <label className="text-sm font-semibold block mb-2" style={{ color: "var(--text-secondary)" }}>
                  🔒 Xác nhận mật khẩu
                </label>
                <input
                  type="password"
                  className="input-dark"
                  placeholder="Nhập lại mật khẩu"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  disabled={loading}
                  autoComplete="new-password"
                />
              </div>

              {error && (
                <div className="rounded-lg p-3 text-sm"
                  style={{ background: "rgba(239,68,68,0.1)", color: "var(--accent-red)", border: "1px solid rgba(239,68,68,0.2)" }}>
                  ⚠️ {error}
                </div>
              )}

              <button type="submit" className="btn-primary w-full text-base h-[52px] flex items-center justify-center gap-2"
                disabled={loading}>
                {loading ? (
                  <span className="flex items-center gap-2">
                    <svg className="animate-spin w-5 h-5" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" /></svg>
                    Đang tạo tài khoản...
                  </span>
                ) : "Tạo Tài Khoản"}
              </button>
            </form>

            {/* Divider */}
            <div className="flex items-center gap-4 my-6">
              <div className="flex-1 h-px" style={{ background: "rgba(255,255,255,0.08)" }} />
              <span className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>hoặc</span>
              <div className="flex-1 h-px" style={{ background: "rgba(255,255,255,0.08)" }} />
            </div>

            {/* OAuth Buttons */}
            <div className="space-y-3">
              <button onClick={loginWithGoogle} disabled={loading}
                className="w-full flex items-center justify-center gap-3 h-12 rounded-xl text-sm font-semibold transition-all duration-200 cursor-pointer"
                style={{
                  background: "rgba(255,255,255,0.05)",
                  border: "1px solid rgba(255,255,255,0.1)",
                  color: "var(--text-primary)",
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.08)"; e.currentTarget.style.borderColor = "rgba(255,255,255,0.2)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.05)"; e.currentTarget.style.borderColor = "rgba(255,255,255,0.1)"; }}>
                <svg width="20" height="20" viewBox="0 0 24 24">
                  <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/>
                  <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                  <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                  <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                </svg>
                Đăng ký với Google
              </button>

              <button onClick={loginWithGithub} disabled={loading}
                className="w-full flex items-center justify-center gap-3 h-12 rounded-xl text-sm font-semibold transition-all duration-200 cursor-pointer"
                style={{
                  background: "rgba(255,255,255,0.05)",
                  border: "1px solid rgba(255,255,255,0.1)",
                  color: "var(--text-primary)",
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.08)"; e.currentTarget.style.borderColor = "rgba(255,255,255,0.2)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.05)"; e.currentTarget.style.borderColor = "rgba(255,255,255,0.1)"; }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="var(--text-primary)">
                  <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0112 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z"/>
                </svg>
                Đăng ký với GitHub
              </button>
            </div>

            {/* Login link */}
            <p className="text-center text-sm mt-6" style={{ color: "var(--text-muted)" }}>
              Đã có tài khoản?{" "}
              <Link href="/login" className="font-semibold no-underline" style={{ color: "var(--accent-primary)" }}>
                Đăng nhập
              </Link>
            </p>
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}
