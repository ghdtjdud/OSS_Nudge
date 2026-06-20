import { useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import PageLayout from '../components/PageLayout'
import Button from '../components/Button'

export default function DashboardPage() {
  const navigate = useNavigate()

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
        <div className="calendar-placeholder">
          <div className="calendar-inner">캘린더 API 연동</div>
        </div>

        <div className="dashboard-main">
          <h1 className="title">Nudge 대시보드</h1>
          <p className="subtitle text-center">자신의 기록을 확인하세요</p>

          <div className="dashboard-actions">
            <Button onClick={handleReturnChat} variant="primary">기존 채팅으로 돌아가기</Button>
            <Button onClick={handleExit} variant="secondary">종료하기</Button>
          </div>
        </div>
      </div>
    </PageLayout>
  )
}
