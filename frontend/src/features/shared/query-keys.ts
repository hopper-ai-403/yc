/** Shared feature-layer primitives: query key factory helpers. */

export const createQueryKeys = <T extends string>(domain: T) => ({
  all: [domain] as const,
  lists: () => [domain, "list"] as const,
  list: (params?: Record<string, unknown>) =>
    [domain, "list", params ?? {}] as const,
  details: () => [domain, "detail"] as const,
  detail: (id: string) => [domain, "detail", id] as const,
});
