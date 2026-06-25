import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import PageLayout from '../components/PageLayout'
import Button from '../components/Button'
import { authFetch } from '../api'

const stickerImageMap = {
STICKER_1: 'public/stickers/sticker-1-small-sprout.png',
STICKER_2: 'public/stickers/sticker-2-growing-sprout.png',
STICKER_3: 'public/stickers/sticker-3-blooming-flower.png',
STICKER_4: 'public/stickers/sticker-4-flower-bouquet.png',
}

const USE_MOCK_STICKERS = true
const MOCK_STICKER_COUNT = 12

function createSeededRandom(seed) {
  let value = seed >>> 0

  return () => {
    value = (
      value * 1664525 +
      1013904223
    ) >>> 0

    return value / 4294967296
  }
}

function getMockStickers(year, month) {
  const today = new Date()

  const currentYear = today.getFullYear()
  const currentMonth = today.getMonth() + 1
  const currentDay = today.getDate()

  const selectedMonthValue = year * 100 + month
  const currentMonthValue = currentYear * 100 + currentMonth

  // 미래 월에는 가짜 스티커 없음
  if (selectedMonthValue > currentMonthValue) {
    return []
  }

  const lastDayOfMonth = new Date(
    year,
    month,
    0
  ).getDate()

  // 현재 월은 어제까지만 가짜 데이터 생성
  // 오늘 데이터는 실제 백엔드 데이터를 사용
  const maxAvailableDay =
    selectedMonthValue === currentMonthValue
      ? currentDay - 1
      : lastDayOfMonth

  if (maxAvailableDay <= 0) {
    return []
  }

  const random = createSeededRandom(
    year * 100 + month
  )

  const availableDays = Array.from(
    { length: maxAvailableDay },
    (_, index) => index + 1
  )

  const selectedDays = []

  const stickerCount = Math.min(
    MOCK_STICKER_COUNT,
    availableDays.length
  )

  for (
    let index = 0;
    index < stickerCount;
    index += 1
  ) {
    const randomIndex = Math.floor(
      random() * availableDays.length
    )

    const [selectedDay] = availableDays.splice(
      randomIndex,
      1
    )

    selectedDays.push(selectedDay)
  }

  return selectedDays
    .sort((a, b) => a - b)
    .map((day) => {
      const completedCount =
        Math.floor(random() * 4) + 1

      return {
        date: toDateString(
          year,
          month,
          day
        ),
        completed_count: completedCount,
        sticker_type: `STICKER_${completedCount}`,
      }
    })
}

const WEEK_DAYS = ['일', '월', '화', '수', '목', '금', '토']

function padNumber(value) {
return String(value).padStart(2, '0')
}

function toDateString(year, month, day) {
return `${year}-${padNumber(month)}-${padNumber(day)}`
}

function getCalendarCells(year, month) {
const firstDate = new Date(year, month - 1, 1)
const lastDate = new Date(year, month, 0)

const firstDay = firstDate.getDay()
const lastDay = lastDate.getDate()

const cells = []

for (let i = 0; i < firstDay; i += 1) {
cells.push(null)
}

for (let day = 1; day <= lastDay; day += 1) {
cells.push({
day,
date: toDateString(year, month, day),
})
}

while (cells.length % 7 !== 0) {
cells.push(null)
}

return cells
}

export default function DashboardPage() {
const navigate = useNavigate()

const today = new Date()

const [year, setYear] = useState(today.getFullYear())
const [month, setMonth] = useState(today.getMonth() + 1)
const [stickers, setStickers] = useState([])
const [isLoading, setIsLoading] = useState(false)
const [errorMessage, setErrorMessage] = useState('')

const calendarCells = useMemo(() => {
return getCalendarCells(year, month)
}, [year, month])

const stickerByDate = useMemo(() => {
return stickers.reduce((acc, sticker) => {
acc[sticker.date] = sticker
return acc
}, {})
}, [stickers])

const fetchCalendar = useCallback(async () => {
  const mockStickers = USE_MOCK_STICKERS
    ? getMockStickers(year, month)
    : []

  try {
    setIsLoading(true)
    setErrorMessage('')

    // 실제 백엔드 데이터는 항상 조회
    const data = await authFetch(
      `/api/v1/dashboard/calendar?year=${year}&month=${month}`
    )

    const realStickers = data.stickers || []

    if (!USE_MOCK_STICKERS) {
      setStickers(realStickers)
      return
    }

    // 날짜 기준으로 가짜 데이터와 실제 데이터 병합
    const mergedStickerMap = new Map()

    // 가짜 과거 기록 먼저 저장
    mockStickers.forEach((sticker) => {
      mergedStickerMap.set(
        sticker.date,
        sticker
      )
    })

    // 실제 데이터가 같은 날짜에 있으면 실제 데이터로 덮어쓰기
    realStickers.forEach((sticker) => {
      mergedStickerMap.set(
        sticker.date,
        sticker
      )
    })

    const mergedStickers = Array.from(
      mergedStickerMap.values()
    ).sort((a, b) => {
      return a.date.localeCompare(b.date)
    })

    console.log('가짜 과거 스티커:', mockStickers)
    console.log('실제 스티커:', realStickers)
    console.log('최종 병합 스티커:', mergedStickers)

    setStickers(mergedStickers)
  } catch (error) {
    console.error(
      '대시보드 캘린더 조회 실패:',
      error
    )

    // 실제 API가 실패해도 과거 가짜 데이터는 표시
    if (USE_MOCK_STICKERS) {
      setStickers(mockStickers)

      setErrorMessage(
        '오늘의 실제 미션 기록을 불러오지 못했습니다.'
      )
    } else {
      setStickers([])

      setErrorMessage(
        error.message ||
          '캘린더 기록을 불러오지 못했습니다.'
      )
    }
  } finally {
    setIsLoading(false)
  }
}, [year, month])

useEffect(() => {
fetchCalendar()
}, [fetchCalendar])

const handlePrevMonth = () => {
if (month === 1) {
setYear((prev) => prev - 1)
setMonth(12)
return
}

setMonth((prev) => prev - 1)

}

const handleNextMonth = () => {
if (month === 12) {
setYear((prev) => prev + 1)
setMonth(1)
return
}

setMonth((prev) => prev + 1)

}

const handleReturnChat = useCallback(() => {
navigate('/chat')
}, [navigate])

const handleExit = useCallback(() => {
localStorage.removeItem('todayChat')
localStorage.removeItem('selectedMission')
localStorage.removeItem('missionResult')
navigate('/')
}, [navigate])

return (
<PageLayout>
<div className="dashboard-page container">
<div className="dashboard-main">
<h1 className="title">Nudge 대시보드</h1>
<p className="subtitle text-center">자신의 기록을 확인하세요</p>

      <div className="dashboard-calendar-card">
        <div className="calendar-header">
          <Button onClick={handlePrevMonth} variant="secondary">
            이전
          </Button>

          <h2 className="calendar-title">
            {year}년 {month}월
          </h2>

          <Button onClick={handleNextMonth} variant="secondary">
            다음
          </Button>
        </div>

        {errorMessage && (
          <p className="error-message">{errorMessage}</p>
        )}

        {isLoading ? (
          <p className="dashboard-loading">캘린더 기록을 불러오는 중입니다...</p>
        ) : (
          <div className="calendar-grid">
            {WEEK_DAYS.map((day) => (
              <div key={day} className="calendar-weekday">
                {day}
              </div>
            ))}

            {calendarCells.map((cell, index) => {
              if (!cell) {
                return (
                  <div
                    key={`empty-${index}`}
                    className="calendar-cell calendar-cell-empty"
                  />
                )
              }

              const sticker = stickerByDate[cell.date]
              const stickerImage = sticker
                ? stickerImageMap[sticker.sticker_type]
                : null

              return (
                <div key={cell.date} className="calendar-cell">
                  <span className="calendar-date-number">{cell.day}</span>

                  {stickerImage && (
                    <img
                      src={stickerImage}
                      alt={`${sticker.completed_count}개 미션 완료`}
                      className="calendar-sticker"
                    />
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      <div className="dashboard-actions">
        <Button onClick={handleReturnChat} variant="primary">
          기존 채팅으로 돌아가기
        </Button>
        <Button onClick={handleExit} variant="secondary">
          종료하기
        </Button>
      </div>
    </div>
  </div>
</PageLayout>

)
}