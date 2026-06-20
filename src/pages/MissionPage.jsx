import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import PageLayout from '../components/PageLayout'

const MISSION_TEXTS = {
  drink_water: '지금 자리에서 일어나서\n물 한잔을 마시세요',
  brush_teeth: '세면대로 가서\n양치를 해보세요',
  take_medicine: '정해진 약을 확인하고\n복용해보세요',
  eat_meal: '간단한 식사라도\n챙겨보세요'
}

export default function MissionPage() {
  const navigate = useNavigate()
  const [missionKey, setMissionKey] = useState('drink_water')
  const [missionText, setMissionText] = useState(MISSION_TEXTS.drink_water)

  useEffect(() => {
    const stored = localStorage.getItem('recommendedMission') || 'drink_water'
    const key = stored || 'drink_water'
    setMissionKey(key)
    setMissionText(MISSION_TEXTS[key] ?? MISSION_TEXTS.drink_water)

    const timer = setTimeout(() => {
      localStorage.setItem('selectedMission', key)
      navigate('/verify')
    }, 5000)

    return () => clearTimeout(timer)
  }, [navigate])

  return (
    <PageLayout>
      <div className="mission-page">
        <div className="mission-card">
          <div className="mission-text">
            {missionText.split('\n').map((line, i) => (
              <div key={i}>{line}</div>
            ))}
          </div>
          <div className="mission-note">잠시후 카메라가 활성화 될 예정입니다</div>
        </div>
      </div>
    </PageLayout>
  )
}
