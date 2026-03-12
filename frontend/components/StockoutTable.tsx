import type { StockoutPrediction } from "@/types";

function urgencyColor(days: number | null): string {
  if (days === null) return "text-gray-500";
  if (days <= 7) return "text-red-400";
  if (days <= 14) return "text-red-400";
  if (days <= 30) return "text-amber-400";
  return "text-green-400";
}

function urgencyBadge(days: number | null): string {
  if (days === null) return "N/A";
  if (days <= 7) return "CRITICAL";
  if (days <= 14) return "URGENT";
  if (days <= 30) return "WARNING";
  return "HEALTHY";
}

export default function StockoutTable({ predictions }: { predictions: StockoutPrediction[] }) {
  if (predictions.length === 0) {
    return <p className="text-gray-500 text-sm py-4">No stockout predictions yet.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-gray-500 text-xs uppercase tracking-wider border-b border-gray-800">
            <th className="pb-3 pr-4">Product</th>
            <th className="pb-3 pr-4">Size</th>
            <th className="pb-3 pr-4">Stock</th>
            <th className="pb-3 pr-4">Velocity</th>
            <th className="pb-3 pr-4">Days Left</th>
            <th className="pb-3 pr-4">Status</th>
            <th className="pb-3 pr-4">Reorder Qty</th>
            <th className="pb-3">Order By</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-800/50">
          {predictions.map((p) => (
            <tr key={p.id} className="hover:bg-gray-900/50">
              <td className="py-3 pr-4 text-white font-medium">{p.product_name}</td>
              <td className="py-3 pr-4 text-gray-400">{p.size}</td>
              <td className="py-3 pr-4 text-gray-300">{p.current_stock}</td>
              <td className="py-3 pr-4 text-gray-300">{p.daily_velocity.toFixed(1)}/day</td>
              <td className={`py-3 pr-4 font-semibold ${urgencyColor(p.days_until_stockout)}`}>
                {p.days_until_stockout ?? "—"}
              </td>
              <td className="py-3 pr-4">
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${urgencyColor(p.days_until_stockout)} bg-gray-800`}>
                  {urgencyBadge(p.days_until_stockout)}
                </span>
              </td>
              <td className="py-3 pr-4 text-gray-300">{p.recommended_reorder_qty}</td>
              <td className="py-3 text-gray-400">{p.recommended_order_by_date ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
