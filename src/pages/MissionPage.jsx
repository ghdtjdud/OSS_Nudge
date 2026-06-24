import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import PageLayout from '../components/PageLayout'
import { authFetch } from '../api'

const DEFAULT_MISSION = {
card_title: '물 한잔 마시기',
card_subtitle: '지금 자리에서 일어나서\n물 한잔을 마시세요',
mission_code: 'drink_water',
}

function parseRecommendedMission() {
const stored = localStorage.getItem('recommendedMission')

if (!stored) {
return DEFAULT_MISSION
}

try {
const parsed = JSON.parse(stored)

return {
  ...DEFAULT_MISSION,
  ...parsed,
}

} catch (error) {
return DEFAULT_MISSION
}
}

export default function MissionPage() {
const navigate = useNavigate()

const [mission, setMission] = useState(DEFAULT_MISSION)
const [statusText, setStatusText] = useState('잠시후 카메라가 활성화 될 예정입니다')
const [errorMessage, setErrorMessage] = useState('')

useEffect(() => {
const currentMission = parseRecommendedMission()
setMission(currentMission)

const startMission = async () => {
  const userMissionId =
    currentMission.user_mission_id ||
    currentMission.userMissionId ||
    currentMission.id

  if (!userMissionId) {
    console.error('user_mission_id가 없습니다:', currentMission)
    setErrorMessage('미션 ID를 찾을 수 없습니다.')
    return
  }

  try {
    setStatusText('미션 인증을 준비하고 있어요...')

    const response = await authFetch(`/api/v1/missions/${userMissionId}/start`, {
      method: 'PATCH',
    })

    console.log('미션 시작 응답:', response)

    localStorage.setItem('userMissionId', userMissionId)
    localStorage.setItem(
      'selectedMission',
      currentMission.mission_code ||
        currentMission.missionCode ||
        currentMission.mission_type ||
        currentMission.missionType ||
        'drink_water'
    )

    if (currentMission.verification_code) {
      localStorage.setItem('verificationCode', currentMission.verification_code)
    }

    if (currentMission.instance_key) {
      localStorage.setItem('instanceKey', currentMission.instance_key)
    }

    navigate('/verify')
  } catch (error) {
    console.error('미션 시작 실패:', error)
    setErrorMessage(error.message || '미션 시작에 실패했습니다.')
    setStatusText('미션 인증 화면으로 이동하지 못했습니다.')
  }
}

const timer = setTimeout(() => {
  startMission()
}, 5000)

return () => clearTimeout(timer)

}, [navigate])

const title = mission.card_title || mission.title || '오늘의 미션'

const subtitle =
mission.card_subtitle ||
mission.description ||
'지금 자리에서 일어나서\n작은 행동을 시작해보세요'

return (
<PageLayout>
<div className="mission-page">
<div className="mission-card">
<div className="mission-text">
<div>{title}</div>

        {subtitle.split('\n').map((line, i) => (
          <div key={i}>{line}</div>
        ))}
      </div>

      <div className="mission-note">{statusText}</div>

      {errorMessage && (
        <div className="mission-note" style={{ marginTop: 12 }}>
          오류: {errorMessage}
        </div>
      )}
    </div>
  </div>
</PageLayout>

)
}