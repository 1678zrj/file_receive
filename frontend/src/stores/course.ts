/**
 * 课程数据状态管理
 * 说明：后端的课程列表 / 我的课程等查询接口尚未提供，这里统一收口调用，
 * 并在接口缺失（404/405）时优雅降级为空列表 + 标记位，页面层据此展示占位提示。
 */
import { defineStore } from 'pinia'
import { courseApi, enrollmentApi } from '@/api'
import type { CourseCreate, CourseResponse } from '@/api/types'
import { UserRole } from '@/api/types'
import type { ApiError } from '@/api/http'

interface CourseState {
  /** 我教的课（教师） */
  teaching: CourseResponse[]
  /** 我学的课（学生） */
  enrolled: CourseResponse[]
  /** 所有课程（管理员全局视角） */
  allList: CourseResponse[]
  loading: boolean
  /** 列表接口是否缺失（后端未提供时为 true，页面展示占位提示） */
  listApiMissing: boolean
}

function isMissingApi(e: unknown): boolean {
  const err = e as ApiError
  return err.status === 404 || err.status === 405
}

export const useCourseStore = defineStore('course', {
  state: (): CourseState => ({
    teaching: [],
    enrolled: [],
    allList: [],
    loading: false,
    listApiMissing: false,
  }),
  getters: {
    /** 全部可见课程（我教的 + 我学的 + 全局所有课，按 id 去重） */
    allCourses(): CourseResponse[] {
      const map = new Map<number, CourseResponse>()
      this.teaching.forEach((c) => map.set(c.id, c))
      this.enrolled.forEach((c) => map.set(c.id, c))
      this.allList.forEach((c) => map.set(c.id, c))
      return [...map.values()]
    },
    /** 课程选择器可选项：教师=我教的；管理员=所有；学生=我学的 */
    selectableCourses(): CourseResponse[] {
      return this.allCourses
    },
  },
  actions: {
    /**
     * 刷新课程数据，按角色差异化加载：
     *  - ADMIN：加载全部课程（全局视角）
     *  - TEACHER：加载「我教的」+「我学的」
     *  - STUDENT：加载「我学的」
     */
    async refreshMyCourses(role: UserRole) {
      this.loading = true
      this.listApiMissing = false
      this.teaching = []
      this.enrolled = []
      this.allList = []
      try {
        const jobs: Promise<void>[] = []

        if (role === UserRole.ADMIN) {
          // 管理员：拉取所有课程（全局视角）
          jobs.push(
            courseApi
              .list({ page: 1, size: 200 })
              .then((res) => {
                this.allList = res.items || []
              })
              .catch((e) => {
                if (isMissingApi(e)) this.listApiMissing = true
                else throw e
              }),
          )
        } else {
          if (role === UserRole.TEACHER) {
            jobs.push(
              courseApi
                .myTeaching()
                .then((list) => {
                  this.teaching = list || []
                })
                .catch((e) => {
                  if (isMissingApi(e)) this.listApiMissing = true
                  else throw e
                }),
            )
          }
          jobs.push(
            courseApi
              .myEnrolled()
              .then((list) => {
                this.enrolled = list || []
              })
              .catch((e) => {
                if (isMissingApi(e)) this.listApiMissing = true
                else throw e
              }),
          )
        }
        await Promise.all(jobs)
      } finally {
        this.loading = false
      }
    },
    /** 教师创建课程 */
    async createCourse(data: CourseCreate) {
      const course = await courseApi.create(data)
      this.teaching.unshift(course)
      return course
    },
    /** 学生选课 */
    async enroll(courseId: number) {
      return enrollmentApi.enroll({ course_id: courseId })
    },
  },
})
