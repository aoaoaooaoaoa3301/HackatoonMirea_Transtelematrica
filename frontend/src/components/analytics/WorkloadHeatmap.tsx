import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { WorkloadEntry } from '@/types';

interface WorkloadHeatmapProps {
  data: WorkloadEntry[];
}

function getBarColor(util: number): string {
  if (util > 120) return '#e11d48';
  if (util > 80) return '#d97706';
  return '#059669';
}

export function WorkloadHeatmap({ data }: WorkloadHeatmapProps) {
  const sorted = [...data].sort((a, b) => b.capacity_util - a.capacity_util);

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Загруженность команды</CardTitle>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        <div className="min-w-[480px]">
        <ResponsiveContainer width="100%" height={Math.max(280, sorted.length * 36)}>
          <BarChart data={sorted} layout="vertical" margin={{ left: 20 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="hsl(var(--border))" />
            <XAxis
              type="number"
              domain={[0, 'auto']}
              tick={{ fontSize: 11 }}
              tickFormatter={(v) => `${v}%`}
            />
            <YAxis
              dataKey="full_name"
              type="category"
              width={140}
              tick={{ fontSize: 11 }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'hsl(var(--card))',
                border: '1px solid hsl(var(--border))',
                borderRadius: '8px',
                fontSize: '12px',
              }}
              formatter={(value: number) => [`${value}%`, 'Загрузка']}
              labelFormatter={(label) => label}
            />
            <Bar dataKey="capacity_util" name="Загрузка" radius={[0, 4, 4, 0]}>
              {sorted.map((entry, index) => (
                <Cell key={index} fill={getBarColor(entry.capacity_util)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
