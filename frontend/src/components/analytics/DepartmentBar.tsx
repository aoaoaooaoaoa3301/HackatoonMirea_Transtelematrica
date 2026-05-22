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
    <Card className="h-full flex flex-col">
      <CardHeader className="pb-2 flex-none">
        <CardTitle className="text-base">Задачи по отделам</CardTitle>
      </CardHeader>
      <CardContent className="flex-1 relative min-h-[280px]">
        <div className="absolute inset-0 pb-10 px-2 overflow-x-auto overflow-y-hidden">
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
                <Legend 
                  verticalAlign="bottom" 
                  height={36} 
                  iconType="circle"
                  iconSize={8}
                  formatter={(value) => <span className="text-[13px] font-medium text-muted-foreground mr-3">{value}</span>}
                  wrapperStyle={{ bottom: 0, paddingBottom: 10 }}
                />
                <Bar dataKey="done" name="Завершено" stackId="a" fill="#10B981" radius={[0, 0, 0, 0]} opacity={0.9} className="hover:opacity-100 transition-opacity" />
                <Bar dataKey="in_progress" name="В работе" stackId="a" fill="#3B82F6" opacity={0.9} className="hover:opacity-100 transition-opacity" />
                <Bar dataKey="overdue" name="Просрочено" stackId="a" fill="#EF4444" radius={[0, 4, 4, 0]} opacity={0.9} className="hover:opacity-100 transition-opacity" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}