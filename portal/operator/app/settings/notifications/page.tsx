"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Save } from "lucide-react";
import { apiPatch } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import { cn } from "@shared/lib/format";
import { toast } from "sonner";

interface NotificationPref {
  type: string;
  label: string;
  inApp: boolean;
  email: boolean;
  sms: boolean;
  inAppMutable: boolean;
  emailMutable: boolean;
  smsMutable: boolean;
}

const DEFAULT_PREFS: NotificationPref[] = [
  {
    type: "system_critical",
    label: "System down / critical error",
    inApp: true, email: true, sms: true,
    inAppMutable: false, emailMutable: false, smsMutable: false,
  },
  {
    type: "financial_discrepancy",
    label: "Financial discrepancy detected",
    inApp: true, email: true, sms: false,
    inAppMutable: false, emailMutable: true, smsMutable: true,
  },
  {
    type: "approval_request",
    label: "Approval request pending",
    inApp: true, email: true, sms: false,
    inAppMutable: false, emailMutable: true, smsMutable: true,
  },
  {
    type: "billing_cycle_completed",
    label: "Billing cycle completed",
    inApp: true, email: false, sms: false,
    inAppMutable: true, emailMutable: true, smsMutable: false,
  },
  {
    type: "report_generated",
    label: "Report generated",
    inApp: true, email: false, sms: false,
    inAppMutable: true, emailMutable: true, smsMutable: false,
  },
  {
    type: "fwa_high",
    label: "FWA flag (high severity)",
    inApp: true, email: true, sms: false,
    inAppMutable: false, emailMutable: true, smsMutable: true,
  },
  {
    type: "fwa_low",
    label: "FWA flag (medium/low)",
    inApp: true, email: false, sms: false,
    inAppMutable: true, emailMutable: true, smsMutable: false,
  },
  {
    type: "data_refresh",
    label: "Data refresh completed",
    inApp: false, email: false, sms: false,
    inAppMutable: true, emailMutable: false, smsMutable: false,
  },
];

function Toggle({
  checked,
  disabled,
  onChange,
  label,
}: {
  checked: boolean;
  disabled?: boolean;
  onChange?: (checked: boolean) => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange?.(!checked)}
      className={cn(
        "relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500",
        checked ? "bg-teal-500" : "bg-muted-foreground/30",
        disabled && "cursor-not-allowed opacity-50"
      )}
    >
      <span
        className={cn(
          "pointer-events-none inline-block h-4 w-4 translate-x-0 transform rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out",
          checked && "translate-x-4"
        )}
      />
    </button>
  );
}

export default function NotificationsSettingsPage() {
  const [prefs, setPrefs] = useState<NotificationPref[]>(DEFAULT_PREFS);

  const saveMutation = useMutation({
    mutationFn: (data: NotificationPref[]) =>
      apiPatch(`${API_URLS.corePlatform}/users/me/notification-preferences`, {
        preferences: data.map((p) => ({
          type: p.type,
          in_app: p.inApp,
          email: p.email,
          sms: p.sms,
        })),
      }),
    onSuccess: () => {
      toast.success("Notification preferences saved");
    },
    onError: () => {
      toast.error("Failed to save preferences");
    },
  });

  function update(type: string, channel: "inApp" | "email" | "sms", value: boolean) {
    setPrefs((prev) =>
      prev.map((p) => (p.type === type ? { ...p, [channel]: value } : p))
    );
  }

  return (
    <div className="max-w-2xl">
      <div className="mb-6">
        <h1 className="text-xl font-bold">Notification Preferences</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Configure how you receive notifications. Locked items are required for compliance.
        </p>
      </div>

      <div className="rounded-lg border bg-card overflow-hidden">
        <div className="grid grid-cols-[1fr_auto_auto_auto] gap-x-6 border-b px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">
          <span>Notification</span>
          <span className="text-center">In-App</span>
          <span className="text-center">Email</span>
          <span className="text-center">SMS</span>
        </div>
        {prefs.map((pref) => (
          <div
            key={pref.type}
            className="grid grid-cols-[1fr_auto_auto_auto] gap-x-6 items-center border-b px-4 py-3 last:border-0"
          >
            <span className="text-sm">{pref.label}</span>
            <div className="flex justify-center">
              <Toggle
                checked={pref.inApp}
                disabled={!pref.inAppMutable}
                onChange={(v) => update(pref.type, "inApp", v)}
                label={`${pref.label} — In-App`}
              />
            </div>
            <div className="flex justify-center">
              <Toggle
                checked={pref.email}
                disabled={!pref.emailMutable}
                onChange={(v) => update(pref.type, "email", v)}
                label={`${pref.label} — Email`}
              />
            </div>
            <div className="flex justify-center">
              <Toggle
                checked={pref.sms}
                disabled={!pref.smsMutable}
                onChange={(v) => update(pref.type, "sms", v)}
                label={`${pref.label} — SMS`}
              />
            </div>
          </div>
        ))}
      </div>

      <div className="mt-6 flex justify-end">
        <button
          onClick={() => saveMutation.mutate(prefs)}
          disabled={saveMutation.isPending}
          className="flex items-center gap-2 rounded-md bg-teal-500 px-4 py-2 text-sm font-medium text-white hover:bg-teal-600 disabled:opacity-50 transition-colors"
        >
          <Save className="h-4 w-4" />
          {saveMutation.isPending ? "Saving..." : "Save preferences"}
        </button>
      </div>
    </div>
  );
}
