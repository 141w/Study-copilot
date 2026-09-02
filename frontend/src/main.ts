import { createApp } from 'vue'
import { createPinia } from 'pinia'
// Element Plus 组件由 unplugin-vue-components 按需自动导入（见 vite.config.js）；
// 指令式 API（ElMessage）在使用处显式 import。不再全量注册，避免 926KB vendor chunk。
import './styles/element-plus-theme.css'
import App from './App.vue'
import router from './router'
import './styles/global.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.mount('#app')
