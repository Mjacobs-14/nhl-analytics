import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  turbopack: { root: __dirname },
  images: {
    remotePatterns: [{ protocol: "https", hostname: "assets.nhle.com" }],
  },
};

export default nextConfig;
