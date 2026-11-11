let csrf = "";
export const setCsrf = (value: string) => {
  csrf = value;
};
export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
  }
}
export async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  if (csrf) headers.set("X-CSRF-Token", csrf);
  const response = await fetch(path, {
    ...init,
    headers,
    credentials: "include",
    cache: "no-store",
  });
  const payload = await response.json().catch(() => null);
  if (
    response.status === 401 &&
    typeof window !== "undefined" &&
    path !== "/api/v1/me" &&
    !path.startsWith("/api/v1/auth/")
  )
    window.dispatchEvent(new Event("paypool:session-expired"));
  if (!response.ok)
    throw new ApiError(
      response.status,
      typeof payload?.detail === "string"
        ? payload.detail
        : payload?.detail
          ? JSON.stringify(payload.detail)
          : `Request failed (${response.status})`,
    );
  return payload as T;
}
export function post<T>(path: string, data: unknown = {}): Promise<T> {
  return request<T>(path, { method: "POST", body: JSON.stringify(data) });
}
