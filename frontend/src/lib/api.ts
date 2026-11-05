export type ProcurementIntent = {
  source_message: string;
  product_description: string | null;
  quantity: string | null;
  quantity_unit: string | null;
  delivery_date: string | null;
  delivery_date_text: string | null;
  price_ceiling_per_unit_minor: number | null;
  currency: string;
  substitution_consent: boolean;
  protected_attributes: string[];
  clarification_questions: string[];
  confirmation_required: boolean;
};

export type OfferTerms = {
  sku_id: string; quantity_min: number; quantity_max: number; unit_price_minor: number;
  estimated_freight_per_unit_minor: number; currency: string; delivery_terms: string; substitution_consent: boolean;
};
export type Offer = {
  id: string; procurement_request_id: string; buyer_id: string; seller_id: string; actor_id: string;
  version: number; state: "DRAFT" | "SUBMITTED" | "COUNTERED" | "ACCEPTED" | "REJECTED" | "EXPIRED";
  price_ceiling_per_unit_minor: number; terms: OfferTerms;
  validation: { status: "PASSED" | "FAILED" | "PENDING_AUTHORITATIVE_QUOTE"; reason: string | null };
  created_at: string; updated_at: string;
};

export class ApiError extends Error {
  constructor(public status: number, public detail: string) { super(detail); }
}

const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    ...init, credentials: "include", headers: { "Content-Type": "application/json", ...init?.headers }
  });
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    const detail = typeof payload === "object" && payload !== null && "detail" in payload
      ? JSON.stringify(payload.detail) : "The server could not complete this request.";
    throw new ApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}

export const api = {
  parseProcurement: (message: string, currency = "INR") => request<ProcurementIntent>("/api/v1/procurement/parse", { method: "POST", body: JSON.stringify({ message, currency }) }),
  createOffer: (body: Omit<Offer, "id" | "version" | "state" | "validation" | "created_at" | "updated_at">) => request<Offer>("/api/v1/offers", { method: "POST", body: JSON.stringify(body) }),
  listOffers: (requestId: string) => request<Offer[]>(`/api/v1/offers?request_id=${encodeURIComponent(requestId)}`),
  counterOffer: (id: string, actorId: string, terms: OfferTerms) => request<Offer>(`/api/v1/offers/${id}/counter`, { method: "POST", body: JSON.stringify({ actor_id: actorId, terms }) }),
  acceptOffer: (id: string, actorId: string) => request<Offer>(`/api/v1/offers/${id}/accept`, { method: "POST", body: JSON.stringify({ actor_id: actorId }) })
};
