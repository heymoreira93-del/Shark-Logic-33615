import type { NextConfig } from "next";
import { withSentryConfig } from "@sentry/nextjs";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
};

// Sentry wrap is a no-op upload without SENTRY_AUTH_TOKEN.
export default withSentryConfig(nextConfig, {
  silent: true,
  widenClientFileUpload: true,
});
