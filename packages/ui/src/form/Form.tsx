import * as React from "react";
import { useForm, FormProvider, type DefaultValues, type FieldValues } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import type { ZodSchema } from "zod";

export interface FormProps<T extends FieldValues> {
  schema: ZodSchema<T>;
  defaultValues: DefaultValues<T>;
  onSubmit: (data: T) => void | Promise<void>;
  children: React.ReactNode;
  className?: string;
  "aria-label"?: string;
}

/**
 * Thin wrapper: wires react-hook-form + zod resolver, renders FormProvider.
 * Use FormField children to connect inputs to the form state.
 */
export function Form<T extends FieldValues>({
  schema,
  defaultValues,
  onSubmit,
  children,
  className,
  "aria-label": ariaLabel = "form",
}: FormProps<T>) {
  const methods = useForm<T>({
    resolver: zodResolver(schema),
    defaultValues,
  });

  return (
    <FormProvider {...methods}>
      <form
        aria-label={ariaLabel}
        className={["irx-form", className].filter(Boolean).join(" ")}
        onSubmit={methods.handleSubmit((data) => onSubmit(data))}
      >
        {children}
      </form>
    </FormProvider>
  );
}
