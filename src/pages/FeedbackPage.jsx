import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import PageLayout from '../components/PageLayout'
import Button from '../components/Button'

export default function FeedbackPage() {
  const navigate = useNavigate()
  const missionResult = useMemo(() => {
    const stored = localStorage.getItem('missionResult')
    return stored === 'success' ? 'success' : 'fail'
  }, [])

  const handleClick = () => {
    if (missionResult === 'success') {
      navigate('/dashboard')
    } else {
      navigate('/mission')
    }
  }

  const title = missionResult === 'success' ? '오늘의 Nudge 성공🎉' : '미션 확인이 어려워요'
  const subtitle = missionResult === 'success'
    ? '축하합니다.'
    : '다시한번 미션을 수행해주세요!'
  const body = missionResult === 'success'
    ? '오늘의 Nudge로 천천히 한걸음씩 나아가요!'
    : '미션을 완료하고 다시 시도해보세요.'
  const buttonText = missionResult === 'success' ? '대시보드로 이동' : '미션카드로 이동'

  return (
    <PageLayout>
      <div className="container">
        <h1 className="title">{title}</h1>
        <p className="subtitle text-center">{subtitle}</p>
        <p className="subtitle text-center">{body}</p>
        <div className="mt-lg text-center">
          <Button onClick={handleClick}>{buttonText}</Button>
        </div>
      </div>
    </PageLayout>
  )
}
