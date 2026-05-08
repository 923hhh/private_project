/** @type {import('next').NextConfig} */
const nextConfig = {
  /** 开发模式下允许从局域网 / WSL 等主机访问 HMR（webpack-hmr） */
  allowedDevOrigins: ["127.0.0.1", "localhost", "172.29.198.47"],
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  devIndicators: false,
}

export default nextConfig
