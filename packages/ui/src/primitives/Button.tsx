import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

const buttonVariants = cva(
  // Base classes (framework-agnostic — no Tailwind needed to compile; classes are just strings)
  "irx-btn",
  {
    variants: {
      variant: {
        default: "irx-btn--default",
        destructive: "irx-btn--destructive",
        outline: "irx-btn--outline",
        ghost: "irx-btn--ghost",
      },
      size: {
        sm: "irx-btn--sm",
        md: "irx-btn--md",
        lg: "irx-btn--lg",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "md",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

/**
 * Reference button primitive. Uses cva for variant/size composition.
 * Portals apply Tailwind utility classes by augmenting buttonVariants via
 * className merging (cn(buttonVariants(...), className)).
 */
export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant, size, className, ...props }, ref) => (
    <button
      ref={ref}
      className={[buttonVariants({ variant, size }), className].filter(Boolean).join(" ")}
      {...props}
    />
  ),
);
Button.displayName = "Button";
