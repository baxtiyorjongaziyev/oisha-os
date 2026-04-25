import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  transpilePackages: ['@salescoach/shared-types'],
  experimental: { typedRoutes: true },
};

export default nextConfig;
