export async function api<T>(
  path: string,
  body?: unknown,
  method?: string,
  headers?: Record<string, string>,
): Promise<T> {
  const response = await fetch(`/api${path}`, {
    credentials: "same-origin",
    method: method || (body === undefined ? "GET" : "POST"),
    headers: {
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      ...headers,
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    cache: "no-store",
  });
  if (!response.ok) {
    const data = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    if (response.status === 401 && !path.startsWith("/auth/") && typeof window !== "undefined") {
      window.location.replace(authPath(data.setup_required === true));
    }
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail),
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
export function authPath(setupRequired: boolean) {
  return setupRequired ? "/setup" : "/login";
}
export function label(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (x) => x.toUpperCase());
}
export function date(value?: string | null) {
  return value
    ? new Date(value).toLocaleString(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      })
    : "Unavailable";
}
export function percent(value: number) {
  return `${Math.round(value * 100)}%`;
}
