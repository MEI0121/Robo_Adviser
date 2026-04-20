/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    // Same-origin API calls from the browser avoid CORS entirely. Targets FastAPI on 127.0.0.1.
    return [
      {
        source: "/api/v1/:path*",
        destination: "http://127.0.0.1:8000/api/v1/:path*",
      },
    ];
  },
};

export default nextConfig;
