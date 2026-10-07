/** Mock 通用延迟，模拟网络请求 */
import { config } from '@/config'

export function mockDelay<T>(data: T): Promise<T> {
  return new Promise((resolve) => {
    setTimeout(() => resolve(structuredClone(data)), config.MOCK_DELAY)
  })
}
