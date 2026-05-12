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

export const AlertCircle = iconStub("AlertCircle");
export const AlertTriangle = iconStub("AlertTriangle");
export const ArrowDown = iconStub("ArrowDown");
export const ArrowLeft = iconStub("ArrowLeft");
export const ArrowRight = iconStub("ArrowRight");
export const ArrowUp = iconStub("ArrowUp");
export const ArrowUpDown = iconStub("ArrowUpDown");
export const Building2 = iconStub("Building2");
export const Calendar = iconStub("Calendar");
export const Check = iconStub("Check");
export const CheckCircle2 = iconStub("CheckCircle2");
export const ChevronDown = iconStub("ChevronDown");
export const ChevronLeft = iconStub("ChevronLeft");
export const ChevronRight = iconStub("ChevronRight");
export const ChevronUp = iconStub("ChevronUp");
export const ChevronsLeft = iconStub("ChevronsLeft");
export const ChevronsRight = iconStub("ChevronsRight");
export const Clock = iconStub("Clock");
export const Columns3 = iconStub("Columns3");
export const DollarSign = iconStub("DollarSign");
export const Download = iconStub("Download");
export const FileBarChart = iconStub("FileBarChart");
export const FileDown = iconStub("FileDown");
export const FileJson = iconStub("FileJson");
export const FileText = iconStub("FileText");
export const History = iconStub("History");
export const LayoutDashboard = iconStub("LayoutDashboard");
export const LayoutGrid = iconStub("LayoutGrid");
export const Loader2 = iconStub("Loader2");
export const Mail = iconStub("Mail");
export const MapPin = iconStub("MapPin");
export const Pill = iconStub("Pill");
export const PlayCircle = iconStub("PlayCircle");
export const Plus = iconStub("Plus");
export const Radio = iconStub("Radio");
export const Receipt = iconStub("Receipt");
export const RefreshCw = iconStub("RefreshCw");
export const Scale = iconStub("Scale");
export const Search = iconStub("Search");
export const Settings = iconStub("Settings");
export const ShieldAlert = iconStub("ShieldAlert");
export const ShieldCheck = iconStub("ShieldCheck");
export const SlidersHorizontal = iconStub("SlidersHorizontal");
export const Table2 = iconStub("Table2");
export const TrendingUp = iconStub("TrendingUp");
export const Upload = iconStub("Upload");
export const Users = iconStub("Users");
export const Wallet = iconStub("Wallet");
export const X = iconStub("X");
export const XCircle = iconStub("XCircle");
// lucide-react renamed AlertTriangle → TriangleAlert; provide the alias.
export const TriangleAlert = AlertTriangle;

// Proxy for any icon not explicitly listed above
export default new Proxy(
  {},
  {
    get(_target, name) {
      return iconStub(String(name));
    },
  }
);
