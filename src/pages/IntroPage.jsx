import { useNavigate } from 'react-router-dom'
import PageLayout from '../components/PageLayout'
import Button from '../components/Button'

export default function IntroPage() {
  const navigate = useNavigate()

  const handleNext = () => {
    navigate('/survey')
  }

  return (
    <PageLayout>
      <div className="intro-page">
        <h1 className="title text-center">Nudge</h1>

        <p className="intro-text">
          AI 상담사에게 오늘의 상태를 알려주고,
          <br />
          하루에 한 가지 미션을 수행하며 일상을 되찾아봐요
        </p>

        <p className="warning-text">
          만약 AI 상담사가 위험신호를 감지할 시 보호자 및 주치의에게 연결됩니다.
        </p>

        <p className="final-text">당신은 혼자가 아닙니다.</p>

        <div className="intro-actions">
          <Button onClick={handleNext} variant="primary">다음으로</Button>
        </div>
      </div>
    </PageLayout>
  )
}
