import type { NextConfig } from 'next';
import { resolve } from 'node:path';

const nextConfig: NextConfig = {
  // 1GB serverga node_modules'siz deploy uchun — server.js + minimal deps
  output: 'standalone',
  transpilePackages: ['@salescoach/shared-types'],
  typedRoutes: true,
  turbopack: { root: resolve(__dirname, '../..') },
};

export default nextConfig;
