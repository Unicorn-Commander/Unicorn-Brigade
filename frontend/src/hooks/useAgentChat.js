import { useState, useRef, useCallback } from 'react';
import api from '../services/api';

/**
 * Headless per-agent streaming chat. One instance owns one conversation with one
 * agent — mount several (e.g. one per floating comms window) to talk to multiple
 * agents independently and in parallel.
 *
 * Mirrors the backend SSE protocol: start / tool_call / tool_result / token /
 * complete / error (+ [DONE]). Routes through api.streamAgentChat so it carries
 * auth headers + credentials.
 */
export function useAgentChat(agent, { model, initialMessages } = {}) {
  // Seed from a prior conversation (e.g. promoting a briefing answer). Re-id so
  // the seeds never collide with this instance's own m-N ids, and mark them done.
  const [messages, setMessages] = useState(() =>
    (initialMessages || []).map((m, i) => ({ ...m, id: `seed-${i}`, isStreaming: false }))
  );
  const [isStreaming, setIsStreaming] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [currentTool, setCurrentTool] = useState(null);
  const abortRef = useRef(null);
  const idRef = useRef(0);
  const nextId = () => `m-${(idRef.current += 1)}`;

  const send = useCallback(
    async (text) => {
      const content = (text ?? '').trim();
      if (!content || !agent || isStreaming) return;

      const history = messages.map((m) => ({ role: m.role, content: m.content }));
      const userMsg = { id: nextId(), role: 'user', content };
      const assistantId = nextId();
      const assistantMsg = {
        id: assistantId,
        role: 'assistant',
        content: '',
        toolCalls: [],
        model: model || agent.model,
        isStreaming: true,
      };
      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setIsThinking(true);
      setIsStreaming(true);
      setCurrentTool(null);

      const controller = new AbortController();
      abortRef.current = controller;
      let acc = '';
      let gotToken = false;

      try {
        const res = await api.streamAgentChat(
          agent.id,
          {
            message: content,
            stream: true,
            history,
            model: model || agent.model,
            temperature: agent.temperature,
          },
          { signal: controller.signal }
        );
        if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

        const reader = res.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          for (const line of chunk.split('\n')) {
            if (!line.startsWith('data: ')) continue;
            const payload = line.slice(6).trim();
            if (!payload || payload === '[DONE]') continue;
            let ev;
            try {
              ev = JSON.parse(payload);
            } catch {
              continue;
            }

            if (ev.type === 'start') {
              if (!ev.tools?.length) setIsThinking(false);
            } else if (ev.type === 'tool_call') {
              setIsThinking(false);
              setCurrentTool(ev.name);
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, toolCalls: [...(m.toolCalls || []), { name: ev.name, arguments: ev.arguments }] }
                    : m
                )
              );
            } else if (ev.type === 'tool_result') {
              setCurrentTool(null);
              setMessages((prev) =>
                prev.map((m) => {
                  if (m.id !== assistantId) return m;
                  const calls = (m.toolCalls || []).map((tc) =>
                    tc.name === ev.name && tc.result === undefined
                      ? { ...tc, result: ev.result, error: ev.error }
                      : tc
                  );
                  return { ...m, toolCalls: calls };
                })
              );
            } else if (ev.type === 'token') {
              if (!gotToken) {
                gotToken = true;
                setIsThinking(false);
              }
              acc += ev.content || '';
              setMessages((prev) => prev.map((m) => (m.id === assistantId ? { ...m, content: acc } : m)));
            } else if (ev.type === 'complete') {
              const finalContent = ev.content || acc;
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? {
                        ...m,
                        content: finalContent,
                        model: ev.model || m.model,
                        toolCalls: ev.toolCalls || m.toolCalls || [],
                        isStreaming: false,
                      }
                    : m
                )
              );
            } else if (ev.type === 'error') {
              throw new Error(ev.error || 'stream error');
            }
          }
        }
        setMessages((prev) => prev.map((m) => (m.id === assistantId ? { ...m, isStreaming: false } : m)));
      } catch (err) {
        const aborted = controller.signal.aborted;
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  content: m.content || (aborted ? '' : `⚠️ ${err.message}`),
                  isError: !aborted && !m.content,
                  isStreaming: false,
                }
              : m
          )
        );
      } finally {
        setIsThinking(false);
        setIsStreaming(false);
        setCurrentTool(null);
        abortRef.current = null;
      }
    },
    [agent, messages, isStreaming, model]
  );

  const abort = useCallback(() => abortRef.current?.abort(), []);
  const reset = useCallback(() => setMessages([]), []);

  return { messages, isStreaming, isThinking, currentTool, send, abort, reset };
}

export default useAgentChat;
