import { create } from 'zustand'
import * as chatApi from '../api/chat'
import type {
  Conversation,
  Message,
  NodeStep,
  SSEError,
  SSEFollowUp,
  SSEResult,
} from '../types'

const FALLBACK_RESULT_MSG = '查询完成'
const FALLBACK_ERROR_MSG = '执行出错，请重试'
const FALLBACK_NETWORK_ERROR = '网络错误'

/** 节点名称到中文标签的映射 */
const NODE_LABELS: Record<string, string> = {
  schema_retriever: '检索表结构',
  intent_parse: '解析意图',
  follow_up: '追问确认',
  sql_generator: '生成 SQL',
  sql_validator: '校验 SQL',
  sql_selector: '选优 SQL',
  sql_judge: '语义裁决',
  executor: '执行查询',
  result_summarizer: '总结结果',
}

interface ChatState {
  conversations: Conversation[]
  activeId: number | null
  messages: Message[]
  /** 当前 graph 执行到的节点（用于展示进度） */
  currentNode: string | null
  /** 节点执行步骤列表（仅追加已触发的节点） */
  nodeSteps: NodeStep[]
  /** 追问问题 */
  followUpQuestion: string | null
  /** SQL 结果 */
  sqlResult: string | null
  executeResult: Record<string, unknown>[] | null
  /** 错误信息 */
  errorMessage: string | null
  /** 是否正在发送 */
  sending: boolean
  loading: boolean

  loadConversations: () => Promise<void>
  createConversation: () => Promise<number>
  selectConversation: (id: number) => Promise<void>
  deleteConversation: (id: number) => Promise<void>
  sendMessage: (content: string) => Promise<void>
  reset: () => void
}

/** 标记失败：running 节点标红，若无 running 则将最后一个 completed 节点标红 */
function failStepsOnError(steps: NodeStep[]): NodeStep[] {
  const now = Date.now()
  const hasRunning = steps.some((s) => s.status === 'running')

  if (hasRunning) {
    return steps.map((step) =>
      step.status === 'running'
        ? { ...step, status: 'failed' as const, elapsedMs: now - step.startTime }
        : step
    )
  }

  const lastCompletedIdx = steps.findLastIndex((s) => s.status === 'completed')
  if (lastCompletedIdx === -1) return steps

  return steps.map((step, i) =>
    i === lastCompletedIdx
      ? { ...step, status: 'failed' as const }
      : step
  )
}

export const useChatStore = create<ChatState>((set, get) => ({
  conversations: [],
  activeId: null,
  messages: [],
  currentNode: null,
  nodeSteps: [],
  followUpQuestion: null,
  sqlResult: null,
  executeResult: null,
  errorMessage: null,
  sending: false,
  loading: false,

  loadConversations: async () => {
    set({ loading: true })
    try {
      const res = await chatApi.listConversations()
      set({ conversations: res.items })
    } finally {
      set({ loading: false })
    }
  },

  createConversation: async () => {
    const conv = await chatApi.createConversation()
    set((s) => ({
      conversations: [conv, ...s.conversations],
      activeId: conv.id,
      messages: [],
      currentNode: null,
      nodeSteps: [],
      followUpQuestion: null,
      sqlResult: null,
      executeResult: null,
      errorMessage: null,
    }))
    return conv.id
  },

  selectConversation: async (id) => {
    set({
      activeId: id,
      messages: [],
      currentNode: null,
      nodeSteps: [],
      followUpQuestion: null,
      sqlResult: null,
      executeResult: null,
      errorMessage: null,
      loading: true,
    })
    try {
      const detail = await chatApi.getConversationDetail(id)
      const msgs = detail.messages
      if (detail.execute_result && msgs.length > 0) {
        for (let i = msgs.length - 1; i >= 0; i--) {
          if (msgs[i].role === 'assistant' && msgs[i].content.includes('```sql')) {
            msgs[i] = { ...msgs[i], executeResult: detail.execute_result }
            break
          }
        }
      }
      set({
        messages: msgs,
        sqlResult: detail.sql,
        executeResult: detail.execute_result,
        errorMessage: detail.error_message,
        followUpQuestion: detail.follow_up_question,
      })
    } finally {
      set({ loading: false })
    }
  },

  deleteConversation: async (id) => {
    await chatApi.deleteConversation(id)
    set((s) => {
      const filtered = s.conversations.filter((c) => c.id !== id)
      const isActive = s.activeId === id
      return {
        conversations: filtered,
        ...(isActive
          ? {
              activeId: null,
              messages: [],
              currentNode: null,
              nodeSteps: [],
              followUpQuestion: null,
              sqlResult: null,
              executeResult: null,
              errorMessage: null,
            }
          : {}),
      }
    })
  },

  sendMessage: async (content) => {
    const { activeId } = get()
    if (!activeId) return

    const isFollowUpReply = !!get().followUpQuestion

    // 乐观追加用户消息，追问回复时保留已有节点进度
    set((s) => ({
      messages: [...s.messages, { role: 'user' as const, content }],
      sending: true,
      currentNode: null,
      nodeSteps: isFollowUpReply ? s.nodeSteps : [],
      followUpQuestion: null,
      sqlResult: null,
      executeResult: null,
      errorMessage: null,
    }))

    try {
      const stream = chatApi.sendMessageStream(activeId, content)
      for await (const { event, data } of stream) {
        switch (event) {
          case 'node_start': {
            const nodeName = (data as unknown as { node: string }).node
            const label = NODE_LABELS[nodeName] || nodeName
            set((s) => ({
              currentNode: label,
              nodeSteps: [
                ...s.nodeSteps,
                {
                  node: nodeName,
                  label,
                  status: 'running',
                  startTime: Date.now(),
                  elapsedMs: null,
                },
              ],
            }))
            break
          }
          case 'node_complete': {
            const nodeName = (data as unknown as { node: string }).node
            const now = Date.now()
            set((s) => ({
              currentNode: null,
              nodeSteps: s.nodeSteps.map((step) =>
                step.node === nodeName && step.status === 'running'
                  ? { ...step, status: 'completed', elapsedMs: now - step.startTime }
                  : step
              ),
            }))
            break
          }
          case 'follow_up': {
            const { question } = data as unknown as SSEFollowUp
            set({
              followUpQuestion: question,
              currentNode: null,
              messages: [
                ...get().messages,
                { role: 'assistant', content: question },
              ],
            })
            break
          }
          case 'result': {
            const { sql, summary, execute_result } = data as unknown as SSEResult
            const content = summary || (sql ? `\`\`\`sql\n${sql}\n\`\`\`` : FALLBACK_RESULT_MSG)
            set({
              sqlResult: sql,
              executeResult: execute_result,
              currentNode: null,
              messages: [
                ...get().messages,
                { role: 'assistant', content, executeResult: execute_result },
              ],
            })
            break
          }
          case 'error': {
            const { error_message } = data as unknown as SSEError
            if (error_message) {
              console.error('[chat] agent error:', error_message)
            }
            set((s) => ({
              errorMessage: error_message || null,
              currentNode: null,
              nodeSteps: failStepsOnError(s.nodeSteps),
              messages: [
                ...get().messages,
                { role: 'assistant', content: FALLBACK_ERROR_MSG },
              ],
            }))
            break
          }
          case 'done':
            break
        }
      }
    } catch (e) {
      set((s) => ({
        errorMessage: e instanceof Error ? e.message : FALLBACK_NETWORK_ERROR,
        currentNode: null,
        nodeSteps: failStepsOnError(s.nodeSteps),
      }))
    } finally {
      set({ sending: false })
      // 刷新对话列表以更新标题和状态
      get().loadConversations()
    }
  },

  reset: () =>
    set({
      conversations: [],
      activeId: null,
      messages: [],
      currentNode: null,
      nodeSteps: [],
      followUpQuestion: null,
      sqlResult: null,
      executeResult: null,
      errorMessage: null,
      sending: false,
      loading: false,
    }),
}))
