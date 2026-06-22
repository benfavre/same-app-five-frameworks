import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Pin the workspace root to this app dir so a parent lockfile doesn't
  // confuse Turbopack's root inference during build.
  turbopack: {
    root: __dirname,
  },
};

export default nextConfig;
