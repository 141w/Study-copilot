import type { Directive } from 'vue'

/**
 * 原地 DOM morph（而非整体重设 innerHTML）。
 *
 * 流式每 token 更新正文时，结构相同处复用既有节点：
 * 悬浮层、焦点、hover 状态不会因为父容器 innerHTML 被整树重建而丢失。
 */

function isElement(n: ChildNode | null): n is Element {
  return !!n && n.nodeType === Node.ELEMENT_NODE
}

function sameIdentity(a: Element, b: Element): boolean {
  if (a.tagName !== b.tagName) return false
  // data-index 相同才视为同一角标/同一锚点，避免流式插入时错位复用
  const ai = a.getAttribute('data-index')
  const bi = b.getAttribute('data-index')
  if (ai !== null || bi !== null) return ai === bi
  return true
}

function morphElement(oldEl: Element, newEl: Element): void {
  // 先同步属性：旧的多余属性移除，新的/变化的写入
  for (const attr of Array.from(oldEl.attributes)) {
    if (!newEl.hasAttribute(attr.name)) oldEl.removeAttribute(attr.name)
  }
  for (const attr of Array.from(newEl.attributes)) {
    if (oldEl.getAttribute(attr.name) !== attr.value) {
      oldEl.setAttribute(attr.name, attr.value)
    }
  }
  morphChildren(oldEl, newEl)
}

function morphChildren(parent: Element, source: Node): void {
  const newNodes = Array.from(source.childNodes)
  const oldNodes = Array.from(parent.childNodes)
  const max = Math.max(newNodes.length, oldNodes.length)

  // 倒序处理，删除多余旧节点时不影响前面的索引语义
  for (let i = 0; i < max; i++) {
    const oldN: ChildNode | null = oldNodes[i] ?? null
    const newN: ChildNode | null = newNodes[i] ?? null

    if (newN && !oldN) {
      parent.appendChild(newN.cloneNode(true))
      continue
    }
    if (!newN && oldN) {
      parent.removeChild(oldN)
      continue
    }
    if (!oldN || !newN) continue

    // 文本节点：只更新 nodeValue，不替换节点
    if (oldN.nodeType === Node.TEXT_NODE && newN.nodeType === Node.TEXT_NODE) {
      if (oldN.nodeValue !== newN.nodeValue) oldN.nodeValue = newN.nodeValue
      continue
    }

    // 同构元素：原地 morph
    if (isElement(oldN) && isElement(newN) && sameIdentity(oldN, newN)) {
      morphElement(oldN, newN)
      continue
    }

    // 注释 / 异构节点：整体替换
    parent.replaceChild(newN.cloneNode(true), oldN)
  }
}

/** 将 html 字符串 morph 进 el（原地更新，不整树 innerHTML） */
export function morphHtml(el: Element, html: string): void {
  const tpl = document.createElement('template')
  tpl.innerHTML = html ?? ''
  morphChildren(el, tpl.content)
}

/**
 * 自定义指令 `v-stable-html`：
 * mounted / updated 时对绑定值做原地 morph。
 * （script setup 中以 `vStableHtml` 引入即可使用 `v-stable-html`）
 */
export const stableHtml: Directive<Element, string | undefined> = {
  mounted(el, binding) {
    morphHtml(el, binding.value ?? '')
  },
  updated(el, binding) {
    if (binding.value !== binding.oldValue) {
      morphHtml(el, binding.value ?? '')
    }
  },
}

export default stableHtml
