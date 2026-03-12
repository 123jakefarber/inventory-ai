interface StatsCardProps {
  label: string;
  value: number | string;
  color?: "red" | "amber" | "green" | "blue" | "white";
}

const colorMap = {
  red: "text-red-400",
  amber: "text-amber-400",
  green: "text-green-400",
  blue: "text-blue-400",
  white: "text-white",
};

export default function StatsCard({ label, value, color = "white" }: StatsCardProps) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <p className="text-xs text-gray-500 uppercase tracking-wide">{label}</p>
      <p className={`text-3xl font-bold mt-2 ${colorMap[color]}`}>{value}</p>
    </div>
  );
}
