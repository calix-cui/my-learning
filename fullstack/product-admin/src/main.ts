import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'

import App from './App.vue'
import router from './router'

import 'element-plus/dist/index.css'
import './styles/index.css'

const app = createApp(App)

app.use(router)
// 中文语言包保证分页、日期、空态等组件文案为中文
app.use(ElementPlus, { locale: zhCn })

app.mount('#app')
