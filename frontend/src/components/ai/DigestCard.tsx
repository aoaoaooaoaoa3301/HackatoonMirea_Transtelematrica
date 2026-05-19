import { useQuery } from '@tanstack/react-query';
import { Sparkles, AlertCircle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { getDigest } from '@/api/ai';

interface DigestCardProps {
  scope?: string;
  id?: string;
  period?: string;
}

export function DigestCard({ scope = 'all', id, period = 'week' }: DigestCardProps) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['ai', 'digest', scope, id, period],
    queryFn: () => getDigest({ scope, id, period }),
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-amber-500" />
          AI-сводка за неделю
        </CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading && (
          <div className="space-y-2">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-5/6" />
          </div>
        )}
        {isError && (
          <div className="flex items-center gap-2 text-muted-foreground text-sm py-4">
            <AlertCircle className="h-4 w-4" />
            AI-сервис временно недоступен
          </div>
        )}
        {data && (
          <div className="space-y-3">
            <p className="text-sm text-foreground leading-relaxed">{data.summary}</p>
            {data.key_points.length > 0 && (
              <ul className="space-y-1.5">
                {data.key_points.map((point, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-muted-foreground">
                    <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-amber-500 shrink-0" />
                    {point}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
