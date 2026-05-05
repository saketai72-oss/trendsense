"use client";
import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { useAuth } from "../lib/AuthContext";

export default function Navbar() {
  const [isOpen, setIsOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const { user, isAuthenticated, logout } = useAuth();
  const menuRef = useRef(null);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false);
      }
    }
    if (menuOpen) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [menuOpen]);

  const handleLogout = async () => {
    await logout();
    setMenuOpen(false);
    setIsOpen(false);
  };

  const userInitial = user?.display_name?.[0] || user?.email?.[0]?.toUpperCase() || "?";

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 border-b"
      style={{
        background: "rgba(10, 11, 26, 0.85)",
        backdropFilter: "blur(16px)",
        WebkitBackdropFilter: "blur(16px)",
        borderColor: "var(--border-color)",
      }}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 w-full">
        <div className="flex items-center justify-between md:grid md:grid-cols-12 md:gap-4 h-16 sm:h-20">
          {/* Logo */}
          <Link href="/" className="md:col-start-1 md:col-span-3 xl:col-start-3 xl:col-span-3 flex items-center gap-2.5 no-underline">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center text-lg"
              style={{ background: "var(--gradient-primary)", boxShadow: "0 2px 10px rgba(220, 38, 38, 0.3)" }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <circle cx="12" cy="12" r="6" />
                <circle cx="12" cy="12" r="2" />
              </svg>
            </div>
            <span className="font-bold text-xl gradient-text tracking-tight">TrendSense</span>
          </Link>

          {/* Desktop Nav */}
          <div className="hidden md:flex md:col-span-5 xl:col-span-4 items-center gap-6 justify-center">
            {[
              { href: "/", label: "Trang Chủ" },
              { href: "/dashboard", label: "Dashboard" },
              { href: "/analyze", label: "Phân Tích Video" },
            ].map((item) => (
              <Link key={item.href} href={item.href}
                className="px-4 py-2.5 rounded-lg text-sm font-semibold no-underline transition-all duration-200"
                style={{ color: "var(--text-secondary)" }}
                onMouseEnter={(e) => {
                  e.target.style.color = "var(--text-primary)";
                  e.target.style.background = "rgba(220, 38, 38, 0.1)";
                }}
                onMouseLeave={(e) => {
                  e.target.style.color = "var(--text-secondary)";
                  e.target.style.background = "transparent";
                }}>
                {item.label}
              </Link>
            ))}
          </div>

          {/* Desktop Auth / CTA */}
          <div className="hidden md:flex md:col-span-4 xl:col-span-3 items-center justify-end gap-3">
            {isAuthenticated ? (
              /* User Menu */
              <div className="relative" ref={menuRef}>
                <button onClick={() => setMenuOpen(!menuOpen)}
                  className="flex items-center gap-2.5 px-3 py-2 rounded-xl transition-all duration-200 cursor-pointer"
                  style={{
                    background: menuOpen ? "rgba(220, 38, 38, 0.1)" : "transparent",
                    border: "1px solid rgba(255,255,255,0.08)",
                  }}
                  onMouseEnter={(e) => { if (!menuOpen) e.currentTarget.style.borderColor = "rgba(255,255,255,0.15)"; }}
                  onMouseLeave={(e) => { if (!menuOpen) e.currentTarget.style.borderColor = "rgba(255,255,255,0.08)"; }}>
                  <div className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold"
                    style={{ background: "var(--gradient-primary)", color: "white" }}>
                    {userInitial}
                  </div>
                  <span className="text-sm font-medium max-w-[120px] truncate" style={{ color: "var(--text-primary)" }}>
                    {user?.display_name || user?.email?.split("@")[0]}
                  </span>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                    style={{ color: "var(--text-muted)", transform: menuOpen ? "rotate(180deg)" : "none", transition: "transform 0.2s" }}>
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                </button>

                {menuOpen && (
                  <div className="absolute right-0 top-full mt-2 w-56 rounded-xl overflow-hidden"
                    style={{
                      background: "var(--bg-card)",
                      border: "1px solid rgba(255,255,255,0.08)",
                      boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
                    }}>
                    <div className="px-4 py-3 border-b" style={{ borderColor: "rgba(255,255,255,0.06)" }}>
                      <p className="text-sm font-semibold truncate" style={{ color: "var(--text-primary)" }}>
                        {user?.display_name || "User"}
                      </p>
                      <p className="text-xs truncate" style={{ color: "var(--text-muted)" }}>{user?.email}</p>
                    </div>
                    <div className="py-1">
                      <Link href="/analyze" onClick={() => setMenuOpen(false)}
                        className="flex items-center gap-3 px-4 py-2.5 text-sm no-underline transition-colors"
                        style={{ color: "var(--text-secondary)" }}
                        onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.04)"; e.currentTarget.style.color = "var(--text-primary)"; }}
                        onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--text-secondary)"; }}>
                        🎬 Phân tích video
                      </Link>
                      <button onClick={handleLogout}
                        className="flex items-center gap-3 px-4 py-2.5 text-sm w-full text-left transition-colors cursor-pointer"
                        style={{ color: "var(--accent-red)", background: "transparent", border: "none" }}
                        onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(239,68,68,0.08)"; }}
                        onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}>
                        🚪 Đăng xuất
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              /* Login / Register Buttons */
              <>
                <Link href="/login"
                  className="px-4 py-2 rounded-lg text-sm font-semibold no-underline transition-all duration-200"
                  style={{ color: "var(--text-secondary)" }}
                  onMouseEnter={(e) => { e.target.style.color = "var(--text-primary)"; }}
                  onMouseLeave={(e) => { e.target.style.color = "var(--text-secondary)"; }}>
                  Đăng nhập
                </Link>
                <Link href="/register" className="btn-primary text-sm no-underline flex items-center gap-2">
                  Đăng ký
                </Link>
              </>
            )}
          </div>

          {/* Mobile toggle */}
          <button className="md:hidden p-2 rounded-lg transition-colors"
            style={{ color: "var(--text-primary)" }}
            onMouseEnter={(e) => e.target.style.background = "rgba(255,255,255,0.05)"}
            onMouseLeave={(e) => e.target.style.background = "transparent"}
            onClick={() => setIsOpen(!isOpen)}>
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              {isOpen ? (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>
        </div>

        {/* Mobile menu */}
        {isOpen && (
          <div className="md:hidden pb-5 pt-2 border-t" style={{ borderColor: "rgba(255,255,255,0.06)" }}>
            <div className="flex flex-col gap-2">
              {[
                { href: "/", label: "Trang Chủ" },
                { href: "/dashboard", label: "Dashboard" },
                { href: "/analyze", label: "Phân Tích Video" },
              ].map((item) => (
                <Link key={item.href} href={item.href}
                  className="px-4 py-3 rounded-lg text-sm font-semibold no-underline transition-all"
                  style={{ color: "var(--text-secondary)", background: "rgba(255,255,255,0.02)" }}
                  onClick={() => setIsOpen(false)}>
                  {item.label}
                </Link>
              ))}

              {/* Mobile Auth */}
              <div className="mt-2 px-4 pt-3 border-t" style={{ borderColor: "rgba(255,255,255,0.06)" }}>
                {isAuthenticated ? (
                  <div className="space-y-2">
                    <div className="flex items-center gap-3 px-3 py-2">
                      <div className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold"
                        style={{ background: "var(--gradient-primary)", color: "white" }}>
                        {userInitial}
                      </div>
                      <div>
                        <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                          {user?.display_name || user?.email?.split("@")[0]}
                        </p>
                        <p className="text-xs" style={{ color: "var(--text-muted)" }}>{user?.email}</p>
                      </div>
                    </div>
                    <button onClick={handleLogout}
                      className="w-full flex items-center justify-center gap-2 h-11 rounded-xl text-sm font-semibold cursor-pointer"
                      style={{
                        background: "rgba(239,68,68,0.1)",
                        border: "1px solid rgba(239,68,68,0.2)",
                        color: "var(--accent-red)",
                      }}>
                      🚪 Đăng xuất
                    </button>
                  </div>
                ) : (
                  <div className="flex gap-3">
                    <Link href="/login"
                      className="flex-1 flex items-center justify-center h-11 rounded-xl text-sm font-semibold no-underline"
                      style={{
                        background: "rgba(255,255,255,0.05)",
                        border: "1px solid rgba(255,255,255,0.1)",
                        color: "var(--text-primary)",
                      }}
                      onClick={() => setIsOpen(false)}>
                      Đăng nhập
                    </Link>
                    <Link href="/register"
                      className="flex-1 btn-primary text-sm no-underline flex items-center justify-center h-11"
                      onClick={() => setIsOpen(false)}>
                      Đăng ký
                    </Link>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </nav>
  );
}
