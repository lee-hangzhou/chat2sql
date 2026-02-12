import { useEffect, useMemo, useRef, type ComponentPropsWithoutRef } from 'react'
import Markdown from 'react-markdown'
import hljs from 'highlight.js/lib/core'
import sql from 'highlight.js/lib/languages/sql'
import 'highlight.js/styles/github.css'
import { Bot, Copy, Check, User } from 'lucide-react'
import { useState, useCallback } from 'react'
import type { Message } from '../types'
import ResultTable from './ResultTable'

hljs.registerLanguage('sql', sql)

function CodeBlock({ className, children, ...rest }: ComponentPropsWithoutRef<'code'>) {
  const [copied, setCopied] = useState(false)
  const match = /language-(\w+)/.exec(className || '')
  const lang = match ? match[1] : ''
  const code = String(children).replace(/\n$/, '')

  const highlighted = useMemo(() => {
    if (!lang) return null
    try {
      return hljs.highlight(code, { language: lang }).value
    } catch {
      return null
    }
  }, [code, lang])

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }, [code])

  if (!match) {
    return <code className="inline-code" {...rest}>{children}</code>
  }

  return (
    <div className="code-block">
      <div className="code-block-header">
        <span>{lang}</span>
        <button onClick={handleCopy} className="code-copy-btn">
          {copied ? <Check size={14} /> : <Copy size={14} />}
          {copied ? '已复制' : '复制'}
        </button>
      </div>
      <pre>
        {highlighted ? (
          <code dangerouslySetInnerHTML={{ __html: highlighted }} />
        ) : (
          <code>{code}</code>
        )}
      </pre>
    </div>
  )
}

interface Props {
  messages: Message[]
  currentNode: string | null
  sending: boolean
}

export default function MessageList({ messages, currentNode, sending }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, currentNode])

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6">
      <div className="mx-auto max-w-3xl space-y-6">
        {messages.map((msg, i) =>
          msg.role === 'user' ? (
            <div key={i} className="flex justify-end gap-3">
              <div className="max-w-[75%] rounded-2xl bg-blue-600 px-4 py-3 text-sm leading-relaxed text-white whitespace-pre-wrap">
                {msg.content}
              </div>
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-600 text-white">
                <User size={18} />
              </div>
            </div>
          ) : (
            <div key={i}>
              <div className="flex gap-3">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-emerald-600 text-white">
                  <Bot size={18} />
                </div>
                <div className="min-w-0 flex-1 text-sm leading-relaxed text-gray-800 chat-markdown">
                  <Markdown components={{ code: CodeBlock }}>{msg.content}</Markdown>
                </div>
              </div>
              {msg.executeResult && msg.executeResult.length > 0 && (
                <div className="ml-11 mt-3">
                  <ResultTable data={msg.executeResult} />
                </div>
              )}
            </div>
          )
        )}

        {/* 执行进度指示 */}
        {sending && currentNode && (
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-emerald-600 text-white">
              <Bot size={18} />
            </div>
            <div className="flex items-center gap-2 rounded-2xl border border-gray-100 bg-white px-4 py-3 text-sm text-gray-500 shadow-sm">
              <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-emerald-500" />
              {currentNode}...
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  )
}
