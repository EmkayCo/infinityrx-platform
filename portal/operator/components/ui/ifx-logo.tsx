import Image from "next/image";
import { cn } from "@shared/lib/format";

interface IfxLogoProps {
  variant?: "white" | "navy" | "blue";
  size?: "sm" | "md" | "lg" | "xl";
  /** Retained for API compatibility; the brand wordmark is part of the asset. */
  showWordmark?: boolean;
  className?: string;
}

const SIZE_PX: Record<NonNullable<IfxLogoProps["size"]>, { w: number; h: number }> = {
  sm: { w: 96, h: 24 },
  md: { w: 132, h: 32 },
  lg: { w: 176, h: 44 },
  xl: { w: 320, h: 80 },
};

const ICON_ONLY_PX: Record<NonNullable<IfxLogoProps["size"]>, number> = {
  sm: 24,
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
