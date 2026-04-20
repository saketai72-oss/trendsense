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
        borderColor: "var(--border-color)",
      }}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 w-full">
        <div className="flex items-center justify-between md:grid md:grid-cols-12 md:gap-4 h-16">
          {/* Logo */}
          <Link href="/" className="md:col-start-3 md:col-span-3 flex items-center gap-2 no-underline">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center text-lg"
              style={{ background: "var(--gradient-primary)" }}>
              🎯
            </div>
            <span className="font-bold text-lg gradient-text">TrendSense</span>
          </Link>

          {/* Desktop Nav */}
          <div className="hidden md:flex md:col-span-4 items-center gap-8 justify-center">
            {[
              { href: "/", label: "Trang Chủ" },
              { href: "/dashboard", label: "Dashboard" },
              { href: "/analyze", label: "Phân Tích Video" },
            ].map((item) => (
              <Link key={item.href} href={item.href}
                className="px-4 py-2 rounded-lg text-sm font-medium no-underline transition-all duration-200"
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
          <div className="hidden md:flex md:col-span-2 items-center gap-3 justify-end">
            <Link href="/analyze" className="btn-primary text-sm no-underline">
              🚀 Dự Báo Ngay
            </Link>
          </div>

          {/* Mobile toggle */}
          <button className="md:hidden p-2 rounded-lg"
            style={{ color: "var(--text-primary)" }}
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
          <div className="md:hidden pb-4 border-t" style={{ borderColor: "var(--border-color)" }}>
            <div className="flex flex-col gap-1 pt-3">
              {[
                { href: "/", label: "Trang Chủ" },
                { href: "/dashboard", label: "Dashboard" },
                { href: "/analyze", label: "Phân Tích Video" },
              ].map((item) => (
                <Link key={item.href} href={item.href}
                  className="px-4 py-2 rounded-lg text-sm no-underline"
                  style={{ color: "var(--text-secondary)" }}
                  onClick={() => setIsOpen(false)}>
                  {item.label}
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>
    </nav>
  );
}
