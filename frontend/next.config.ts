import type { NextConfig } from "next";

const isProductionBuild = process.env.NODE_ENV === "production";
const apiOrigin = (() => {
  try {
    return process.env.NEXT_PUBLIC_API_BASE_URL
      ? new URL(process.env.NEXT_PUBLIC_API_BASE_URL).origin
      : "";
  } catch {
    return "";
  }
})();
const supabaseOrigin = (() => {
  try {
    return process.env.NEXT_PUBLIC_SUPABASE_URL
      ? new URL(process.env.NEXT_PUBLIC_SUPABASE_URL).origin
      : "";
  } catch {
    return "";
  }
})();

const csp = [
  "default-src 'self'",
  `connect-src 'self' ${apiOrigin} ${supabaseOrigin} https://*.supabase.co`.trim(),
  "font-src 'self' data:",
  `img-src 'self' data: blob: ${apiOrigin} ${supabaseOrigin} https://images.unsplash.com https://ui-avatars.com`.trim(),
  "media-src 'self' blob:",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "upgrade-insecure-requests",
].join("; ");

const nextConfig: NextConfig = {
  productionBrowserSourceMaps: false,
  reactStrictMode: false,
  compress: true,
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "images.unsplash.com" },
      { protocol: "https", hostname: "ui-avatars.com" },
      { protocol: "https", hostname: "celtm-web-master-1.onrender.com" },
      ...(!isProductionBuild
        ? [
            { protocol: "http" as const, hostname: "127.0.0.1" },
            { protocol: "http" as const, hostname: "localhost" },
          ]
        : []),
    ],
  },
  experimental: {
    optimizePackageImports: [
      "lucide-react",
      "date-fns",
      "framer-motion",
      "clsx",
      "tailwind-merge"
    ],
  },
  async headers() {
    if (!isProductionBuild) {
      return [];
    }
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains; preload" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
