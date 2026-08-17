import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  turbopack: {
    root: path.resolve(__dirname, "../.."),
  },
  transpilePackages: ["@salescoach/ui", "@salescoach/shared-types"],
};

export default nextConfig;
