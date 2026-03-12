export interface ProductVariant {
  id: number;
  product_id: number;
  product_name: string | null;
  category: string | null;
  sku: string;
  size: string;
  color: string;
  current_stock: number;
  price: number;
}

export interface Supplier {
  name: string;
  lead_time_days: number;
  moq: number;
  case_pack_size: number;
}

export interface Product {
  id: number;
  name: string;
  category: string;
  square_id: string | null;
  supplier: Supplier | null;
  variants: ProductVariant[];
  total_stock: number;
}

export interface StockoutPrediction {
  id: number;
  variant_id: number;
  sku: string;
  product_name: string | null;
  size: string;
  color: string;
  current_stock: number;
  daily_velocity: number;
  days_until_stockout: number | null;
  predicted_stockout_date: string | null;
  recommended_reorder_qty: number;
  recommended_order_by_date: string | null;
  created_at: string | null;
}

export interface Alert {
  id: number;
  type: "stockout" | "reorder" | "dead_inventory";
  variant_id: number;
  sku: string | null;
  product_name: string | null;
  message: string;
  is_read: boolean;
  created_at: string | null;
}

export interface PredictionSummary {
  critical: number;
  warning: number;
  healthy: number;
  unread_alerts: number;
  actions_needed_today: number;
}

export interface DashboardData {
  inventory_summary: {
    total_products: number;
    total_variants: number;
    total_units_in_stock: number;
  };
  prediction_summary: PredictionSummary;
  critical_alerts: Alert[];
  reorder_actions: Alert[];
}
