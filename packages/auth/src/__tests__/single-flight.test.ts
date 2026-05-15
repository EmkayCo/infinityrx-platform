import { describe, it, expect, vi } from "vitest";
import { SingleFlightRefresh } from "../single-flight.js";

describe("SingleFlightRefresh", () => {
  it("coalesces concurrent calls with the same key to one execution", async () => {
    const sf = new SingleFlightRefresh<number>();
    const fn = vi.fn(async () => {
      await new Promise((r) => setTimeout(r, 10));
      return 42;
    });
    const [a, b, c] = await Promise.all([
      sf.run("k", fn),
      sf.run("k", fn),
      sf.run("k", fn),
    ]);
    expect(a).toBe(42);
    expect(b).toBe(42);
    expect(c).toBe(42);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("different keys do not coalesce", async () => {
    const sf = new SingleFlightRefresh<string>();
    const fn1 = vi.fn(async () => "a");
    const fn2 = vi.fn(async () => "b");
    const [a, b] = await Promise.all([sf.run("k1", fn1), sf.run("k2", fn2)]);
    expect(a).toBe("a");
    expect(b).toBe("b");
    expect(fn1).toHaveBeenCalledTimes(1);
    expect(fn2).toHaveBeenCalledTimes(1);
  });

  it("after the in-flight resolves, the next call with the same key runs again", async () => {
    const sf = new SingleFlightRefresh<number>();
    let counter = 0;
    const fn = async () => ++counter;
    await sf.run("k", fn);
    await sf.run("k", fn);
    expect(counter).toBe(2);
  });

  it("after the in-flight rejects, the next call with the same key runs again", async () => {
    const sf = new SingleFlightRefresh<number>();
    let counter = 0;
    const fn = async () => {
      counter++;
      if (counter === 1) throw new Error("first call fails");
      return counter;
    };
    await expect(sf.run("k", fn)).rejects.toThrow("first call fails");
    expect(await sf.run("k", fn)).toBe(2);
  });
});
