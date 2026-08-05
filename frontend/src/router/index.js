import { createRouter, createWebHistory } from 'vue-router'
import Library from '../views/Library.vue'
import Reader from '../views/Reader.vue'
import Notes from '../views/Notes.vue'
import ConversationPage from '../views/ConversationPage.vue'
import BookManagement from '../views/BookManagement.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'library',
      component: Library
    },
    {
      path: '/book/:id',
      name: 'reader',
      component: Reader
    },
    {
      path: '/book/:id/notes',
      name: 'notes',
      component: Notes
    },
    {
      path: '/book/:id/manage',
      name: 'book-management',
      component: BookManagement
    },
    {
      path: '/book/:id/conversation/:conversationId',
      name: 'conversation',
      component: ConversationPage
    }
  ]
})

export default router
