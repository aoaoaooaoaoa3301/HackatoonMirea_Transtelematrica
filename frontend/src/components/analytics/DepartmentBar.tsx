import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface DeptData {
  department_name: string;
  done: number;
  in_progress: number;
  overdue: number;
}

interface DepartmentBarProps {
  data: DeptData[];
}

export function DepartmentBar({ data }: DepartmentBarProps) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Задачи по отделам</CardTitle>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        <div className="min-w-[360px]">
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={data} layout="vertical" margin={{ left: 20 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="hsl(var(--border))" />
            <XAxis type="number" tick={{ fontSize: 12 }} />
            <YAxis
              dataKey="department_name"
              type="category"
              width={120}
              tick={{ fontSize: 11 }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'hsl(var(--card))',
                border: '1px solid hsl(var(--border))',
                borderRadius: '8px',
                fontSize: '12px',
              }}
            />
            <Legend wrapperStyle={{ fontSize: '12px' }} />
            <Bar dataKey="done" name="Завершено" stackId="a" fill="#059669" radius={[0, 0, 0, 0]} />
            <Bar dataKey="in_progress" name="В работе" stackId="a" fill="#2563eb" />
            <Bar dataKey="overdue" name="Просрочено" stackId="a" fill="#e11d48" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
