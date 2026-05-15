import * as React from "react";

export type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

/**
 * Reference input primitive. forwardRef-compatible so react-hook-form's
 * register() and Controller render prop both work without a wrapper.
 */
export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={["irx-input", className].filter(Boolean).join(" ")}
      {...props}
    />
  ),
);
Input.displayName = "Input";
