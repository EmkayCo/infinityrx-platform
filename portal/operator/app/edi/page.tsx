import Link from "next/link";
import { Activity, FileText, Users, ShieldCheck, ArrowRight } from "lucide-react";

// Server Component — no client-side data, just a landing page with 4 cards
// linking to the EDI sub-routes. Exists so the sidebar's "EDI Operations"
// parent link doesn't 404.
interface EdiSection {
  href: string;
  title: string;
  description: string;
  icon: React.ElementType;
  accent: string;
}

const SECTIONS: EdiSection[] = [
  {
    href: "/edi/monitor",
    title: "Transaction Monitor",
    description:
      "Live throughput and rejection rates across all inbound and outbound X12 and NCPDP traffic.",
    icon: Activity,
    accent: "text-teal-400",
  },
  {
    href: "/edi/transactions",
    title: "Transactions",
    description:
      "Searchable log of every 834, 835, 837, 270/271, 276/277, and NCPDP Batch 1.2 transaction.",
    icon: FileText,
    accent: "text-blue-400",
  },
  {
    href: "/edi/partners",
    title: "Trading Partners",
    description:
      "Configure AS2 / SFTP endpoints, envelope settings, test-to-production promotion, and per-partner routing.",
    icon: Users,
    accent: "text-purple-400",
  },
  {
    href: "/edi/certs",
    title: "Certificates",
    description:
      "AS2 signing/encryption certificates, expiry alerts, and renewal workflow.",
    icon: ShieldCheck,
    accent: "text-yellow-400",
  },
];

export default function EdiIndexPage() {
  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">EDI Operations</h1>
        <p className="text-slate-400 text-sm mt-1">
          Trading partners, transaction monitoring, and certificate management
          for X12 and NCPDP EDI.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {SECTIONS.map(({ href, title, description, icon: Icon, accent }) => (
          <Link
            key={href}
            href={href}
            className="group rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5 transition-all hover:border-teal-600/40 hover:bg-ifx-surface-dark/80"
          >
            <div className="flex items-start justify-between mb-3">
              <Icon className={`w-6 h-6 ${accent}`} />
              <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-teal-400 group-hover:translate-x-0.5 transition-all" />
            </div>
            <h3 className="text-base font-semibold text-white mb-1">{title}</h3>
            <p className="text-sm text-slate-400 leading-relaxed">{description}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
