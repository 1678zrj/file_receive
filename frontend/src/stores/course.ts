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
  /** 加载课程列表时的错误信息（非「接口缺失」类错误） */
  loadError: string
}

function isMissingApi(e: unknown): boolean {
  const err = e as ApiError
  return err.status === 404 || err.status === 405
}

/**
 * 按角色挑选「可选课程」。
 * `CourseSelector` 与「首次进入默认选中第一门课」共用这一份逻辑，避免两处漂移
 * （出现「下拉里没有这门课、但默认又选中了它」这种情况）。
 */
export function pickCoursesForRole(
  role: UserRole | undefined,
  lists: { teaching: CourseResponse[]; enrolled: CourseResponse[]; allList: CourseResponse[] },
): CourseResponse[] {
  if (role === UserRole.ADMIN) return lists.allList
  if (role === UserRole.TEACHER) return lists.teaching
  return lists.enrolled
}

export const useCourseStore = defineStore('course', {
  state: (): CourseState => ({
    teaching: [],
    enrolled: [],
    allList: [],
    loading: false,
    listApiMissing: false,
    loadError: '',
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
      this.loadError = ''
      this.teaching = []
      this.enrolled = []
      this.allList = []
      /*
       * ⚠️ 这里**不允许把错误抛给调用方**。
       * 之前每个 job 在非 404/405 时会 `throw e`，Promise.all 于是 reject，
       * 而多处调用方是 `await courseStore.refreshMyCourses(...)` 且没有 try/catch，
       * 结果一个课程接口的偶发错误（500/断网）会把 await 之后的所有初始化一起跳过：
       *  - QaView：会话深链定位、?topic= 自动提问全部不执行
       *  - CourseCenterView：enrolledIds 不会被赋值 → 所有课程都显示成「未选」
       * 现在统一改成记录到 loadError，调用方永远不会被打断。
       */
      const record = (e: unknown) => {
        if (isMissingApi(e)) {
          this.listApiMissing = true
          return
        }
        const msg = (e as ApiError)?.message || '课程列表加载失败'
        if (!this.loadError) this.loadError = msg
        console.error('[course] 课程列表加载失败：', e)
      }
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
              .catch(record),
          )
        } else {
          if (role === UserRole.TEACHER) {
            jobs.push(
              courseApi
                .myTeaching()
                .then((list) => {
                  this.teaching = list || []
                })
                .catch(record),
            )
          }
          jobs.push(
            courseApi
              .myEnrolled()
              .then((list) => {
                this.enrolled = list || []
              })
              .catch(record),
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
