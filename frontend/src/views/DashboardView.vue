<template>
  <div class="page-container">
    <!-- 欢迎横幅（沉稳深蓝） -->
    <div class="welcome-banner fade-in-up">
      <div class="wb-text">
        <h2 class="wb-title">{{ greeting }}，{{ auth.user?.real_name }}</h2>
        <p class="wb-sub">{{ today }} · 欢迎回到云课堂{{ roleScopeText }}工作台</p>
      </div>
      <div class="wb-right">
        <el-button class="wb-btn" @click="$router.push('/my-courses')">
          {{ isTeachingSide ? '我的课程' : '进入学习' }}
          <el-icon class="el-icon--right"><ArrowRight /></el-icon>
        </el-button>
      </div>
    </div>

    <!-- 统计概览 -->
    <div class="stat-grid">
      <div v-for="(s, i) in statCards" :key="i" class="stat-card cc-card fade-in-up" :style="{ animationDelay: `${i * 0.04}s` }">
        <div class="stat-icon" :style="{ background: s.bg, color: s.color }">
          <el-icon :size="22"><component :is="s.icon" /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ s.value }}</div>
          <div class="stat-label">{{ s.label }}</div>
        </div>
      </div>
    </div>

    <!-- 数据看板（图表） -->
    <div class="chart-grid">
      <div class="cc-card chart-card fade-in-up">
        <div class="panel-head">
          <h3 class="panel-title">作业提交情况</h3>
        </div>
        <div ref="rateChartRef" class="chart-box"></div>
      </div>
      <div class="cc-card chart-card fade-in-up">
        <div class="panel-head">
          <h3 class="panel-title">成绩分布</h3>
        </div>
        <div ref="distChartRef" class="chart-box"></div>
      </div>
    </div>

    <div class="two-col">
      <!-- 左：我的课程 + 待办 -->
      <div class="left-col">
        <div class="cc-card panel fade-in-up">
          <div class="panel-head">
            <h3 class="panel-title">{{ isTeachingSide ? (auth.isAdmin ? '全部课程' : '我教的课') : '我的课程' }}</h3>
            <el-link type="primary" :underline="false" @click="$router.push('/my-courses')">查看全部</el-link>
          </div>
          <div v-loading="courseStore.loading" class="panel-body">
            <el-empty v-if="!courseStore.loading && listCourses.length === 0" description="暂无课程" :image-size="70">
              <el-button type="primary" class="btn-primary" @click="$router.push('/courses')">前往课程广场</el-button>
            </el-empty>
            <div v-else class="course-list">
              <div
                v-for="c in listCourses"
                :key="c.id"
                class="course-row"
                @click="$router.push({ name: 'course-detail', params: { id: c.id } })"
              >
                <div class="course-cover-mini" :style="{ background: courseCover(c.name) }">
                  <span>{{ c.course_code || '—' }}</span>
                </div>
                <div class="course-info">
                  <div class="ci-name">{{ c.name }}</div>
                  <div class="ci-sub">{{ c.overview || '暂无简介' }}</div>
                </div>
                <el-icon class="ci-arrow" :size="15"><ArrowRight /></el-icon>
              </div>
            </div>
          </div>
        </div>

        <!-- 待办：即将截止的作业 -->
        <div class="cc-card panel fade-in-up">
          <div class="panel-head">
            <h3 class="panel-title">待办 · 即将截止的作业</h3>
          </div>
          <div v-loading="todoLoading" class="panel-body">
            <el-empty v-if="!todoLoading && upcoming.length === 0" description="暂无待提交作业" :image-size="70" />
            <div v-else class="todo-list">
              <div
                v-for="a in upcoming"
                :key="a.id"
                class="todo-item"
                @click="$router.push({ name: 'course-detail', params: { id: a.course_id } })"
              >
                <div class="todo-badge" :class="deadlineInfo(a.deadline).urgent ? 'badge-urgent' : 'badge-normal'">
                  {{ deadlineInfo(a.deadline).text }}
                </div>
                <div class="todo-main">
                  <div class="todo-title">{{ a.title }}</div>
                  <div class="todo-meta">{{ formatDateTime(a.deadline) }} 截止</div>
                </div>
                <el-icon class="ci-arrow" :size="14"><ArrowRight /></el-icon>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右：快捷入口 + 关于 -->
      <div class="right-col">
        <div class="cc-card panel fade-in-up">
          <div class="panel-head">
            <h3 class="panel-title">快捷入口</h3>
          </div>
          <div class="quick-list">
            <div v-for="(q, i) in quickEntries" :key="i" class="quick-item" @click="$router.push(q.to)">
              <el-icon :size="18" :color="q.color"><component :is="q.icon" /></el-icon>
              <span class="qi-text">{{ q.title }}</span>
              <el-icon class="ci-arrow" :size="14"><ArrowRight /></el-icon>
            </div>
          </div>
        </div>
        <div class="cc-card panel fade-in-up">
          <div class="panel-head">
            <h3 class="panel-title">关于平台</h3>
          </div>
          <div class="about-text">
            云课堂提供课程管理、资源上传、作业发布与提交、成绩管理，以及基于 RAG 的课程知识库智能问答能力。
            <span v-if="config.USE_MOCK" class="mock-tip">当前为演示数据预览模式。</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import dayjs from 'dayjs'
import * as echarts from 'echarts/core'
import { PieChart, BarChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { useAuthStore } from '@/stores/auth'
import { useCourseStore } from '@/stores/course'
import { statsApi, assignmentApi } from '@/api'
import type { Assignment, StatsOverview } from '@/api/types'
import { courseCover, deadlineInfo, formatDateTime } from '@/utils/format'
import { config } from '@/config'

echarts.use([PieChart, BarChart, TooltipComponent, LegendComponent, GridComponent, CanvasRenderer])

const auth = useAuthStore()
const courseStore = useCourseStore()

const rateChartRef = ref<HTMLDivElement>()
const distChartRef = ref<HTMLDivElement>()
const stats = ref<StatsOverview | null>(null)
const upcoming = ref<Assignment[]>([])
const todoLoading = ref(false)
let rateChart: echarts.ECharts | null = null
let distChart: echarts.ECharts | null = null

onMounted(async () => {
  if (auth.user) courseStore.refreshMyCourses(auth.user.role)
  loadStats()
  loadUpcoming()
})

onBeforeUnmount(() => {
  rateChart?.dispose()
  distChart?.dispose()
})

const greeting = computed(() => {
  const h = dayjs().hour()
  if (h < 6) return '夜深了'
  if (h < 12) return '早上好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
})
const week = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
const today = dayjs().format('YYYY年MM月DD日') + ' ' + week[dayjs().day()]

/** 教学侧（教师/管理员）还是学习侧（学生） */
const isTeachingSide = computed(() => auth.isTeacherOrAdmin)
const roleScopeText = computed(() => (auth.isAdmin ? '管理' : auth.isTeacher ? '教学' : '学习'))

const listCourses = computed(() => courseStore.allCourses.slice(0, 5))

const statCards = computed(() => [
  {
    icon: 'Notebook',
    label: auth.isAdmin ? '全部课程' : auth.isTeacher ? '我教的课程' : '在学课程',
    value: stats.value?.course_count ?? courseStore.allCourses.length,
    bg: '#e8f1fd',
    color: '#2d6cdf',
  },
  {
    icon: 'User',
    label: isTeachingSide.value ? '学生总数' : '全部课程',
    value: stats.value?.student_count ?? courseStore.allCourses.length,
    bg: '#e7f6ef',
    color: '#1a7a50',
  },
  {
    icon: 'EditPen',
    label: '作业数',
    value: stats.value?.assignment_count ?? '—',
    bg: '#fdf3e3',
    color: '#b7760a',
  },
  {
    icon: 'DataAnalysis',
    label: '作业提交率',
    value: stats.value ? `${stats.value.submission_rate}%` : '—',
    bg: '#f0edfb',
    color: '#7a5cc4',
  },
])

const quickEntries = computed(() => {
  const list = [
    { icon: 'Search', title: '课程广场', to: '/courses', color: '#2d6cdf' },
    { icon: 'Notebook', title: '我的课程', to: '/my-courses', color: '#1a7a50' },
    { icon: 'Collection', title: '知识库管理', to: '/knowledge', color: '#b7760a' },
    { icon: 'ChatDotRound', title: 'AI 问答', to: '/qa', color: '#7a5cc4' },
  ]
  if (auth.isTeacherOrAdmin) {
    list.push({ icon: 'Plus', title: '创建课程', to: '/my-courses?create=1', color: '#31859b' })
  }
  return list
})

async function loadStats() {
  try {
    stats.value = await statsApi.overview()
    await nextTickRender()
  } catch {
    /* mock 或接口缺失时静默 */
  }
}

async function loadUpcoming() {
  todoLoading.value = true
  try {
    upcoming.value = await assignmentApi.upcoming()
  } catch {
    upcoming.value = []
  } finally {
    todoLoading.value = false
  }
}

async function nextTickRender() {
  await new Promise((r) => setTimeout(r, 0))
  renderCharts()
}

function renderCharts() {
  if (!stats.value) return
  // 提交率环形图
  if (rateChartRef.value) {
    rateChart = rateChart || echarts.init(rateChartRef.value)
    const rate = stats.value.submission_rate
    rateChart.setOption({
      tooltip: { trigger: 'item', formatter: '{b}: {c}%' },
      series: [
        {
          type: 'pie',
          radius: ['58%', '78%'],
          avoidLabelOverlap: false,
          label: { show: true, position: 'center', formatter: `{value|${rate}%}\n{label|提交率}`, rich: { value: { fontSize: 26, fontWeight: 700, color: '#2d6cdf' }, label: { fontSize: 12, color: '#8492a6' } } },
          data: [
            { value: rate, name: '已提交', itemStyle: { color: '#2d6cdf' } },
            { value: 100 - rate, name: '未提交', itemStyle: { color: '#e3e8ee' } },
          ],
        },
      ],
    })
  }
  // 成绩分布柱状图
  if (distChartRef.value) {
    distChart = distChart || echarts.init(distChartRef.value)
    const dist = stats.value.score_distribution
    distChart.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: 40, right: 16, top: 20, bottom: 28 },
      xAxis: { type: 'category', data: dist.map((d) => d.range), axisLine: { lineStyle: { color: '#e3e8ee' } }, axisLabel: { color: '#8492a6' } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: '#f0f2f7' } }, axisLabel: { color: '#8492a6' } },
      series: [
        {
          type: 'bar',
          data: dist.map((d) => d.count),
          barWidth: '46%',
          itemStyle: { color: '#2d6cdf', borderRadius: [4, 4, 0, 0] },
        },
      ],
    })
  }
}
</script>

<style scoped>
.welcome-banner {
  background: linear-gradient(120deg, #1a3a5c 0%, #1f2d3d 100%);
  border-radius: var(--radius-md);
  padding: 24px 28px;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.wb-title { margin: 0; font-size: 20px; font-weight: 600; }
.wb-sub { margin: 6px 0 0; opacity: 0.75; font-size: 13px; }
.wb-btn { background: rgba(255, 255, 255, 0.14); border: 1px solid rgba(255, 255, 255, 0.25); color: #fff; }
.wb-btn:hover { background: rgba(255, 255, 255, 0.22); color: #fff; }

.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}
.stat-card { display: flex; align-items: center; gap: 14px; padding: 18px; }
.stat-icon { width: 46px; height: 46px; border-radius: 6px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.stat-value { font-size: 24px; font-weight: 700; line-height: 1.1; }
.stat-label { font-size: 12.5px; color: var(--text-secondary); margin-top: 3px; }

.chart-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}
@media (max-width: 900px) {
  .chart-grid { grid-template-columns: 1fr; }
}
.chart-card { overflow: hidden; }
.chart-box { height: 240px; }

.two-col {
  display: grid;
  grid-template-columns: 1.5fr 1fr;
  gap: 16px;
  align-items: start;
}
@media (max-width: 900px) {
  .two-col { grid-template-columns: 1fr; }
}
.left-col, .right-col { display: flex; flex-direction: column; gap: 16px; }
.panel { overflow: hidden; }
.panel-head { display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid var(--border); }
.panel-title { margin: 0; font-size: 15px; font-weight: 600; }
.panel-body { padding: 8px; }

.course-list { display: flex; flex-direction: column; }
.course-row { display: flex; align-items: center; gap: 12px; padding: 10px 12px; border-radius: 4px; cursor: pointer; }
.course-row:hover { background: var(--bg-soft); }
.course-cover-mini { width: 52px; height: 38px; border-radius: 4px; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 11px; font-weight: 600; flex-shrink: 0; }
.course-info { flex: 1; min-width: 0; }
.ci-name { font-weight: 600; font-size: 14px; }
.ci-sub { font-size: 12px; color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ci-arrow { color: var(--text-faint); flex-shrink: 0; }

.todo-list { display: flex; flex-direction: column; }
.todo-item { display: flex; align-items: center; gap: 12px; padding: 11px 12px; border-radius: 4px; cursor: pointer; }
.todo-item:hover { background: var(--bg-soft); }
.todo-badge { font-size: 11.5px; font-weight: 600; padding: 2px 9px; border-radius: 3px; white-space: nowrap; flex-shrink: 0; }
.badge-urgent { color: #ea580c; background: #fdf3e3; }
.badge-normal { color: #2d6cdf; background: #e8f1fd; }
.todo-main { flex: 1; min-width: 0; }
.todo-title { font-weight: 600; font-size: 13.5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.todo-meta { font-size: 12px; color: var(--text-secondary); margin-top: 2px; }

.quick-list { padding: 6px; }
.quick-item { display: flex; align-items: center; gap: 12px; padding: 12px 14px; border-radius: 4px; cursor: pointer; font-size: 14px; }
.quick-item:hover { background: var(--bg-soft); }
.qi-text { flex: 1; }
.about-text { padding: 14px 18px; font-size: 13px; color: var(--text-regular); line-height: 1.8; }
.mock-tip { color: var(--orange); }
</style>
