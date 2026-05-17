/** @type {import('next').NextConfig} */

// BACKEND_URL: đọc từ env var để linh hoạt
//   - Local dev:   BACKEND_URL=http://localhost:8080  (set trong .env.local)
//   - Production:  BACKEND_URL=https://trendsense-sfj6.onrender.com (set trên Vercel/Render)
const BACKEND_URL = process.env.BACKEND_URL || "https://trendsense-sfj6.onrender.com";

const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BACKEND_URL}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
