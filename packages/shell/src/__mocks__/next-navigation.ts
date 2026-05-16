// Stub for next/navigation in vitest context.
// Tests that use next/navigation mock it explicitly via vi.mock().
export const redirect = () => { throw new Error("redirect called without mock"); };
export const useRouter = () => { throw new Error("useRouter called without mock"); };
export const useSearchParams = () => { throw new Error("useSearchParams called without mock"); };
export const usePathname = () => "/";
