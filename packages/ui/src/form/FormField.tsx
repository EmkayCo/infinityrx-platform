import * as React from "react";
import { useFormContext, Controller, type FieldValues, type Path } from "react-hook-form";

export interface FormFieldRenderProps {
  name: string;
  value: unknown;
  onChange: (...event: unknown[]) => void;
  onBlur: () => void;
  ref: React.Ref<unknown>;
}

export interface FormFieldProps<T extends FieldValues> {
  name: Path<T>;
  label: string;
  children: (field: FormFieldRenderProps) => React.ReactNode;
}

/**
 * Controller wrapper. Renders label + field slot + zod-sourced error message.
 * The children render prop receives the field object compatible with Input/forwardRef primitives.
 */
export function FormField<T extends FieldValues>({ name, label, children }: FormFieldProps<T>) {
  const { control, formState: { errors } } = useFormContext<T>();
  const error = errors[name];

  return (
    <div className="irx-form-field">
      <label htmlFor={name} className="irx-form-field__label">
        {label}
      </label>
      <Controller
        name={name}
        control={control}
        render={({ field }) => (
          <div id={name}>
            {children(field as unknown as FormFieldRenderProps)}
          </div>
        )}
      />
      {error != null && (
        <span className="irx-form-field__error" role="alert">
          {String(error.message)}
        </span>
      )}
    </div>
  );
}
