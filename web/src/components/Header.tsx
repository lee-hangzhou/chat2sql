import { useState } from 'react'
import { LogOut, User } from 'lucide-react'
import { useAuthStore } from '../stores/auth'
import LoginModal from './LoginModal'

export default function Header() {
  const { user, isAuthenticated, logout } = useAuthStore()
  const [showLogin, setShowLogin] = useState(false)
  const [showMenu, setShowMenu] = useState(false)

  return (
    <>
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-gray-200 bg-white px-6">
        <h1 className="text-lg font-semibold text-gray-800">Chat2SQL</h1>

        <div className="relative">
          {isAuthenticated ? (
            <button
              onClick={() => setShowMenu(!showMenu)}
              className="flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-100"
            >
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-600 text-white">
                {user?.username.charAt(0).toUpperCase()}
              </div>
              <span>{user?.username}</span>
            </button>
          ) : (
            <button
              onClick={() => setShowLogin(true)}
              className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              <User size={16} />
              登录
            </button>
          )}

          {showMenu && (
            <div className="absolute right-0 top-full z-10 mt-1 w-36 rounded-lg border border-gray-200 bg-white py-1 shadow-lg">
              <button
                onClick={async () => {
                  setShowMenu(false)
                  await logout()
                }}
                className="flex w-full items-center gap-2 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
              >
                <LogOut size={16} />
                退出登录
              </button>
            </div>
          )}
        </div>
      </header>

      {showLogin && <LoginModal onClose={() => setShowLogin(false)} />}
    </>
  )
}
