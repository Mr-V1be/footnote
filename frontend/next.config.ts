import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/shared/i18n/request.ts");

const config: NextConfig = {
  reactStrictMode: true,
  // Keep the project free of files written by the dev server.
  agentRules: false,
  devIndicators: false,
  poweredByHeader: false,
  output: "standalone",
  // The Redis and OIDC clients run only on the server and keep their own sockets.
  serverExternalPackages: ["redis", "openid-client"],
  experimental: {
    optimizePackageImports: ["@tabler/icons-react", "radix-ui"],
  },
};

export default withNextIntl(config);
