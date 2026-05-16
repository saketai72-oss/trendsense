"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "../lib/AuthContext";
import {
  createPayment,
  checkPaymentStatus,
  getSubscriptionStatus,
} from "../lib/api";
import Navbar from "../components/Navbar";

// ── Quota progress bar ────────────────────────────────────────────────────────
function QuotaBar({ used, limit }) {
  const pct = limit > 0 ? Math.min(100, (used / limit) * 100) : 0;
  const color = pct >= 100 ? "#ef4444" : pct >= 70 ? "#f59e0b" : "#10b981";
  return (
    <div style={{ width: "100%" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          marginBottom: 6,
          fontSize: 13,
          color: "var(--text-secondary)",
        }}
      >
        <span>Đã dùng hôm nay</span>
        <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>
          {used}/{limit} video
        </span>
      </div>
      <div
        style={{
          height: 8,
          borderRadius: 99,
          background: "rgba(255,255,255,0.07)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${pct}%`,
            borderRadius: 99,
            background: color,
            transition: "width 0.6s ease",
          }}
        />
      </div>
    </div>
  );
}

// ── Copy button ───────────────────────────────────────────────────────────────
function CopyBtn({ text }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {}
  };
  return (
    <button
      onClick={copy}
      style={{
        padding: "4px 10px",
        borderRadius: 6,
        border: "1px solid rgba(255,255,255,0.12)",
        background: copied ? "rgba(16,185,129,0.15)" : "rgba(255,255,255,0.06)",
        color: copied ? "#10b981" : "var(--text-secondary)",
        fontSize: 12,
        cursor: "pointer",
        transition: "all 0.2s",
        fontWeight: 600,
        flexShrink: 0,
      }}
    >
      {copied ? "✓ Đã copy" : "Copy"}
    </button>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function UpgradePage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();

  const [subStatus, setSubStatus] = useState(null);
  const [payment, setPayment] = useState(null); // { qr_url, reference_code, amount, bank, ... }
  const [polling, setPolling] = useState(false);
  const [pollCount, setPollCount] = useState(0);
  const [step, setStep] = useState("plans"); // 'plans' | 'qr' | 'success'
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Load current subscription status
  useEffect(() => {
    if (!isAuthenticated) return;
    getSubscriptionStatus()
      .then(setSubStatus)
      .catch(() => {});
  }, [isAuthenticated]);

  // Redirect if not logged in
  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/login?redirect=/upgrade");
    }
  }, [authLoading, isAuthenticated, router]);

  // Poll payment status after QR shown
  const pollPayment = useCallback(async () => {
    if (!payment?.reference_code) return;
    try {
      const data = await checkPaymentStatus(payment.reference_code);
      if (data.status === "completed") {
        setStep("success");
        setPolling(false);
        // Refresh sub status
        const fresh = await getSubscriptionStatus();
        setSubStatus(fresh);
        return;
      }
    } catch {}
    setPollCount((c) => c + 1);
  }, [payment]);

  useEffect(() => {
    if (!polling || !payment) return;
    const id = setInterval(pollPayment, 5000); // Poll mỗi 5 giây
    return () => clearInterval(id);
  }, [polling, payment, pollPayment]);

  const handleUpgrade = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await createPayment("pro_49k");
      setPayment(data);
      setStep("qr");
      setPolling(true);
      setPollCount(0);
    } catch (e) {
      setError(e.message || "Không thể tạo đơn thanh toán. Vui lòng thử lại.");
    } finally {
      setLoading(false);
    }
  };

  if (authLoading || !isAuthenticated) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div className="spinner" />
      </div>
    );
  }

  const isPro = subStatus?.plan === "pro_49k";

  return (
    <>
      <Navbar />
      <main style={{ minHeight: "100vh", paddingTop: 100, paddingBottom: 60, background: "var(--bg-primary)" }}>
        <div style={{ maxWidth: 760, margin: "0 auto", padding: "0 20px" }}>

          {/* Header */}
          <div style={{ textAlign: "center", marginBottom: 48 }}>
            <div style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              padding: "6px 18px",
              borderRadius: 99,
              background: "rgba(234,179,8,0.12)",
              border: "1px solid rgba(234,179,8,0.25)",
              marginBottom: 20,
            }}>
              <span style={{ fontSize: 16 }}>⭐</span>
              <span style={{ fontSize: 13, fontWeight: 700, color: "#f59e0b" }}>TrendSense Pro</span>
            </div>
            <h1 style={{ fontSize: "clamp(28px, 5vw, 40px)", fontWeight: 800, color: "var(--text-primary)", marginBottom: 12 }}>
              Nâng cấp để phân tích <span style={{ background: "linear-gradient(135deg,#fbbf24,#f59e0b)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>không giới hạn</span>
            </h1>
            <p style={{ fontSize: 16, color: "var(--text-secondary)", maxWidth: 520, margin: "0 auto" }}>
              Tăng từ 2 lên 10 video phân tích mỗi ngày. Giá thân thiện với sinh viên — chỉ bằng 1 tô phở mỗi tháng.
            </p>
          </div>

          {/* Current quota status */}
          {subStatus && (
            <div style={{
              padding: "20px 24px",
              borderRadius: 16,
              background: "var(--bg-card)",
              border: "1px solid rgba(255,255,255,0.06)",
              marginBottom: 32,
            }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16, flexWrap: "wrap", gap: 8 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)" }}>Trạng thái hiện tại</span>
                  <span style={{
                    padding: "3px 10px",
                    borderRadius: 99,
                    fontSize: 12,
                    fontWeight: 700,
                    background: isPro ? "rgba(234,179,8,0.15)" : "rgba(255,255,255,0.08)",
                    color: isPro ? "#f59e0b" : "var(--text-muted)",
                    border: isPro ? "1px solid rgba(234,179,8,0.3)" : "1px solid rgba(255,255,255,0.08)",
                  }}>
                    {isPro ? "⭐ Pro" : "Free"}
                  </span>
                </div>
                {isPro && subStatus.expires_at && (
                  <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
                    Hết hạn: {new Date(subStatus.expires_at).toLocaleDateString("vi-VN")}
                  </span>
                )}
              </div>
              <QuotaBar
                used={subStatus.quota?.used ?? 0}
                limit={subStatus.quota?.limit ?? 2}
              />
            </div>
          )}

          {/* ── STEP: plans ─────────────────────────────────────────── */}
          {step === "plans" && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>

              {/* Free card */}
              <div style={{
                padding: 28,
                borderRadius: 20,
                background: "var(--bg-card)",
                border: "1px solid rgba(255,255,255,0.07)",
              }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text-muted)", marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.08em" }}>Free</div>
                <div style={{ fontSize: 32, fontWeight: 800, color: "var(--text-primary)", marginBottom: 4 }}>0 đ</div>
                <div style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 24 }}>Mãi mãi</div>
                <ul style={{ listStyle: "none", padding: 0, margin: "0 0 24px", display: "flex", flexDirection: "column", gap: 10 }}>
                  {[
                    "2 video phân tích / ngày",
                    "Lịch sử 7 ngày",
                    "AI Gemini 2.5 Flash",
                    "Dashboard xu hướng",
                  ].map((f) => (
                    <li key={f} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 14, color: "var(--text-secondary)" }}>
                      <span style={{ color: "#10b981", fontWeight: 700, fontSize: 16 }}>✓</span> {f}
                    </li>
                  ))}
                </ul>
                {!isPro && (
                  <div style={{
                    padding: "10px 16px",
                    borderRadius: 10,
                    background: "rgba(255,255,255,0.04)",
                    border: "1px solid rgba(255,255,255,0.07)",
                    fontSize: 13,
                    color: "var(--text-muted)",
                    textAlign: "center",
                  }}>
                    Gói hiện tại
                  </div>
                )}
              </div>

              {/* Pro card */}
              <div style={{
                padding: 28,
                borderRadius: 20,
                background: "linear-gradient(135deg, rgba(245,158,11,0.08), rgba(234,179,8,0.04))",
                border: "1px solid rgba(245,158,11,0.25)",
                position: "relative",
                overflow: "hidden",
              }}>
                {/* Best value badge */}
                <div style={{
                  position: "absolute",
                  top: 16,
                  right: 16,
                  padding: "3px 10px",
                  borderRadius: 99,
                  background: "rgba(245,158,11,0.2)",
                  border: "1px solid rgba(245,158,11,0.4)",
                  fontSize: 11,
                  fontWeight: 700,
                  color: "#f59e0b",
                }}>
                  Phổ biến nhất
                </div>

                <div style={{ fontSize: 13, fontWeight: 700, color: "#f59e0b", marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.08em" }}>⭐ Pro</div>
                <div style={{ display: "flex", alignItems: "baseline", gap: 6, marginBottom: 4 }}>
                  <span style={{ fontSize: 32, fontWeight: 800, color: "var(--text-primary)" }}>49.000 đ</span>
                </div>
                <div style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 24 }}>/ 30 ngày • ~1,633đ/ngày</div>
                <ul style={{ listStyle: "none", padding: 0, margin: "0 0 24px", display: "flex", flexDirection: "column", gap: 10 }}>
                  {[
                    { text: "10 video phân tích / ngày", highlight: true },
                    { text: "Lịch sử 30 ngày", highlight: false },
                    { text: "AI Gemini 2.5 Flash", highlight: false },
                    { text: "Ưu tiên xử lý queue", highlight: false },
                    { text: "Badge ⭐ Pro", highlight: false },
                    { text: "Email hỗ trợ ưu tiên", highlight: false },
                  ].map((f) => (
                    <li key={f.text} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 14, color: f.highlight ? "var(--text-primary)" : "var(--text-secondary)", fontWeight: f.highlight ? 600 : 400 }}>
                      <span style={{ color: "#f59e0b", fontWeight: 700, fontSize: 16 }}>✓</span> {f.text}
                    </li>
                  ))}
                </ul>

                {isPro ? (
                  <div style={{
                    padding: "10px 16px",
                    borderRadius: 10,
                    background: "rgba(245,158,11,0.12)",
                    border: "1px solid rgba(245,158,11,0.25)",
                    fontSize: 13,
                    color: "#f59e0b",
                    textAlign: "center",
                    fontWeight: 700,
                  }}>
                    ⭐ Bạn đang dùng gói này
                  </div>
                ) : (
                  <button
                    id="btn-upgrade-pro"
                    onClick={handleUpgrade}
                    disabled={loading}
                    style={{
                      width: "100%",
                      padding: "14px 20px",
                      borderRadius: 12,
                      border: "none",
                      background: loading ? "rgba(245,158,11,0.4)" : "linear-gradient(135deg,#f59e0b,#d97706)",
                      color: "#fff",
                      fontWeight: 700,
                      fontSize: 15,
                      cursor: loading ? "not-allowed" : "pointer",
                      boxShadow: "0 4px 20px rgba(245,158,11,0.3)",
                      transition: "all 0.2s",
                    }}
                  >
                    {loading ? "Đang tạo QR..." : "🚀 Nâng cấp ngay — 49.000đ"}
                  </button>
                )}

                {error && (
                  <p style={{ marginTop: 10, fontSize: 13, color: "#ef4444", textAlign: "center" }}>{error}</p>
                )}
              </div>
            </div>
          )}

          {/* ── STEP: qr ─────────────────────────────────────────────── */}
          {step === "qr" && payment && (
            <div style={{
              padding: 36,
              borderRadius: 24,
              background: "var(--bg-card)",
              border: "1px solid rgba(255,255,255,0.08)",
              textAlign: "center",
            }}>
              <h2 style={{ fontSize: 22, fontWeight: 700, color: "var(--text-primary)", marginBottom: 6 }}>
                Quét mã QR để thanh toán
              </h2>
              <p style={{ fontSize: 14, color: "var(--text-muted)", marginBottom: 28 }}>
                Hệ thống sẽ tự động kích hoạt Pro trong vòng 1–2 phút sau khi nhận tiền
              </p>

              {/* QR image */}
              <div style={{
                display: "inline-block",
                padding: 16,
                borderRadius: 20,
                background: "#fff",
                boxShadow: "0 8px 40px rgba(0,0,0,0.4)",
                marginBottom: 28,
              }}>
                <img
                  src={payment.qr_url}
                  alt="VietQR MB Bank"
                  width={220}
                  height={220}
                  style={{ display: "block", borderRadius: 8 }}
                  onError={(e) => { e.target.style.display = "none"; }}
                />
              </div>

              {/* Bank info */}
              <div style={{
                display: "inline-flex",
                flexDirection: "column",
                gap: 12,
                padding: "20px 28px",
                borderRadius: 16,
                background: "rgba(255,255,255,0.03)",
                border: "1px solid rgba(255,255,255,0.07)",
                textAlign: "left",
                marginBottom: 24,
                minWidth: 280,
              }}>
                {[
                  { label: "Ngân hàng", value: "MB Bank" },
                  { label: "Số tài khoản", value: payment.bank?.account_no, copy: true },
                  { label: "Chủ TK", value: payment.bank?.account_name },
                  { label: "Số tiền", value: payment.amount_formatted, highlight: true },
                  { label: "Nội dung CK", value: payment.reference_code, copy: true, highlight: true },
                ].map((row) => (
                  <div key={row.label} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
                    <span style={{ fontSize: 13, color: "var(--text-muted)", flexShrink: 0 }}>{row.label}</span>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{
                        fontSize: 14,
                        fontWeight: row.highlight ? 700 : 500,
                        color: row.highlight ? "var(--text-primary)" : "var(--text-secondary)",
                        wordBreak: "break-all",
                      }}>
                        {row.value}
                      </span>
                      {row.copy && <CopyBtn text={row.value} />}
                    </div>
                  </div>
                ))}
              </div>

              {/* Warning */}
              <div style={{
                padding: "12px 16px",
                borderRadius: 10,
                background: "rgba(245,158,11,0.08)",
                border: "1px solid rgba(245,158,11,0.2)",
                marginBottom: 24,
                fontSize: 13,
                color: "#f59e0b",
                display: "flex",
                alignItems: "flex-start",
                gap: 8,
                textAlign: "left",
              }}>
                <span style={{ flexShrink: 0 }}>⚠️</span>
                <span>Vui lòng nhập <strong>đúng nội dung chuyển khoản</strong>: <strong>{payment.reference_code}</strong> để hệ thống nhận diện tự động.</span>
              </div>

              {/* Poll status */}
              <div style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 8,
                marginBottom: 20,
                fontSize: 13,
                color: "var(--text-muted)",
              }}>
                <span style={{
                  display: "inline-block",
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: "#10b981",
                  animation: "pulse 1.5s infinite",
                }} />
                Đang chờ xác nhận thanh toán... ({pollCount * 5}s)
              </div>

              <button
                onClick={() => { setStep("plans"); setPolling(false); setPayment(null); }}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "var(--text-muted)",
                  fontSize: 13,
                  cursor: "pointer",
                  textDecoration: "underline",
                }}
              >
                ← Quay lại
              </button>
            </div>
          )}

          {/* ── STEP: success ─────────────────────────────────────────── */}
          {step === "success" && (
            <div style={{
              padding: 48,
              borderRadius: 24,
              background: "linear-gradient(135deg, rgba(16,185,129,0.08), rgba(5,150,105,0.04))",
              border: "1px solid rgba(16,185,129,0.25)",
              textAlign: "center",
            }}>
              <div style={{ fontSize: 64, marginBottom: 20 }}>🎉</div>
              <h2 style={{ fontSize: 28, fontWeight: 800, color: "var(--text-primary)", marginBottom: 10 }}>
                Chào mừng bạn lên Pro!
              </h2>
              <p style={{ fontSize: 15, color: "var(--text-secondary)", marginBottom: 8 }}>
                Gói Pro đã được kích hoạt thành công. Bạn có <strong style={{ color: "#10b981" }}>10 lượt phân tích video mỗi ngày</strong>.
              </p>
              {subStatus?.expires_at && (
                <p style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 32 }}>
                  Hết hạn: {new Date(subStatus.expires_at).toLocaleDateString("vi-VN")}
                </p>
              )}
              <div style={{ display: "flex", gap: 12, justifyContent: "center", flexWrap: "wrap" }}>
                <Link href="/analyze"
                  style={{
                    padding: "12px 28px",
                    borderRadius: 12,
                    background: "linear-gradient(135deg,#10b981,#059669)",
                    color: "#fff",
                    fontWeight: 700,
                    textDecoration: "none",
                    fontSize: 15,
                    boxShadow: "0 4px 20px rgba(16,185,129,0.3)",
                  }}
                >
                  🎬 Bắt đầu phân tích video
                </Link>
                <Link href="/"
                  style={{
                    padding: "12px 28px",
                    borderRadius: 12,
                    background: "rgba(255,255,255,0.06)",
                    border: "1px solid rgba(255,255,255,0.1)",
                    color: "var(--text-primary)",
                    fontWeight: 600,
                    textDecoration: "none",
                    fontSize: 15,
                  }}
                >
                  Về trang chủ
                </Link>
              </div>
            </div>
          )}

          {/* Terms */}
          <p style={{ textAlign: "center", fontSize: 12, color: "var(--text-muted)", marginTop: 32 }}>
            Bằng cách thanh toán, bạn đồng ý với{" "}
            <span style={{ color: "var(--text-secondary)" }}>Điều khoản Dịch vụ</span> của TrendSense.
            Gói Pro có hiệu lực 30 ngày kể từ ngày thanh toán. Không hoàn tiền dưới mọi hình thức.
          </p>
        </div>
      </main>
    </>
  );
}
