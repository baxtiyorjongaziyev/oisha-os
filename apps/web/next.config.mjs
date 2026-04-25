/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ["@salescoach/ui", "@salescoach/shared-types"]
};

export default nextConfig;
