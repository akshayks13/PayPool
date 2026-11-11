import type { Workspace } from "@/lib/commerce";
export type Action = (
  path: string,
  data?: unknown,
  headers?: Record<string, string>,
) => Promise<unknown>;
export type FeatureProps = { data: Workspace; act: Action; busy: boolean };
export type Offer = {
  id: string;
  request_id: string;
  buyer_id: string;
  seller_id: string;
  actor: string;
  version: number;
  status: string;
  currency: string;
  unit: string;
  expires_at: string;
  terms: {
    product_id: string;
    quantity_min: number;
    quantity_max: number;
    unit_price_minor: number;
    note: string;
  };
};
export type Vehicle = {
  id: string;
  name: string;
  registration: string;
  seller_id: string;
  max_weight_grams: number;
  max_volume_cm3: number;
  active: boolean;
};
export type Standing = {
  id: string;
  name: string;
  active: boolean;
  status?: string;
  next_dispatch_date: string;
  repeat_days: number;
  last_error?: string;
  request: {
    quantity_min: number;
    quantity_max: number;
    ceiling_minor: number;
    product_id: string;
  };
};
export type Job = {
  id: string;
  event_type: string;
  status: string;
  attempts: number;
  error?: string;
  occurred_at: string;
};
export type Features = {
  offers: Offer[];
  standing_orders: Standing[];
  vehicles: Vehicle[];
  jobs: Job[];
  agent_runs: { id: string; status: string; created_at: string }[];
  stock_movements: {
    id: string;
    product_id: string;
    delta: number;
    balance: number;
    reason: string;
    at: string;
  }[];
  agent_access: {
    client_id: string;
    name: string;
    active: boolean;
    expires_at: string;
  }[];
};
