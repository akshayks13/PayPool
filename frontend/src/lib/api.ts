export type ProcurementIntent = {
  source_message: string;
  product_description: string | null;
  quantity: string | null;
  quantity_unit: string | null;
  delivery_date: string | null;
  delivery_date_text: string | null;
  price_ceiling_per_unit_minor: number | null;
  target_price_per_unit_minor?: number | null;
  currency: string;
  substitution_consent: boolean;
  protected_attributes: string[];
  clarification_questions: string[];
  confirmation_required: boolean;
};
