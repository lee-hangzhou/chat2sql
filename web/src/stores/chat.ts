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

/** 节点名称到中文标签的映射 */
const NODE_LABELS: Record<string, string> = {
  schema_retriever: '检索表结构',
  intent_parse: '解析意图',
  follow_up: '追问确认',
  sql_generator: '生成 SQL',
  sql_validator: '校验 SQL',
  executor: '执行查询',
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

/** 将所有 running 状态的节点标记为 failed 并计算最终耗时 */
function failRunningSteps(steps: NodeStep[]): NodeStep[] {
  const now = Date.now()
  return steps.map((step) =>
    step.status === 'running'
      ? { ...step, status: 'failed' as const, elapsedMs: now - step.startTime }
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
      set({
        messages: detail.messages,
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

    // 乐观追加用户消息
    set((s) => ({
      messages: [...s.messages, { role: 'user' as const, content }],
      sending: true,
      currentNode: null,
      nodeSteps: [],
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
            const { sql, execute_result } = data as unknown as SSEResult
            const resultMsg = sql ? `\`\`\`sql\n${sql}\n\`\`\`` : '查询完成'
            set({
              sqlResult: sql,
              executeResult: execute_result,
              currentNode: null,
              messages: [
                ...get().messages,
                { role: 'assistant', content: resultMsg },
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
              nodeSteps: failRunningSteps(s.nodeSteps),
              messages: [
                ...get().messages,
                { role: 'assistant', content: '执行出错，请重试' },
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
        errorMessage: e instanceof Error ? e.message : '网络错误',
        currentNode: null,
        nodeSteps: failRunningSteps(s.nodeSteps),
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
