import { useEffect } from 'react'
import { useAuthStore } from './stores/auth'
import { useChatStore } from './stores/chat'
import Header from './components/Header'
import Sidebar from './components/Sidebar'
import ChatArea from './components/ChatArea'

export default function App() {
  const { isAuthenticated, loading, restore } = useAuthStore()
  const { loadConversations, reset } = useChatStore()

  // 初始化：恢复登录态
  useEffect(() => {
    restore()
  }, [restore])

  // 登录/登出后加载或清空对话列表
  useEffect(() => {
    if (loading) return
    if (isAuthenticated) {
      loadConversations()
    } else {
      reset()
    }
  }, [isAuthenticated, loading, loadConversations, reset])

  // 监听 token 过期事件
  useEffect(() => {
    const handler = () => {
      useAuthStore.getState().logout()
    }
    window.addEventListener('auth:expired', handler)
    return () => window.removeEventListener('auth:expired', handler)
  }, [])

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        {isAuthenticated && <Sidebar />}
        <ChatArea />
      </div>
    </div>
  )
}
