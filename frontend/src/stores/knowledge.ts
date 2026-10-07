/**
 * 知识库状态管理（跨「知识库管理」和「AI 问答」两个独立页面共享）
 *  - selectedCourseId：两页通用的课程选择器共享选中课程，跳转时保持
 */
import { defineStore } from 'pinia'

interface KnowledgeState {
  /** 当前选中的课程 id（null 表示未选择） */
  selectedCourseId: number | null
}

export const useKnowledgeStore = defineStore('knowledge', {
  state: (): KnowledgeState => ({
    selectedCourseId: null,
  }),
  actions: {
    setCourseId(id: number | null) {
      this.selectedCourseId = id
    },
  },
})
