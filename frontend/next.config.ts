import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Emits a minimal self contained server bundle for the Docker image.
  // Vercel's own builder expects the default .next output and breaks on
  // standalone mode (missing next-server.js.nft.json), so this only turns on
  // when the Dockerfile explicitly asks for it, never on Vercel.
  ...(process.env.NEXT_OUTPUT_MODE === "standalone" ? { output: "standalone" as const } : {}),
};

export default nextConfig;
