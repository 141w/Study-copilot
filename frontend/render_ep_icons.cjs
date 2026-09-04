const { createSSRApp, h } = require('vue')
const { renderToString } = require('@vue/server-renderer')
const Icons = require('@element-plus/icons-vue')

const PROJECT_ICONS = ['Reading','Document','Close','EditPen','ChatDotSquare','DocumentChecked','Edit','Delete','Tickets','Upload','CopyDocument','TrendCharts','Plus','VideoPlay','VideoPause','Promotion','HomeFilled','Setting','Download','WarningFilled','DocumentAdd','List','Switch','CircleCheckFilled','CircleCloseFilled','Clock','Loading','ArrowRight','View','Search','User','Sunny','Moon','Fold','ChatLineRound','Top','CircleCheck','Link','DocumentCopy','MagicStick','ArrowLeft']

async function main() {
  const out = {}
  for (const name of PROJECT_ICONS) {
    const Comp = Icons[name]
    if (!Comp) { out[name] = null; continue }
    const app = createSSRApp({ render: () => h(Comp) })
    try {
      const svg = await renderToString(app)
      out[name] = svg
    } catch (e) { out[name] = null }
  }
  const fs = require('fs')
  fs.writeFileSync('/tmp/ep_rendered.json', JSON.stringify(out, null, 2))
  const ok = Object.entries(out).filter(([,v]) => v).length
  console.log(`渲染成功: ${ok}/${PROJECT_ICONS.length}`)
  const fail = Object.entries(out).filter(([,v]) => !v).map(([k]) => k)
  if (fail.length) console.log('失败:', fail.join(','))
}
main()
