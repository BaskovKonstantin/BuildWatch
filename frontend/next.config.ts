import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  distDir: process.env.NODE_ENV === "production" ? ".next-prod" : ".next",
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${process.env.BUILDWATCH_API_ORIGIN || "http://127.0.0.1:8600"}/api/:path*` },
    ];
  },
};

export default nextConfig;
