import { create } from 'zustand'
import * as chatApi from '../api/chat'
import type {
  AgentResponse,
  CanvasState,
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
  chart_advisor: '图表建议',
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
  /** 画布状态 */
  canvasState: CanvasState

  loadConversations: () => Promise<void>
  createConversation: () => Promise<number>
  selectConversation: (id: number) => Promise<void>
  deleteConversation: (id: number) => Promise<void>
  sendMessage: (content: string) => Promise<void>
  reset: () => void
  setCanvasLoading: (loading: boolean) => void
  clearCanvas: () => void
  setCanvasFromResponse: (userMessage: string, response: AgentResponse) => void
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
  canvasState: {
    responseType: null,
    chartOption: null,
    tableData: null,
    tableColumns: [],
    summaryText: '',
    insightReport: null,
    queryTitle: '',
    isLoading: false,
  },

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
    get().clearCanvas()
    return conv.id
  },

  selectConversation: async (id) => {
    // 立即清空画布并显示骨架屏
    get().clearCanvas()
    get().setCanvasLoading(true)

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
      const msgs: Message[] = detail.messages.map((m) => ({
        role: m.role,
        content: m.content,
        executeResult: (m as Record<string, unknown>).execute_result as Message['executeResult'] ?? undefined,
        chartOption: (m as Record<string, unknown>).chart_option as Message['chartOption'] ?? undefined,
      }))
      set({
        messages: msgs,
        sqlResult: detail.sql,
        executeResult: detail.execute_result,
        errorMessage: detail.error_message,
        followUpQuestion: detail.follow_up_question,
      })

      // 从对话详情恢复画布状态
      const tableData = detail.execute_result
        ? (detail.execute_result as Record<string, any>[])
        : null
      const tableColumns = tableData && tableData.length > 0 ? Object.keys(tableData[0]) : []
      const chartOption = (detail.chart_option as Record<string, any>) ?? null
      const lastUserMsg = [...msgs].reverse().find((m) => m.role === 'user')?.content ?? ''
      const lastAssistantMsg = [...msgs].reverse().find((m) => m.role === 'assistant')?.content ?? ''

      let responseType: CanvasState['responseType'] = null
      if (tableData || chartOption) {
        responseType = 'query'
      } else if (msgs.length > 0) {
        responseType = 'chat'
      }

      set({
        canvasState: {
          responseType,
          chartOption,
          tableData,
          tableColumns,
          summaryText: lastAssistantMsg,
          insightReport: null,
          queryTitle: lastUserMsg,
          isLoading: false,
        },
      })
    } finally {
      set({ loading: false })
    }
  },

  deleteConversation: async (id) => {
    await chatApi.deleteConversation(id)
    const isActive = get().activeId === id
    set((s) => {
      const filtered = s.conversations.filter((c) => c.id !== id)
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
    if (isActive) get().clearCanvas()
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

    get().setCanvasLoading(true)

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
            get().setCanvasLoading(false)
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
            const { sql, summary, execute_result, chart_option } = data as unknown as SSEResult
            const msgContent = summary || (sql ? `\`\`\`sql\n${sql}\n\`\`\`` : FALLBACK_RESULT_MSG)
            set({
              sqlResult: sql,
              executeResult: execute_result,
              currentNode: null,
              messages: [
                ...get().messages,
                {
                  role: 'assistant',
                  content: msgContent,
                  executeResult: execute_result,
                  chartOption: chart_option,
                },
              ],
            })
            const agentResponse = {
              text: msgContent,
              charts: chart_option ? [chart_option as Record<string, any>] : [],
              insight_report: null,
              response_type: 'query' as const,
              execute_result,
            } as AgentResponse
            get().setCanvasFromResponse(content, agentResponse)
            break
          }
          case 'error': {
            const { error_message } = data as unknown as SSEError
            if (error_message) {
              console.error('[chat] agent error:', error_message)
            }
            get().setCanvasLoading(false)
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
      get().setCanvasLoading(false)
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

  setCanvasLoading: (loading) =>
    set((s) => ({ canvasState: { ...s.canvasState, isLoading: loading } })),

  clearCanvas: () =>
    set({
      canvasState: {
        responseType: null,
        chartOption: null,
        tableData: null,
        tableColumns: [],
        summaryText: '',
        insightReport: null,
        queryTitle: '',
        isLoading: false,
      },
    }),

  setCanvasFromResponse: (userMessage, response) => {
    const rawData = (response as any).execute_result ?? null
    const tableData: Record<string, any>[] | null = Array.isArray(rawData) ? rawData : null
    const tableColumns = tableData && tableData.length > 0 ? Object.keys(tableData[0]) : []
    set({
      canvasState: {
        responseType: response.response_type,
        chartOption: response.charts?.[0] ?? null,
        tableData,
        tableColumns,
        summaryText: response.text,
        insightReport: response.insight_report ?? null,
        queryTitle: userMessage,
        isLoading: false,
      },
    })
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
      canvasState: {
        responseType: null,
        chartOption: null,
        tableData: null,
        tableColumns: [],
        summaryText: '',
        insightReport: null,
        queryTitle: '',
        isLoading: false,
      },
    }),
}))
