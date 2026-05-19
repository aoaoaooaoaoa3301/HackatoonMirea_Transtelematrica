import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { CompletionEntry } from '@/types';

interface CompletionLineProps {
  data: CompletionEntry[];
}

export function CompletionLine({ data }: CompletionLineProps) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Динамика завершения задач</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={280}>
          <AreaChart data={data}>
            <defs>
              <linearGradient id="colorCompletion" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#059669" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#059669" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            <XAxis dataKey="bucket_key" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip
              contentStyle={{
                backgroundColor: 'hsl(var(--card))',
                border: '1px solid hsl(var(--border))',
                borderRadius: '8px',
                fontSize: '12px',
              }}
              formatter={(value: number, name: string) => {
                if (name === 'completion_pct') return [`${value}%`, 'Завершено %'];
                if (name === 'done') return [value, 'Завершено'];
                if (name === 'total') return [value, 'Всего'];
                return [value, name];
              }}
            />
            <Area
              type="monotone"
              dataKey="completion_pct"
              stroke="#059669"
              fillOpacity={1}
              fill="url(#colorCompletion)"
              strokeWidth={2}
            />
            <Line type="monotone" dataKey="total" stroke="#64748b" strokeDasharray="5 5" dot={false} />
            <Line type="monotone" dataKey="done" stroke="#059669" dot={{ r: 3 }} strokeWidth={2} />
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
