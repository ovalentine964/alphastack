import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      // WebSocket proxy — Next.js doesn't support WS natively in API routes,
      // so we rewrite /ws to the backend directly.
      {
        source: "/ws",
        destination: "http://localhost:8000/ws",
      },
    ];
  },
  output: "standalone",
};

export default nextConfig;
