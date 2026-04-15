/**
 * lucide-react mock for vitest.
 *
 * lucide-react ≥1.8.0 uses createContext + useContext internally which
 * breaks in the jsdom test environment under React 19 when the React
 * dispatcher is null during non-act renders. Replace every icon with a
 * trivial SVG stub so error-boundary and component tests don't crash.
 */
import React from "react";

const iconStub = (name: string) => {
  const Comp = React.forwardRef<SVGSVGElement, React.SVGProps<SVGSVGElement>>(
    (props, ref) =>
      React.createElement("svg", {
        "data-icon": name,
        "aria-hidden": true,
        ...props,
        ref,
      })
  );
  Comp.displayName = name;
  return Comp;
};

export const AlertTriangle = iconStub("AlertTriangle");
export const RefreshCw = iconStub("RefreshCw");
export const ArrowUp = iconStub("ArrowUp");
export const ArrowDown = iconStub("ArrowDown");
export const ArrowUpDown = iconStub("ArrowUpDown");
export const Check = iconStub("Check");
export const CheckCircle2 = iconStub("CheckCircle2");
export const ChevronLeft = iconStub("ChevronLeft");
export const ChevronRight = iconStub("ChevronRight");
export const Clock = iconStub("Clock");
export const Columns3 = iconStub("Columns3");
export const DollarSign = iconStub("DollarSign");
export const Download = iconStub("Download");
export const FileText = iconStub("FileText");
export const LayoutGrid = iconStub("LayoutGrid");
export const Search = iconStub("Search");
export const ShieldAlert = iconStub("ShieldAlert");
export const ShieldCheck = iconStub("ShieldCheck");
export const Table2 = iconStub("Table2");
export const TrendingUp = iconStub("TrendingUp");
export const Upload = iconStub("Upload");
export const X = iconStub("X");

// Proxy for any icon not explicitly listed above
export default new Proxy(
  {},
  {
    get(_target, name) {
      return iconStub(String(name));
    },
  }
);
