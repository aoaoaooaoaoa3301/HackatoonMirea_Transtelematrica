import { useState, useRef, useEffect } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import ReactMarkdown from 'react-markdown';
import { Send, Loader2, Sparkles, Bot, User } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import {
  cancelAssistantAction,
  confirmAssistantAction,
  getAssistantConversation,
  sendAssistantMessage,
} from '@/api/ai';
import type { AIChatMessage } from '@/types';

const CONVERSATION_STORAGE_KEY = 'ttm-ai-assistant-conversation-id';

const quickActions = [
  { label: 'Сводка по моей команде', message: 'Дай сводку по задачам моей команды за эту неделю' },
  { label: 'Что в зоне риска?', message: 'Какие задачи сейчас в зоне риска и почему?' },
  { label: 'Кто перегружен?', message: 'Покажи сотрудников с наибольшей загрузкой' },
  { label: 'Стратегические цели', message: 'Покажи статус стратегических целей компании' },
];

interface AIChatPanelProps {
  contextScope?: 'all' | 'department';
  contextDeptId?: string;
}

export function AIChatPanel({ contextScope = 'all', contextDeptId }: AIChatPanelProps) {
  const [conversationId, setConversationId] = useState<string | undefined>(() => {
    try {
      return localStorage.getItem(CONVERSATION_STORAGE_KEY) || undefined;
    } catch {
      return undefined;
    }
  });
  const [messages, setMessages] = useState<AIChatMessage[]>([]);
  const [input, setInput] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);

  const conversationQuery = useQuery({
    queryKey: ['assistant-conversation', conversationId],
    queryFn: () => getAssistantConversation(conversationId),
  });

  const chatMutation = useMutation({
    mutationFn: (message: string) =>
      sendAssistantMessage({
        message,
        conversation_id: conversationId,
        context:
          contextScope === 'department' && contextDeptId
            ? { department_id: contextDeptId }
            : undefined,
      }),
    onSuccess: (data) => {
      setConversationId(data.conversation_id);
      localStorage.setItem(CONVERSATION_STORAGE_KEY, data.conversation_id);
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: data.text, buttons: data.buttons },
      ]);
    },
    onError: () => {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'Извините, произошла ошибка. Попробуйте ещё раз.',
        },
      ]);
    },
  });

  const actionMutation = useMutation({
    mutationFn: ({ callbackData }: { callbackData: string }) => {
      const [kind, actionId] = callbackData.split(':');
      if (!actionId) {
        throw new Error('Invalid action callback');
      }
      return kind === 'cancel' ? cancelAssistantAction(actionId) : confirmAssistantAction(actionId);
    },
    onMutate: ({ callbackData }) => {
      const isCancel = callbackData.startsWith('cancel');
      setMessages((prev) => [
        ...prev.map((message) => ({ ...message, buttons: undefined })),
        { role: 'user', content: isCancel ? 'Отмена' : 'Подтверждаю' },
      ]);
    },
    onSuccess: (data) => {
      setMessages((prev) => [...prev, { role: 'assistant', content: data.text, buttons: data.buttons }]);
    },
    onError: () => {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Не удалось выполнить действие. Попробуйте ещё раз.' },
      ]);
    },
  });

  const handleSend = (text?: string) => {
    const msg = text ?? input.trim();
    if (!msg) return;
    setMessages((prev) => [...prev, { role: 'user', content: msg }]);
    setInput('');
    chatMutation.mutate(msg);
  };

  useEffect(() => {
    if (conversationQuery.data) {
      setConversationId(conversationQuery.data.conversation_id);
      localStorage.setItem(CONVERSATION_STORAGE_KEY, conversationQuery.data.conversation_id);
      setMessages(
        conversationQuery.data.messages
          .filter((message) => message.role === 'user' || message.role === 'assistant')
          .map((message) => ({ role: message.role, content: message.content }))
      );
    }
  }, [conversationQuery.data]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4" ref={scrollRef}>
        <div className="max-w-3xl mx-auto py-6 space-y-6">
          {messages.length === 0 && (
            <div className="text-center py-16">
              <div className="inline-flex h-16 w-16 items-center justify-center rounded-full bg-primary/10 mb-4">
                <Sparkles className="h-8 w-8 text-primary" />
              </div>
              <h2 className="text-xl font-semibold mb-2">AI-помощник</h2>
              <p className="text-muted-foreground text-sm mb-6 max-w-md mx-auto">
                Задайте вопрос о задачах, команде или стратегических целях. AI проанализирует данные и даст рекомендации.
              </p>
              <div className="flex flex-wrap justify-center gap-2">
                {quickActions.map((action) => (
                  <Badge
                    key={action.label}
                    variant="secondary"
                    className="cursor-pointer hover:bg-primary hover:text-primary-foreground transition-colors px-3 py-1.5 text-sm"
                    onClick={() => handleSend(action.message)}
                  >
                    {action.label}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}
            >
              {msg.role === 'assistant' && (
                <Avatar className="h-8 w-8 shrink-0">
                  <AvatarFallback className="bg-primary/10">
                    <Bot className="h-4 w-4" />
                  </AvatarFallback>
                </Avatar>
              )}
              <div
                className={`rounded-lg px-4 py-2.5 max-w-[80%] ${
                  msg.role === 'user'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted md:max-w-[88%]'
                }`}
              >
                {msg.role === 'assistant' ? (
                  <>
                    <div className="prose prose-sm dark:prose-invert max-w-none leading-relaxed prose-headings:mb-2 prose-headings:mt-0 prose-h2:text-base prose-h3:text-sm prose-p:my-2 prose-ul:my-2 prose-ol:my-2 prose-li:my-1 prose-li:pl-1 prose-strong:text-foreground">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                    {msg.buttons && msg.buttons.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {msg.buttons.map((button) => (
                          <Button
                            key={button.callback_data}
                            size="sm"
                            variant={button.callback_data.startsWith('cancel') ? 'outline' : 'default'}
                            disabled={actionMutation.isPending}
                            onClick={() => actionMutation.mutate({ callbackData: button.callback_data })}
                          >
                            {button.label}
                          </Button>
                        ))}
                      </div>
                    )}
                  </>
                ) : (
                  <p className="text-sm">{msg.content}</p>
                )}
              </div>
              {msg.role === 'user' && (
                <Avatar className="h-8 w-8 shrink-0">
                  <AvatarFallback className="bg-primary/10">
                    <User className="h-4 w-4" />
                  </AvatarFallback>
                </Avatar>
              )}
            </div>
          ))}

          {(chatMutation.isPending || conversationQuery.isLoading || actionMutation.isPending) && (
            <div className="flex gap-3">
              <Avatar className="h-8 w-8 shrink-0">
                <AvatarFallback className="bg-primary/10">
                  <Bot className="h-4 w-4" />
                </AvatarFallback>
              </Avatar>
              <div className="bg-muted rounded-lg px-4 py-3">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {actionMutation.isPending ? 'Выполняю...' : 'Думаю...'}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Quick actions (if messages exist) */}
      {messages.length > 0 && (
        <div className="px-4 pb-2">
          <div className="max-w-3xl mx-auto flex flex-wrap gap-1.5">
            {quickActions.map((action) => (
              <Badge
                key={action.label}
                variant="outline"
                className="cursor-pointer hover:bg-accent text-xs transition-colors"
                onClick={() => handleSend(action.message)}
              >
                {action.label}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <div className="border-t bg-background p-4">
        <div className="max-w-3xl mx-auto flex gap-2">
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Задайте вопрос..."
            rows={1}
            className="min-h-[40px] max-h-[120px] resize-none"
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
          />
          <Button
            size="icon"
            onClick={() => handleSend()}
            disabled={!input.trim() || chatMutation.isPending}
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
