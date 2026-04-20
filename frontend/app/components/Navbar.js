"use client";
import { useState } from "react";
import Link from "next/link";

export default function Navbar() {
  const [isOpen, setIsOpen] = useState(false);

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
                <circle cx="12" cy="12" r="10"/>
                <circle cx="12" cy="12" r="6"/>
                <circle cx="12" cy="12" r="2"/>
              </svg>
            </div>
            <span className="font-bold text-xl gradient-text tracking-tight">TrendSense</span>
          </Link>

          {/* Desktop Nav */}
          <div className="hidden md:flex md:col-span-6 xl:col-span-4 items-center gap-6 justify-center">
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

          {/* CTA Button */}
          <div className="hidden md:flex md:col-span-3 xl:col-span-2 items-center justify-end">
            <Link href="/analyze" className="btn-primary text-sm no-underline flex items-center gap-2">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
              </svg>
              Dự Báo Ngay
            </Link>
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
              <div className="mt-2 px-4">
                <Link href="/analyze" className="btn-primary text-sm no-underline flex items-center justify-center gap-2 w-full text-center"
                   onClick={() => setIsOpen(false)}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
                  </svg>
                  Dự Báo Ngay
                </Link>
              </div>
            </div>
          </div>
        )}
      </div>
    </nav>
  );
}
