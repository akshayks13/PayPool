export const roles = ["RETAILER", "SELLER", "DRIVER", "ADMIN"] as const;
export type Role = (typeof roles)[number];

export const roleLabel: Record<Role, string> = {
  RETAILER: "Retailer",
  SELLER: "Seller",
  DRIVER: "Driver",
  ADMIN: "Admin",
};

export const navByRole: Record<
  Role,
  Array<{ label: string; segment: string }>
> = {
  RETAILER: [
    { label: "Home", segment: "" },
    { label: "Buy with PayPool", segment: "procurement" },
    { label: "Find products", segment: "catalog" },
    { label: "My buying list", segment: "requests" },
    { label: "Recurring requests", segment: "standing-orders" },
    { label: "Prices & offers", segment: "offers" },
    { label: "Shared delivery", segment: "pools" },
    { label: "My orders", segment: "orders" },
    { label: "Bills & receipts", segment: "receipts" },
    { label: "Messages", segment: "notifications" },
    { label: "Agent access", segment: "agent-access" },
    { label: "My shop", segment: "settings" },
  ],
  SELLER: [
    { label: "Home", segment: "" },
    { label: "My products", segment: "catalog" },
    { label: "Upload product sheet", segment: "upload-products" },
    { label: "External catalog feed", segment: "product-feed" },
    { label: "Stock", segment: "inventory" },
    { label: "My prices", segment: "pricing" },
    { label: "Buyer requests", segment: "offers" },
    { label: "Where I deliver", segment: "service-areas" },
    { label: "Vehicles & delivery", segment: "fleet" },
    { label: "Shared orders", segment: "pools" },
    { label: "Ready to send", segment: "dispatch" },
    { label: "My orders", segment: "orders" },
    { label: "Messages", segment: "notifications" },
    { label: "My business", segment: "settings" },
  ],
  DRIVER: [
    { label: "Today’s route", segment: "" },
    { label: "Assigned stops", segment: "stops" },
    { label: "Proof of delivery", segment: "pod" },
    { label: "Delivery exceptions", segment: "exceptions" },
    { label: "Completed deliveries", segment: "completed" },
    { label: "Profile", segment: "profile" },
  ],
  ADMIN: [
    { label: "Operations overview", segment: "" },
    { label: "Users & roles", segment: "users" },
    { label: "Seller verification", segment: "seller-verification" },
    { label: "Orders & pools", segment: "operations" },
    { label: "Payment health", segment: "integrations" },
    { label: "Exceptions & support", segment: "exceptions" },
    { label: "Audit log", segment: "audit" },
    { label: "Jobs & reconciliation", segment: "jobs" },
    { label: "Environment status", segment: "environment" },
  ],
};
