import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Emits a minimal self contained server bundle for the Docker image.
  // Vercel ignores this and uses its own build output.
  output: "standalone",
};

export default nextConfig;
