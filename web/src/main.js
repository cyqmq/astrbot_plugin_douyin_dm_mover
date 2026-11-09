import { createApp } from 'vue'
import App from './App.vue'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import './style.css'
import { bootstrap } from './composables/bootstrap.js'

createApp(App).mount('#app')
bootstrap()
