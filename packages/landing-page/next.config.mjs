import bundleAnalyzer from '@next/bundle-analyzer';

const withBundleAnalyzer = bundleAnalyzer({
  enabled: process.env.ANALYZE === 'true',
});

/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'picsum.photos',
      },
    ],
  },
  // Optimize icon imports to reduce bundle size
  modularizeImports: {
    'lucide-react': {
      transform: 'lucide-react/dist/esm/icons/{{kebabCase member}}',
    },
  },
  // Enable experimental optimizations
  experimental: {
    optimizePackageImports: ['lucide-react'],
  },
  // Compress output
  compress: true,
  // Enable SWC minification
  swcMinify: true,
};

export default withBundleAnalyzer(nextConfig);
