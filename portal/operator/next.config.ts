import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  webpack: (config) => {
    // Resolve @shared alias
    config.resolve.alias["@shared"] = path.resolve(__dirname, "../shared");

    // Make shared/ use operator's node_modules so it can resolve lucide-react, etc.
    const operatorModules = path.resolve(__dirname, "node_modules");
    if (Array.isArray(config.resolve.modules)) {
      if (!config.resolve.modules.includes(operatorModules)) {
        config.resolve.modules = [operatorModules, ...config.resolve.modules];
      }
    } else {
      config.resolve.modules = [operatorModules, "node_modules"];
    }

    return config;
  },
  typedRoutes: false,
};

export default nextConfig;
