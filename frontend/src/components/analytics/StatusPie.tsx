import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
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
      <CardContent className="flex flex-1 flex-col min-h-[280px]">
        <div className="min-h-0 flex-1">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={chartData}
                cx="50%"
                cy="52%"
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
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="flex h-12 flex-none flex-wrap items-start justify-center gap-x-3 gap-y-1 pt-2">
          {chartData.map((entry) => (
            <div key={entry.name} className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ backgroundColor: entry.color }} />
              <span>{entry.name}</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
