"use client";
import { useEffect, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "../../lib/AuthContext";

function CallbackHandler() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { handleOAuthCallback } = useAuth();
  const [status, setStatus] = useState("processing");
  const [error, setError] = useState("");

  useEffect(() => {
    const errorParam = searchParams.get("error");
    if (errorParam) {
      setStatus("error");
      const messages = {
        google_exchange_failed: "Không thể xác thực với Google. Vui lòng thử lại.",
        github_exchange_failed: "Không thể xác thực với GitHub. Vui lòng thử lại.",
        google_no_email: "Google không cung cấp email. Vui lòng thử lại.",
        github_no_email: "GitHub không cung cấp email. Vui lòng kiểm tra cài đặt quyền riêng tư.",
        oauth_create_failed: "Không thể tạo tài khoản. Vui lòng thử lại.",
      };
      setError(messages[errorParam] || `Lỗi xác thực: ${errorParam}`);
      return;
    }

    const success = handleOAuthCallback(searchParams);
    if (success) {
      setStatus("success");
      setTimeout(() => router.replace("/analyze"), 1000);
    } else {
      setStatus("error");
      setError("Không tìm thấy token xác thực. Vui lòng thử lại.");
    }
  }, [searchParams, handleOAuthCallback, router]);

  return (
    <main className="min-h-screen w-full flex items-center justify-center"
      style={{ background: "var(--bg-primary)" }}>
      <div className="text-center max-w-md mx-auto px-4">
        {status === "processing" && (
          <>
            <svg className="animate-spin w-12 h-12 mx-auto mb-4" viewBox="0 0 24 24"
              style={{ color: "var(--accent-primary)" }}>
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            <h2 className="text-xl font-bold">Đang xác thực...</h2>
            <p className="text-sm mt-2" style={{ color: "var(--text-muted)" }}>Vui lòng chờ trong giây lát.</p>
          </>
        )}
        {status === "success" && (
          <>
            <div className="text-5xl mb-4">✅</div>
            <h2 className="text-xl font-bold">Đăng nhập thành công!</h2>
            <p className="text-sm mt-2" style={{ color: "var(--text-muted)" }}>Đang chuyển hướng...</p>
          </>
        )}
        {status === "error" && (
          <>
            <div className="text-5xl mb-4">❌</div>
            <h2 className="text-xl font-bold mb-2">Đăng nhập thất bại</h2>
            <p className="text-sm mb-6" style={{ color: "var(--accent-red)" }}>{error}</p>
            <button onClick={() => router.replace("/login")}
              className="btn-primary text-sm">
              Quay lại đăng nhập
            </button>
          </>
        )}
      </div>
    </main>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense fallback={
      <main className="min-h-screen w-full flex items-center justify-center" style={{ background: "var(--bg-primary)" }}>
        <div className="text-center">
          <svg className="animate-spin w-10 h-10 mx-auto mb-4" viewBox="0 0 24 24" style={{ color: "var(--accent-primary)" }}>
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
        </div>
      </main>
    }>
      <CallbackHandler />
    </Suspense>
  );
}
