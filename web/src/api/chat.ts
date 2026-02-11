import { post, postSSE } from './client'
import type { Conversation, ConversationDetail, PaginatedData } from '../types'

export function createConversation(): Promise<Conversation> {
  return post<Conversation>('/chat/conversations/create')
}

export function listConversations(
  offset = 0,
  limit = 50,
): Promise<PaginatedData<Conversation>> {
  return post<PaginatedData<Conversation>>('/chat/conversations/list', {
    offset,
    limit,
  })
}

export function getConversationDetail(
  conversationId: number,
): Promise<ConversationDetail> {
  return post<ConversationDetail>('/chat/conversations/detail', {
    conversation_id: conversationId,
  })
}

export function deleteConversation(conversationId: number): Promise<null> {
  return post<null>('/chat/conversations/delete', {
    conversation_id: conversationId,
  })
}

export function sendMessageStream(conversationId: number, content: string) {
  return postSSE('/chat/conversations/messages/send', {
    conversation_id: conversationId,
    content,
  })
}
