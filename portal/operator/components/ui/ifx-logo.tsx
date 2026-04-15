import Image from "next/image";
import { cn } from "@shared/lib/format";

interface IfxLogoProps {
  /**
   * - `white` / `navy` / `blue` → static PNG asset
   * - `theme` → renders as a color mask so the fill follows the current
   *   text color (set via `className` or Tailwind `text-*` / `dark:text-*`)
   */
  variant?: "white" | "navy" | "blue" | "theme";
  size?: "sm" | "md" | "lg" | "xl";
  /** Retained for API compatibility; the brand wordmark is part of the asset. */
  showWordmark?: boolean;
  className?: string;
}

const SIZE_PX: Record<NonNullable<IfxLogoProps["size"]>, { w: number; h: number }> = {
  sm: { w: 82, h: 20 },
  md: { w: 132, h: 32 },
  lg: { w: 176, h: 44 },
  xl: { w: 416, h: 104 },
};

const ICON_ONLY_PX: Record<NonNullable<IfxLogoProps["size"]>, number> = {
  sm: 20,
  md: 32,
  lg: 44,
  xl: 60,
};

/**
 * Official InfinityRx brand mark.
 * - `white` variant → public/images/infinityrx-white.png (for dark surfaces)
 * - `navy` / `blue` variants → public/images/infinityrx-blue.png (for light surfaces)
 *
 * The brand asset includes the infinity mark + "InfinityRx" wordmark baked
 * in. `showWordmark={false}` switches to icon-only (square crop).
 */
export function IfxLogo({
  variant = "navy",
  size = "md",
  showWordmark = true,
  className,
}: IfxLogoProps) {
  // `theme` variant: render as a CSS mask driven by currentColor so the
  // logo fill follows text color (use Tailwind `text-[#0B1120] dark:text-white`
  // on the caller or className).
  if (variant === "theme") {
    const { w, h } = showWordmark ? SIZE_PX[size] : { w: ICON_ONLY_PX[size], h: ICON_ONLY_PX[size] };
    const maskStyle: React.CSSProperties = {
      width: w,
      height: h,
      backgroundColor: "currentColor",
      WebkitMaskImage: "url(/images/infinityrx-white.png)",
      maskImage: "url(/images/infinityrx-white.png)",
      WebkitMaskRepeat: "no-repeat",
      maskRepeat: "no-repeat",
      WebkitMaskPosition: showWordmark ? "center" : "left center",
      maskPosition: showWordmark ? "center" : "left center",
      WebkitMaskSize: "contain",
      maskSize: "contain",
    };
    return (
      <span
        role="img"
        aria-label="InfinityRx"
        className={cn("inline-block shrink-0", className)}
        style={maskStyle}
      />
    );
  }

  const src = variant === "white"
    ? "/images/infinityrx-white.png"
    : "/images/infinityrx-blue.png";

  if (!showWordmark) {
    const px = ICON_ONLY_PX[size];
    return (
      <div
        className={cn("relative shrink-0 overflow-hidden", className)}
        style={{ width: px, height: px }}
        aria-label="InfinityRx"
      >
        <Image
          src={src}
          alt="InfinityRx"
          fill
          sizes={`${px}px`}
          className="object-contain object-left"
          priority
        />
      </div>
    );
  }

  const { w, h } = SIZE_PX[size];
  return (
    <Image
      src={src}
      alt="InfinityRx"
      width={w}
      height={h}
      sizes={`${w}px`}
      className={cn("object-contain", className)}
      priority
    />
  );
}
