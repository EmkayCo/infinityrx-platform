"use client";

import React, { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Search, CheckCircle, XCircle, Loader } from "lucide-react";
import { apiPost } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { EligibilityResult } from "@shared/types/directories";
import { cn, formatDate, formatDateTime } from "@shared/lib/format";

const schema = z.object({
  member_id: z.string().min(1, "Member ID is required"),
  date_of_birth: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Enter date as YYYY-MM-DD"),
});

type FormValues = z.infer<typeof schema>;

export default function EligibilityCheckPage() {
  const [result, setResult] = useState<EligibilityResult | null>(null);
  const [isChecking, setIsChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  async function onSubmit(values: FormValues) {
    setIsChecking(true);
    setResult(null);
    setError(null);
    try {
      const res = await apiPost<EligibilityResult>(
        `${API_URLS.memberManagement}/api/v1/members/eligibility`,
        values
      );
      setResult(res);
    } catch {
      setError("Eligibility check failed. Please try again.");
    } finally {
      setIsChecking(false);
    }
  }

  return (
    <div className="p-6 max-w-xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Eligibility Check</h1>
        <p className="text-slate-400 text-sm mt-1">
          Verify member coverage status in real time
        </p>
      </div>

      <form
        onSubmit={handleSubmit(onSubmit)}
        className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-6 space-y-4"
      >
        <div>
          <label className="block text-xs font-medium text-slate-300 mb-1.5">
            Member ID
          </label>
          <input
            {...register("member_id")}
            placeholder="MBR-123456"
            className="w-full px-3 py-2 rounded-lg border border-ifx-border-dark bg-navy-900 text-white text-sm placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-teal-500/40"
          />
          {errors.member_id && (
            <p className="text-xs text-red-400 mt-1">{errors.member_id.message}</p>
          )}
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-300 mb-1.5">
            Date of Birth
          </label>
          <input
            {...register("date_of_birth")}
            type="date"
            className="w-full px-3 py-2 rounded-lg border border-ifx-border-dark bg-navy-900 text-white text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/40"
          />
          {errors.date_of_birth && (
            <p className="text-xs text-red-400 mt-1">{errors.date_of_birth.message}</p>
          )}
        </div>

        <button
          type="submit"
          disabled={isChecking}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-teal-600 hover:bg-teal-500 text-white text-sm font-medium transition-colors disabled:opacity-50"
        >
          {isChecking ? (
            <>
              <Loader className="w-4 h-4 animate-spin" />
              Checking...
            </>
          ) : (
            <>
              <Search className="w-4 h-4" />
              Check Eligibility
            </>
          )}
        </button>
      </form>

      {error && (
        <div className="rounded-lg border border-red-700/30 bg-red-900/10 p-4 text-sm text-red-400">
          {error}
        </div>
      )}

      {result && (
        <div
          className={cn(
            "rounded-lg border p-5 space-y-3",
            result.found && result.coverage_status === "active"
              ? "border-green-700/30 bg-green-900/10"
              : "border-red-700/30 bg-red-900/10"
          )}
        >
          <div className="flex items-center gap-3">
            {result.found && result.coverage_status === "active" ? (
              <CheckCircle className="w-6 h-6 text-green-400" />
            ) : (
              <XCircle className="w-6 h-6 text-red-400" />
            )}
            <div>
              <p className="text-base font-semibold text-white">
                {result.found
                  ? result.coverage_status === "active"
                    ? "Member is Eligible"
                    : `Coverage Status: ${result.coverage_status}`
                  : "Member Not Found"}
              </p>
              <p className="text-xs text-slate-400">
                Checked: {formatDateTime(result.checked_at)}
              </p>
            </div>
          </div>

          {result.found && (
            <div className="space-y-1.5 text-sm pt-2 border-t border-ifx-border-dark">
              {result.plan_name && (
                <div className="flex justify-between">
                  <span className="text-slate-400">Plan</span>
                  <span className="text-white">{result.plan_name}</span>
                </div>
              )}
              {result.group_id && (
                <div className="flex justify-between">
                  <span className="text-slate-400">Group ID</span>
                  <span className="text-white font-mono">{result.group_id}</span>
                </div>
              )}
              {result.coverage_effective_date && (
                <div className="flex justify-between">
                  <span className="text-slate-400">Effective</span>
                  <span className="text-white">{formatDate(result.coverage_effective_date)}</span>
                </div>
              )}
              {result.coverage_term_date && (
                <div className="flex justify-between">
                  <span className="text-slate-400">Term Date</span>
                  <span className="text-red-400">{formatDate(result.coverage_term_date)}</span>
                </div>
              )}
            </div>
          )}
          {result.error && (
            <p className="text-xs text-red-400">{result.error}</p>
          )}
        </div>
      )}
    </div>
  );
}
