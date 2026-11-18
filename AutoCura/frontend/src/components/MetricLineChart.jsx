import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatChartTime } from "../utils/format";

export function MetricLineChart({ data, lines, height = 220, unit = "" }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -18 }}>
        <CartesianGrid stroke="var(--border-soft)" vertical={false} />
        <XAxis
          dataKey="timestamp"
          tickFormatter={formatChartTime}
          stroke="var(--text-faint)"
          fontSize={11}
          tickLine={false}
        />
        <YAxis stroke="var(--text-faint)" fontSize={11} tickLine={false} unit={unit} />
        <Tooltip
          labelFormatter={formatChartTime}
          contentStyle={{
            background: "var(--surface-raised)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            fontSize: 12,
          }}
        />
        {lines.map((line) => (
          <Line
            key={line.key}
            type="monotone"
            dataKey={line.key}
            name={line.label}
            stroke={line.color}
            strokeWidth={2}
            dot={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
