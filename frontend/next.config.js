/** @type {import('next').NextConfig} */
const nextConfig = {
  // Proxy all /api/py/* requests to the FastAPI server to avoid CORS issues.
  // In production, replace localhost:8000 with your deployed backend URL.
  async rewrites() {
    return [
      {
        source: "/api/py/:path*",
        destination: "http://localhost:8000/:path*",
      },
    ];
  },
};

export default nextConfig;
