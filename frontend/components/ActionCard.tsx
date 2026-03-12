import type { Alert } from "@/types";

const typeStyles = {
  stockout: { bg: "bg-red-500/10", border: "border-red-500/30", dot: "bg-red-500" },
  reorder: { bg: "bg-amber-500/10", border: "border-amber-500/30", dot: "bg-amber-500" },
  dead_inventory: { bg: "bg-blue-500/10", border: "border-blue-500/30", dot: "bg-blue-500" },
};

export default function ActionCard({ alert }: { alert: Alert }) {
  const style = typeStyles[alert.type] || typeStyles.reorder;

  return (
    <div className={`${style.bg} border ${style.border} rounded-lg p-4 flex items-start gap-3`}>
      <div className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${style.dot}`} />
      <div className="min-w-0">
        <p className="text-sm text-white">{alert.message}</p>
        <p className="text-xs text-gray-500 mt-1">
          {alert.product_name} {alert.sku ? `· ${alert.sku}` : ""}
        </p>
      </div>
    </div>
  );
}
