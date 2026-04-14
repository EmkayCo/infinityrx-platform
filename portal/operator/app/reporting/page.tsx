"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Search, Star, Clock, Play } from "lucide-react";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { Skeleton } from "@shared/components/skeleton";
import { EmptyState } from "@shared/components/empty-state";
import { apiGet, apiPost, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { ReportTemplate, ReportCategory } from "@shared/types/reporting";
import { cn, formatDate } from "@shared/lib/format";
import { useRouter } from "next/navigation";

const CATEGORIES: { id: ReportCategory | "all"; label: string }[] = [
  { id: "all", label: "All" },
  { id: "financial", label: "Financial" },
  { id: "clinical", label: "Clinical" },
  { id: "operational", label: "Operational" },
  { id: "regulatory", label: "Regulatory" },
];

const CATEGORY_COLORS: Record<ReportCategory, string> = {
  financial: "bg-green-900/30 text-green-300 border-green-700/30",
  clinical: "bg-blue-900/30 text-blue-300 border-blue-700/30",
  operational: "bg-purple-900/30 text-purple-300 border-purple-700/30",
  regulatory: "bg-yellow-900/30 text-yellow-300 border-yellow-700/30",
};

function ReportCard({
  template,
  onGenerate,
  onToggleFavorite,
}: {
  template: ReportTemplate;
  onGenerate: (id: string) => void;
  onToggleFavorite: (id: string) => void;
}) {
  return (
    <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5 flex flex-col gap-3 hover:border-teal-600/40 transition-colors">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-white truncate">{template.name}</h3>
          <span
            className={cn(
              "inline-block text-xs px-2 py-0.5 rounded border mt-1 capitalize",
              CATEGORY_COLORS[template.category]
            )}
          >
            {template.category}
          </span>
        </div>
        <button
          onClick={() => onToggleFavorite(template.id)}
          aria-label={template.is_favorite ? "Remove from favorites" : "Add to favorites"}
          className="text-slate-500 hover:text-yellow-400 transition-colors flex-shrink-0"
        >
          <Star
            className={cn("w-4 h-4", template.is_favorite && "fill-yellow-400 text-yellow-400")}
          />
        </button>
      </div>
      <p className="text-xs text-slate-400 leading-relaxed flex-1">{template.description}</p>
      {template.last_generated && (
        <div className="flex items-center gap-1 text-xs text-slate-500">
          <Clock className="w-3 h-3" />
          Last generated: {formatDate(template.last_generated)}
        </div>
      )}
      <div className="flex gap-2">
        <button
          onClick={() => onGenerate(template.id)}
          className="flex items-center gap-1.5 flex-1 justify-center px-3 py-2 rounded-lg bg-teal-600 hover:bg-teal-500 text-white text-xs font-medium transition-colors"
        >
          <Play className="w-3 h-3" />
          Generate
        </button>
      </div>
    </div>
  );
}

export default function ReportLibraryPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [activeCategory, setActiveCategory] = useState<ReportCategory | "all">("all");
  const [searchQuery, setSearchQuery] = useState("");

  const { data: templates = [], isLoading } = useQuery<ReportTemplate[]>({
    queryKey: ["report-templates"],
    queryFn: () =>
      apiGet<ReportTemplate[]>(buildUrl(`${API_URLS.reporting}/api/v1/reports/templates`)),
    staleTime: 120_000,
  });

  const toggleFavorite = useMutation({
    mutationFn: (templateId: string) =>
      apiPost(`${API_URLS.reporting}/api/v1/reports/templates/${templateId}/favorite`, {}),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["report-templates"] });
    },
  });

  const filtered = templates.filter((t) => {
    const matchesCategory = activeCategory === "all" || t.category === activeCategory;
    const matchesSearch =
      !searchQuery ||
      t.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.description.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  const favorites = templates.filter((t) => t.is_favorite);
  const recents = templates
    .filter((t) => t.last_generated)
    .sort(
      (a, b) =>
        new Date(b.last_generated!).getTime() - new Date(a.last_generated!).getTime()
    )
    .slice(0, 5);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Report Library</h1>
          <p className="text-slate-400 text-sm mt-1">
            {templates.length} report templates available
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => router.push("/reporting/scheduled")}
            className="px-3 py-2 text-sm rounded-lg border border-ifx-border-dark text-slate-300 hover:bg-navy-700 transition-colors"
          >
            Scheduled Reports
          </button>
          <button
            onClick={() => router.push("/reporting/builder")}
            className="px-3 py-2 text-sm rounded-lg bg-teal-600 hover:bg-teal-500 text-white font-medium transition-colors"
          >
            Report Builder
          </button>
        </div>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
        <input
          type="search"
          placeholder="Search reports..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full max-w-md pl-9 pr-4 py-2 rounded-lg border border-ifx-border-dark bg-ifx-surface-dark text-white text-sm placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-teal-500/40"
        />
      </div>

      {/* Favorites */}
      {favorites.length > 0 && (
        <ErrorBoundary>
          <div>
            <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">
              Favorites
            </h2>
            <div className="flex gap-2 flex-wrap">
              {favorites.map((t) => (
                <button
                  key={t.id}
                  onClick={() => router.push(`/reporting/generate?template=${t.id}`)}
                  className="flex items-center gap-2 px-3 py-2 rounded-lg border border-yellow-700/30 bg-yellow-900/10 text-yellow-300 text-xs hover:bg-yellow-900/20 transition-colors"
                >
                  <Star className="w-3 h-3 fill-yellow-400" />
                  {t.name}
                </button>
              ))}
            </div>
          </div>
        </ErrorBoundary>
      )}

      {/* Recent */}
      {recents.length > 0 && (
        <ErrorBoundary>
          <div>
            <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">
              Recently Generated
            </h2>
            <div className="flex gap-2 flex-wrap">
              {recents.map((t) => (
                <button
                  key={t.id}
                  onClick={() => router.push(`/reporting/generate?template=${t.id}`)}
                  className="flex items-center gap-2 px-3 py-2 rounded-lg border border-ifx-border-dark text-slate-300 text-xs hover:bg-navy-700 transition-colors"
                >
                  <Clock className="w-3 h-3" />
                  {t.name}
                </button>
              ))}
            </div>
          </div>
        </ErrorBoundary>
      )}

      {/* Category tabs */}
      <div className="flex gap-1 border-b border-ifx-border-dark">
        {CATEGORIES.map((cat) => (
          <button
            key={cat.id}
            onClick={() => setActiveCategory(cat.id)}
            className={cn(
              "px-4 py-2 text-sm font-medium border-b-2 transition-colors",
              activeCategory === cat.id
                ? "border-teal-500 text-teal-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            )}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {/* Template grid */}
      <ErrorBoundary>
        {isLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-48 rounded-lg" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState
            title="No reports found"
            description="Try adjusting your search or category filter."
          />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {filtered.map((template) => (
              <ReportCard
                key={template.id}
                template={template}
                onGenerate={(id) => router.push(`/reporting/generate?template=${id}`)}
                onToggleFavorite={(id) => toggleFavorite.mutate(id)}
              />
            ))}
          </div>
        )}
      </ErrorBoundary>
    </div>
  );
}
