import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { AlertTriangle, AlertCircle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { getRisks } from '@/api/ai';

interface RiskListProps {
  scope?: string;
  id?: string;
  limit?: number;
}

export function RiskList({ scope = 'all', id, limit }: RiskListProps) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['ai', 'risks', scope, id],
    queryFn: () => getRisks({ scope, id }),
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  const items = limit ? data?.items.slice(0, limit) : data?.items;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-rose-500" />
          Требует внимания
        </CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading && (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="flex gap-2">
                <Skeleton className="h-3 w-3 mt-1 rounded-full shrink-0" />
                <div className="flex-1 space-y-1">
                  <Skeleton className="h-3 w-3/4" />
                  <Skeleton className="h-2 w-full" />
                </div>
              </div>
            ))}
          </div>
        )}
        {isError && (
          <div className="flex items-center gap-2 text-muted-foreground text-sm py-4">
            <AlertCircle className="h-4 w-4" />
            AI-сервис временно недоступен
          </div>
        )}
        {items && items.length === 0 && (
          <p className="text-sm text-muted-foreground py-4 text-center">
            Нет рисков - всё под контролем
          </p>
        )}
        {items && items.length > 0 && (
          <div className="space-y-3">
            {items.map((item, i) => (
              <Link
                key={i}
                to={`/tasks/${item.task_id}`}
                className="flex items-start gap-2 group rounded-md p-1.5 -mx-1.5 hover:bg-accent/50 transition-colors"
              >
                <span
                  className={`mt-1.5 h-2 w-2 rounded-full shrink-0 ${
                    item.risk_level === 'high' ? 'bg-rose-500' : 'bg-amber-500'
                  }`}
                />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate group-hover:underline">
                    {item.task_title}
                  </p>
                  <p className="text-xs text-muted-foreground line-clamp-2">{item.reason}</p>
                </div>
              </Link>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
