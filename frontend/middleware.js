/**
 * Next.js Edge Middleware
 * ========================
 * Bảo vệ route phía server trước khi page render:
 *  - Kiểm tra cookie `ts_auth` (flag lightweight, không chứa secret)
 *  - Redirect về /login nếu chưa đăng nhập
 *  - Thêm security headers cho mọi response
 */
import { NextResponse } from "next/server";

// Routes yêu cầu đăng nhập
const PROTECTED_PATHS = ["/analyze", "/dashboard", "/video"];

// Routes công khai (không cần auth)
const PUBLIC_PATHS = ["/", "/login", "/register", "/auth/callback"];

function isProtectedPath(pathname) {
  return PROTECTED_PATHS.some(
    (p) => pathname === p || pathname.startsWith(p + "/")
  );
}

export function middleware(request) {
  const { pathname } = request.nextUrl;

  // Bỏ qua static files, Next.js internals, API proxy
  if (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api") ||
    pathname.startsWith("/favicon") ||
    pathname.includes(".")
  ) {
    return addSecurityHeaders(NextResponse.next());
  }

  // Route protection
  if (isProtectedPath(pathname)) {
    const hasAuth = request.cookies.get("ts_auth")?.value;
    if (!hasAuth) {
      const loginUrl = new URL("/login", request.url);
      loginUrl.searchParams.set("redirect", pathname);
      return NextResponse.redirect(loginUrl);
    }
  }

  // Redirect authenticated users away from login/register
  if (pathname === "/login" || pathname === "/register") {
    const hasAuth = request.cookies.get("ts_auth")?.value;
    if (hasAuth) {
      return NextResponse.redirect(new URL("/dashboard", request.url));
    }
  }

  return addSecurityHeaders(NextResponse.next());
}

function addSecurityHeaders(response) {
  response.headers.set("X-Frame-Options", "DENY");
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  response.headers.set(
    "Permissions-Policy",
    "camera=(), microphone=(), geolocation=()"
  );
  return response;
}

export const config = {
  matcher: [
    /*
     * Match tất cả paths ngoại trừ:
     *  - _next/static (static files)
     *  - _next/image (image optimization)
     *  - favicon.ico
     */
    "/((?!_next/static|_next/image|favicon.ico).*)",
  ],
};
