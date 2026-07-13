/** @type {import('next').NextConfig} */
const nextConfig = {
  // Produce a standalone output for container / Amplify deployments
  output: "standalone",

  async headers() {
    return [
      {
        // Immutable caching for hashed Next.js static assets
        source: "/_next/static/:path*",
        headers: [
          {
            key: "Cache-Control",
            value: "public, max-age=31536000, immutable",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
