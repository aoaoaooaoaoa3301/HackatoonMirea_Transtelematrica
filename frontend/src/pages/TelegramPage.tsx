import { useMutation, useQuery } from '@tanstack/react-query';
import { QRCodeSVG } from 'qrcode.react';
import { Bot, CheckCircle2, Copy, Link2, RefreshCw, QrCode, ExternalLink } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { getTelegramStatus, startTelegramLink, type TelegramLinkCode } from '@/api/telegram';
import { queryClient } from '@/lib/queryClient';

const DEFAULT_TELEGRAM_BOT_USERNAME = 'TranstelematikaAIassistant_bot';
const DEFAULT_TELEGRAM_BOT_URL = `https://t.me/${DEFAULT_TELEGRAM_BOT_USERNAME}`;

async function copyToClipboard(text: string) {
  try {
    if (navigator.clipboard?.writeText && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      toast.success('Команда скопирована');
      return;
    }

    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'fixed';
    textarea.style.left = '-9999px';
    textarea.style.top = '0';
    document.body.appendChild(textarea);
    textarea.select();
    const copied = document.execCommand('copy');
    document.body.removeChild(textarea);

    if (!copied) {
      throw new Error('copy command failed');
    }
    toast.success('Команда скопирована');
  } catch {
    toast.error('Не удалось скопировать. Скопируйте команду вручную.');
  }
}

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
  const botUsername = statusQuery.data?.bot_username ?? linkCode?.bot_username ?? DEFAULT_TELEGRAM_BOT_USERNAME;
  const botUrl = `https://t.me/${botUsername}`;
  const personalLink = linkCode
    ? linkCode.deep_link ?? `${botUrl}?start=${encodeURIComponent(linkCode.code)}`
    : null;

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
          <CardTitle className="flex items-center gap-2">
            <QrCode data-icon="inline-start" />
            QR-код Telegram-бота
          </CardTitle>
          <CardDescription>Отсканируйте код, чтобы открыть бота в Telegram.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4 sm:flex-row sm:items-center">
          <div className="w-fit rounded-lg bg-white p-4">
            <QRCodeSVG
              value={botUrl || DEFAULT_TELEGRAM_BOT_URL}
              size={220}
              level="M"
              includeMargin
              aria-label="QR-код Telegram-бота"
            />
          </div>
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1">
              <span className="text-sm text-muted-foreground">Ссылка на бота</span>
              <a
                href={botUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm font-medium text-primary hover:underline"
              >
                @{botUsername}
              </a>
            </div>
            <a href={botUrl} target="_blank" rel="noopener noreferrer">
              <Button variant="outline" className="w-full sm:w-auto">
                <ExternalLink data-icon="inline-start" />
                Открыть бота
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
              <p className="text-sm text-muted-foreground">
                Для привязки нужен персональный одноразовый код. Откройте бота по QR-коду выше и отправьте команду /link с кодом.
              </p>
              <Button onClick={() => linkMutation.mutate()} disabled={linkMutation.isPending}>
                {linkMutation.isPending ? <RefreshCw data-icon="inline-start" /> : <Link2 data-icon="inline-start" />}
                Получить код подключения
              </Button>

              {linkCode && (
                <div className="flex flex-col gap-4 rounded-md border p-4 sm:flex-row sm:items-start">
                  <div className="flex flex-1 flex-col gap-3">
                    {personalLink && (
                      <a href={personalLink} target="_blank" rel="noopener noreferrer">
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
                          onClick={() => copyToClipboard(`/link ${linkCode.code}`)}
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
