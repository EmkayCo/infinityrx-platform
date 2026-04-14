import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  webpack: (config) => {
    config.resolve.alias["@shared"] = path.resolve(__dirname, "../shared");
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
