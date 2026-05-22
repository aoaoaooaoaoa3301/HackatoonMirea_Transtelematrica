import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { STATUS_LABELS, STATUS_CHART_COLORS } from '@/lib/statusUtils';
import type { Status } from '@/types';

interface StatusPieProps {
  data: { status: Status; count: number }[];
  title?: string;
}

export function StatusPie({ data, title = 'Распределение по статусам' }: StatusPieProps) {
  const chartData = data.map((d) => ({
    name: STATUS_LABELS[d.status],
    value: d.count,
    color: STATUS_CHART_COLORS[d.status],
  }));

  return (
    <Card className="h-full flex flex-col">
      <CardHeader className="pb-2 flex-none">
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent className="flex-1 min-h-[280px]">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={chartData}
              cx="50%"
              cy="50%"
              innerRadius={60}
              outerRadius={100}
              paddingAngle={3}
              dataKey="value"
              label={({ percent }) => `${(percent * 100).toFixed(0)}%`}
              labelLine={false}
            >
              {chartData.map((entry, index) => (
                <Cell key={index} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip
              formatter={(value: number) => [`${value} задач`, '']}
              contentStyle={{
                backgroundColor: 'hsl(var(--card))',
                border: '1px solid hsl(var(--border))',
                borderRadius: '8px',
              }}
            />
            <Legend
              formatter={(value) => <span className="text-xs">{value}</span>}
            />
          </PieChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
