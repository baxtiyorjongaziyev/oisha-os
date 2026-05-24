import type { NextConfig } from 'next';
import { resolve } from 'node:path';

const nextConfig: NextConfig = {
  transpilePackages: ['@salescoach/shared-types'],
  typedRoutes: true,
  turbopack: { root: resolve(__dirname, '../..') },
};

export default nextConfig;
