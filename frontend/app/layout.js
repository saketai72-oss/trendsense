import "./globals.css";

export const metadata = {
  title: "TrendSense — AI Dự Báo Xu Hướng TikTok",
  description:
    "Hệ thống AI phân tích và dự báo khả năng lan truyền video TikTok. Khám phá xu hướng, tốc độ viral và nhận đề xuất tối ưu nội dung.",
  keywords: "TikTok, viral, AI, prediction, xu hướng, trend, TrendSense",
};

export default function RootLayout({ children }) {
  return (
    <html lang="vi">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="antialiased">{children}</body>
    </html>
  );
}
