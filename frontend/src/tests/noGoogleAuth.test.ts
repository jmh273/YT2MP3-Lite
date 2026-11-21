// 守門：前端原始碼不呼叫任何需要 Google 授權的後端路由，也不引用已移除的 store。
// 掃描先確認看到已知錨點（/url-preview、/download），再判斷不該存在的東西；
// 並用好、壞兩段輸入當對照組，證明判準會給不同答案。
// 射程：只看字面字串；用變數拼出來的路徑看不到（目前程式裡沒有這種寫法）。
import { describe, it, expect } from 'vitest'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'

const SRC = join(process.cwd(), 'src')

const FORBIDDEN = [
  /['"`]\/(auth|subscriptions|channels|drive|quota|latest-videos|trending-videos|discovery|search-channels)\b/,
  /@\/stores\/(auth|quota|watchlist|discovery|driveUpload)\b/,
  /LoginView|WatchlistPanel|DriveUploadPanel|ReconcileWizard/,
]

function stripComments(src: string): string {
  return src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/[^\n]*/g, '$1').replace(/<!--[\s\S]*?-->/g, '')
}

function hits(src: string): string[] {
  const clean = stripComments(src)
  return FORBIDDEN.flatMap((re) => {
    const m = clean.match(re)
    return m ? [m[0]] : []
  })
}

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = join(dir, name)
    if (statSync(full).isDirectory()) return name === 'tests' ? [] : sourceFiles(full)
    return /\.(ts|vue)$/.test(name) ? [full] : []
  })
}

describe('前端不依賴 Google 授權', () => {
  it('對照組：判準對壞輸入有反應、對好輸入沒有', () => {
    expect(hits("await apiGet('/subscriptions')")).not.toEqual([])
    expect(hits("import { useAuthStore } from '@/stores/auth'")).not.toEqual([])
    expect(hits("// 以前會呼叫 apiGet('/auth/status')\nawait apiGet('/url-preview')")).toEqual([])
  })

  it('src/ 底下（測試以外）沒有任何違規', () => {
    const files = sourceFiles(SRC)
    const all = files.map((f) => readFileSync(f, 'utf-8')).join('\n')
    // 錨點：真的掃到了來源與下載功能
    expect(files.length).toBeGreaterThan(10)
    expect(all).toContain('/url-preview')
    expect(all).toContain("'/download'")

    const violations = files.flatMap((f) =>
      hits(readFileSync(f, 'utf-8')).map((h) => `${relative(SRC, f)}: ${h}`),
    )
    expect(violations).toEqual([])
  })
})
