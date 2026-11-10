import type { NextConfig } from "next";

/**
 * Two modes:
 * - `npm run dev`     → Next dev server on :3000, proxying /api/* to FastAPI on :8000.
 * - `npm run build`   → static export to ./out, which FastAPI serves itself (one process,
 *                       one origin, no CORS). Rewrites are not allowed with `output: "export"`,
 *                       hence the switch.
 */
const isExport = process.env.NEXT_EXPORT === "1" || process.env.npm_lifecycle_event === "build";
const apiOrigin = process.env.API_ORIGIN ?? "http://127.0.0.1:8000";

// Tailwind v4 is compiled by this Turbopack loader (from the scaffold) — needed in both modes.
const turbopack: NextConfig["turbopack"] = {
  rules: { "*.css": { loaders: ["@tailwindcss/turbopack"], as: "*.css" } },
};

const nextConfig: NextConfig = isExport
  ? { output: "export", trailingSlash: true, images: { unoptimized: true }, turbopack }
  : {
      trailingSlash: true,
      turbopack,
      async rewrites() {
        return [{ source: "/api/:path*", destination: `${apiOrigin}/api/:path*` }];
      },
    };

export default nextConfig;
