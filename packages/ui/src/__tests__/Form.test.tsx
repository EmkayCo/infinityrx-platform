import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { z } from "zod";
import { Form } from "../form/Form.js";
import { FormField } from "../form/FormField.js";
import { Input } from "../primitives/Input.js";

const schema = z.object({ email: z.string().email("Invalid email") });

describe("Form + FormField", () => {
  it("renders a form element", () => {
    render(
      <Form schema={schema} defaultValues={{ email: "" }} onSubmit={() => {}}>
        <FormField name="email" label="Email">
          {(field) => <Input {...field} />}
        </FormField>
      </Form>,
    );
    expect(screen.getByRole("form")).toBeDefined();
  });

  it("renders the field label", () => {
    render(
      <Form schema={schema} defaultValues={{ email: "" }} onSubmit={() => {}}>
        <FormField name="email" label="Email">
          {(field) => <Input {...field} />}
        </FormField>
      </Form>,
    );
    expect(screen.getByText("Email")).toBeDefined();
  });

  it("shows zod validation error on submit with invalid value", async () => {
    render(
      <Form schema={schema} defaultValues={{ email: "" }} onSubmit={() => {}}>
        <FormField name="email" label="Email">
          {(field) => <Input {...field} />}
        </FormField>
        <button type="submit">Submit</button>
      </Form>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Submit" }));
    expect(await screen.findByText("Invalid email")).toBeDefined();
  });

  it("calls onSubmit with validated data on valid submission", async () => {
    const onSubmit = vi.fn();
    render(
      <Form schema={schema} defaultValues={{ email: "" }} onSubmit={onSubmit}>
        <FormField name="email" label="Email">
          {(field) => <Input {...field} />}
        </FormField>
        <button type="submit">Submit</button>
      </Form>,
    );
    await userEvent.type(screen.getByRole("textbox"), "user@example.com");
    await userEvent.click(screen.getByRole("button", { name: "Submit" }));
    expect(onSubmit).toHaveBeenCalledWith({ email: "user@example.com" });
  });
});
