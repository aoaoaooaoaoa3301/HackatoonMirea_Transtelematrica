import { useMutation, useQuery } from '@tanstack/react-query';
import { QRCodeSVG } from 'qrcode.react';
import { Bot, CheckCircle2, Copy, Link2, RefreshCw, QrCode, ExternalLink } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { getTelegramStatus, startTelegramLink, type TelegramLinkCode } from '@/api/telegram';
import { queryClient } from '@/lib/queryClient';

const TELEGRAM_BOT_URL = 'https://t.me/TRANSTELEMATIKAAIASSISTANT_BOT';

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
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">Telegram-бот</h1>
        <p className="text-sm text-muted-foreground">
          Подключение Telegram к текущему аккаунту для команд AI-помощника.
        </p>
      </div>

      <Card className="max-w-2xl">
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-md bg-primary/10 text-primary">
              <QrCode data-icon="inline-start" />
            </div>
            <div className="flex flex-col gap-1">
              <CardTitle>QR-код Telegram-бота</CardTitle>
              <CardDescription>Отсканируйте код или откройте бота по ссылке.</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="flex flex-col gap-4 sm:flex-row sm:items-center">
          <div className="flex w-full max-w-72 justify-center rounded-lg bg-white p-4">
            <QRCodeSVG
              value={TELEGRAM_BOT_URL}
              size={224}
              level="M"
              includeMargin
              aria-label="QR-код Telegram-бота @TRANSTELEMATIKAAIASSISTANT_BOT"
            />
          </div>
          <div className="flex flex-1 flex-col gap-3">
            <div>
              <p className="text-sm font-medium">@TRANSTELEMATIKAAIASSISTANT_BOT</p>
              <p className="text-sm text-muted-foreground">
                Используйте этот QR для быстрого перехода к боту в Telegram.
              </p>
            </div>
            <a href={TELEGRAM_BOT_URL} target="_blank" rel="noopener noreferrer">
              <Button className="w-full sm:w-auto">
                <ExternalLink data-icon="inline-start" />
                Открыть Telegram-бота
              </Button>
            </a>
          </div>
        </CardContent>
      </Card>

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
                <div className="flex flex-col gap-4 rounded-md border p-4 sm:flex-row sm:items-start">
                  {/* QR — scan to auto-link without typing the code.
                      Shown only when the bot username is configured
                      (otherwise deep_link is null → fall back to code). */}
                  {linkCode.deep_link && (
                    <div className="flex flex-col items-center gap-2 shrink-0">
                      <div className="rounded-lg bg-white p-3">
                        <QRCodeSVG value={linkCode.deep_link} size={160} level="M" />
                      </div>
                      <span className="flex items-center gap-1 text-xs text-muted-foreground">
                        <QrCode className="h-3 w-3" />
                        Наведите камеру Telegram
                      </span>
                    </div>
                  )}

                  <div className="flex flex-1 flex-col gap-3">
                    {linkCode.deep_link && (
                      <a href={linkCode.deep_link} target="_blank" rel="noopener noreferrer">
                        <Button className="w-full sm:w-auto">
                          <ExternalLink data-icon="inline-start" />
                          Открыть бота и подключить
                        </Button>
                      </a>
                    )}

                    <div className="flex flex-col gap-1">
                      <span className="text-xs text-muted-foreground">
                        Или введите код вручную командой <code>/link</code>:
                      </span>
                      <div className="flex flex-wrap items-center gap-3">
                        <span className="font-mono text-3xl font-semibold tracking-normal">
                          {linkCode.code}
                        </span>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => navigator.clipboard.writeText(`/link ${linkCode.code}`)}
                        >
                          <Copy data-icon="inline-start" />
                          Скопировать
                        </Button>
                      </div>
                    </div>

                    <p className="text-sm text-muted-foreground">{linkCode.instruction}</p>
                    {expiresAt && (
                      <p className="text-xs text-muted-foreground">Код действует до {expiresAt}</p>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
