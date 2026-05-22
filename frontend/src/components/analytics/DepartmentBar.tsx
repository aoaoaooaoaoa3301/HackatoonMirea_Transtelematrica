import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
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

const legendItems = [
  { label: 'Завершено', color: '#10B981' },
  { label: 'В работе', color: '#3B82F6' },
  { label: 'Просрочено', color: '#EF4444' },
];

export function DepartmentBar({ data }: DepartmentBarProps) {
  return (
    <Card className="h-full flex flex-col">
      <CardHeader className="pb-2 flex-none">
        <CardTitle className="text-base">Задачи по отделам</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col">
        <div className="h-[280px] min-h-[280px] overflow-x-auto overflow-y-hidden px-2">
          <div className="min-w-[420px] h-full w-full py-2">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data} layout="vertical" margin={{ left: 20, right: 20, top: 0, bottom: 0 }} barSize={16}>
                <CartesianGrid strokeDasharray="4 4" horizontal={false} stroke="hsl(var(--border))" opacity={0.5} />
                <XAxis 
                  type="number" 
                  tick={{ fontSize: 13, fill: 'hsl(var(--muted-foreground))', fontFamily: 'inherit' }} 
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  dataKey="department_name"
                  type="category"
                  width={140}
                  tick={{ fontSize: 13, fill: 'hsl(var(--muted-foreground))', fontFamily: 'inherit', fontWeight: 500 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  cursor={{ fill: 'hsl(var(--muted)/0.4)' }}
                  contentStyle={{
                    backgroundColor: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '8px',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
                    fontFamily: 'inherit',
                    fontSize: '13px'
                  }}
                  itemStyle={{ fontFamily: 'inherit' }}
                />
                <Bar dataKey="done" name="Завершено" stackId="a" fill="#10B981" radius={[0, 0, 0, 0]} opacity={0.9} className="hover:opacity-100 transition-opacity" />
                <Bar dataKey="in_progress" name="В работе" stackId="a" fill="#3B82F6" opacity={0.9} className="hover:opacity-100 transition-opacity" />
                <Bar dataKey="overdue" name="Просрочено" stackId="a" fill="#EF4444" radius={[0, 4, 4, 0]} opacity={0.9} className="hover:opacity-100 transition-opacity" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="flex h-12 flex-none flex-wrap items-start justify-center gap-x-4 gap-y-1 pt-2">
          {legendItems.map((entry) => (
            <div key={entry.label} className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: entry.color }} />
              <span>{entry.label}</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
