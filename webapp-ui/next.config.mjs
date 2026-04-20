/** @type {import('next').NextConfig} */
const FASTAPI_URL = process.env.INTERNAL_API_BASE || "http://127.0.0.1:8000"

const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  async headers() {
    return [{
      source: "/:path*",
      headers: [
        { key: "X-Frame-Options", value: "DENY" },
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      ],
    }];
  },
  // dev 환경에서 /api/* 를 FastAPI로 프록시 (프로덕션에서는 Cloudflare Tunnel이 분리)
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${FASTAPI_URL}/api/:path*` }]
  },
};
export default nextConfig;
