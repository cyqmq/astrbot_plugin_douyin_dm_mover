import { createApp } from 'vue'
import App from './App.vue'
import './style.css'
import { bootstrap } from './composables/bootstrap.js'

createApp(App).mount('#app')
bootstrap()
