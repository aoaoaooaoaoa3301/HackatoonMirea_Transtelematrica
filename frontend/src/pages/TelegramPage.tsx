import { useMutation, useQuery } from '@tanstack/react-query';
import { Bot, CheckCircle2, Copy, Link2, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { getTelegramStatus, startTelegramLink, type TelegramLinkCode } from '@/api/telegram';
import { queryClient } from '@/lib/queryClient';

export default function TelegramPage() {
  const statusQuery = useQuery({
    queryKey: ['telegram-status'],
    queryFn: getTelegramStatus,
  });

  const linkMutation = useMutation({
    mutationFn: startTelegramLink,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['telegram-status'] });
    },
  });

  const linkCode = linkMutation.data as TelegramLinkCode | undefined;
  const expiresAt = linkCode ? new Date(linkCode.expires_at).toLocaleString('ru-RU') : null;

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">Telegram-бот</h1>
        <p className="text-sm text-muted-foreground">
          Подключение Telegram к текущему аккаунту для команд AI-помощника.
        </p>
      </div>

      <Card className="max-w-2xl">
        <CardHeader>
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="flex size-10 items-center justify-center rounded-md bg-primary/10 text-primary">
                <Bot data-icon="inline-start" />
              </div>
              <div className="flex flex-col gap-1">
                <CardTitle>Статус подключения</CardTitle>
                <CardDescription>Текущий Telegram-аккаунт пользователя.</CardDescription>
              </div>
            </div>
            {statusQuery.isLoading ? (
              <Skeleton className="h-6 w-28" />
            ) : statusQuery.data?.connected ? (
              <Badge variant="secondary">Подключен</Badge>
            ) : (
              <Badge variant="outline">Не подключен</Badge>
            )}
          </div>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {statusQuery.data?.connected ? (
            <div className="flex items-center gap-3 rounded-md border p-3">
              <CheckCircle2 data-icon="inline-start" />
              <div className="flex flex-col gap-1 text-sm">
                <span className="font-medium">
                  {statusQuery.data.telegram_username
                    ? `@${statusQuery.data.telegram_username}`
                    : `Telegram ID ${statusQuery.data.telegram_user_id}`}
                </span>
                {statusQuery.data.linked_at && (
                  <span className="text-muted-foreground">
                    Подключен {new Date(statusQuery.data.linked_at).toLocaleString('ru-RU')}
                  </span>
                )}
              </div>
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              <Button onClick={() => linkMutation.mutate()} disabled={linkMutation.isPending}>
                {linkMutation.isPending ? <RefreshCw data-icon="inline-start" /> : <Link2 data-icon="inline-start" />}
                Получить код подключения
              </Button>

              {linkCode && (
                <div className="flex flex-col gap-3 rounded-md border p-4">
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="font-mono text-3xl font-semibold tracking-normal">{linkCode.code}</span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => navigator.clipboard.writeText(`/link ${linkCode.code}`)}
                    >
                      <Copy data-icon="inline-start" />
                      Скопировать
                    </Button>
                  </div>
                  <p className="text-sm text-muted-foreground">{linkCode.instruction}</p>
                  {expiresAt && <p className="text-xs text-muted-foreground">Код действует до {expiresAt}</p>}
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
