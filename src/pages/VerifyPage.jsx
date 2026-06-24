import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import PageLayout from '../components/PageLayout'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const VERIFY_TIMEOUT_SECONDS = 15

const MISSION_LABELS = {
DRINK_WATER: '물 마시기',
BRUSH_TEETH: '양치하기',
TAKE_MEDICATION: '약 복용',
EAT_MEAL: '식사하기',
drink_water: '물 마시기',
brush_teeth: '양치하기',
take_medicine: '약 복용',
eat_meal: '식사하기',
}

const MISSION_TARGETS = {
DRINK_WATER: 'cup',
BRUSH_TEETH: 'toothbrush',
TAKE_MEDICATION: 'pill',
EAT_MEAL: 'bowl',
drink_water: 'cup',
brush_teeth: 'toothbrush',
take_medicine: 'pill',
eat_meal: 'bowl',
}

function getErrorMessage(errorBody, fallbackMessage) {
if (!errorBody) return fallbackMessage

if (typeof errorBody.detail === 'string') {
return errorBody.detail
}

if (Array.isArray(errorBody.detail)) {
return JSON.stringify(errorBody.detail, null, 2)
}

if (typeof errorBody.message === 'string') {
return errorBody.message
}

return fallbackMessage
}

function getMissionCode() {
const selectedMission = localStorage.getItem('selectedMission')
const recommendedMissionRaw = localStorage.getItem('recommendedMission')

if (selectedMission) {
return selectedMission
}

if (recommendedMissionRaw) {
try {
const recommendedMission = JSON.parse(recommendedMissionRaw)

  return (
    recommendedMission.mission_code ||
    recommendedMission.missionCode ||
    recommendedMission.mission_type ||
    recommendedMission.missionType ||
    'DRINK_WATER'
  )
} catch (error) {
  return 'DRINK_WATER'
}

}

return 'DRINK_WATER'
}

export default function VerifyPage() {
const navigate = useNavigate()

const videoRef = useRef(null)
const canvasRef = useRef(null)
const streamRef = useRef(null)
const timeoutRef = useRef(null)
const stoppedRef = useRef(false)
const errorCountRef = useRef(0)
const startedAtRef = useRef(null)

const [missionCode, setMissionCode] = useState('DRINK_WATER')
const [progress, setProgress] = useState(0)
const [detected, setDetected] = useState(false)
const [remainingTime, setRemainingTime] = useState(VERIFY_TIMEOUT_SECONDS)
const [statusMessage, setStatusMessage] = useState('웹캠을 준비하고 있어요.')
const [errorMessage, setErrorMessage] = useState('')
const [cameraReady, setCameraReady] = useState(false)

useEffect(() => {
const currentMissionCode = getMissionCode()
setMissionCode(currentMissionCode)
}, [])

useEffect(() => {
stoppedRef.current = false
errorCountRef.current = 0
startedAtRef.current = Date.now()

const userMissionId = localStorage.getItem('userMissionId')
const accessToken = localStorage.getItem('access_token')

const stopCamera = () => {
  if (timeoutRef.current) {
    clearTimeout(timeoutRef.current)
    timeoutRef.current = null
  }

  if (streamRef.current) {
    streamRef.current.getTracks().forEach((track) => track.stop())
    streamRef.current = null
  }
}

const goToFeedback = (result, detail = null) => {
  stoppedRef.current = true
  stopCamera()

  localStorage.setItem('missionResult', result)

  if (detail) {
    localStorage.setItem('missionVerifyResult', JSON.stringify(detail))
  }

  navigate('/feedback', {
    state: {
      missionResult: result,
      result: detail,
    },
  })
}

const getCurrentFrameBlob = () => {
  return new Promise((resolve, reject) => {
    const video = videoRef.current
    const canvas = canvasRef.current

    if (!video || !canvas) {
      reject(new Error('웹캠 화면을 찾을 수 없습니다.'))
      return
    }

    if (!video.videoWidth || !video.videoHeight) {
      reject(new Error('웹캠이 아직 준비되지 않았습니다.'))
      return
    }

    canvas.width = video.videoWidth
    canvas.height = video.videoHeight

    const context = canvas.getContext('2d')

    if (!context) {
      reject(new Error('이미지 캡처를 준비하지 못했습니다.'))
      return
    }

    context.drawImage(video, 0, 0, canvas.width, canvas.height)

    canvas.toBlob(
      (blob) => {
        if (!blob) {
          reject(new Error('이미지 프레임 생성에 실패했습니다.'))
          return
        }

        resolve(blob)
      },
      'image/jpeg',
      0.85
    )
  })
}

const sendCurrentFrame = async () => {
  const imageBlob = await getCurrentFrameBlob()

  const formData = new FormData()
  formData.append('image', imageBlob, 'frame.jpg')

  const response = await fetch(
    `${API_BASE_URL}/api/v1/missions/${userMissionId}/verify-frame`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
      body: formData,
    }
  )

  const data = await response.json()

  console.log('미션 프레임 인증 응답:', data)

  if (!response.ok) {
    throw new Error(
      getErrorMessage(data, `프레임 인증 요청 실패 (${response.status})`)
    )
  }

  return data
}

const verifyLoop = async () => {
  if (stoppedRef.current) return

  const elapsedSeconds = startedAtRef.current
    ? Math.floor((Date.now() - startedAtRef.current) / 1000)
    : 0

  const nextRemainingTime = Math.max(
    VERIFY_TIMEOUT_SECONDS - elapsedSeconds,
    0
  )

  setRemainingTime(nextRemainingTime)

  if (elapsedSeconds >= VERIFY_TIMEOUT_SECONDS) {
    goToFeedback('fail', {
      reason: 'TIMEOUT',
      message: '제한 시간 안에 미션 인증을 완료하지 못했습니다.',
    })
    return
  }

  try {
    const result = await sendCurrentFrame()

    errorCountRef.current = 0
    setErrorMessage('')

    setDetected(result.detected === true)
    setProgress(result.progress_percent ?? 0)

    if (result.completed === true) {
      goToFeedback('success', result)
      return
    }

    if (result.detected === true) {
      setStatusMessage('잘 인식되고 있어요. 잠시 그대로 유지해주세요.')
    } else {
      setStatusMessage('인증할 물건을 화면 중앙에 보여주세요.')
    }
  } catch (error) {
    console.error('프레임 인증 실패:', error)

    errorCountRef.current += 1

    if (errorCountRef.current >= 3) {
      setErrorMessage(error.message || '객체 인증 중 오류가 발생했습니다.')
      setStatusMessage('인증 중 문제가 발생했어요. 잠시 후 다시 시도해주세요.')
    } else {
      setStatusMessage('인증 서버 응답을 기다리고 있어요.')
    }
  }

  if (!stoppedRef.current) {
    timeoutRef.current = setTimeout(verifyLoop, 500)
  }
}

const startCamera = async () => {
  if (!userMissionId) {
    setStatusMessage('미션 정보를 찾을 수 없습니다.')
    setErrorMessage('userMissionId가 없습니다. 미션을 다시 시작해주세요.')
    return
  }

  if (!accessToken) {
    setStatusMessage('로그인이 만료되었습니다.')
    setErrorMessage('다시 로그인해주세요.')
    return
  }

  try {
    setStatusMessage('웹캠 권한을 요청하고 있어요.')

    const stream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: 'user',
      },
      audio: false,
    })

    streamRef.current = stream

    if (videoRef.current) {
      videoRef.current.srcObject = stream
      await videoRef.current.play()
    }

    setCameraReady(true)
    setStatusMessage('인증할 물건을 화면 중앙에 보여주세요.')

    timeoutRef.current = setTimeout(verifyLoop, 500)
  } catch (error) {
    console.error('웹캠 실행 실패:', error)
    setStatusMessage('웹캠을 실행하지 못했습니다.')
    setErrorMessage('카메라 권한을 허용해주세요.')
  }
}

startCamera()

return () => {
  stoppedRef.current = true
  stopCamera()
}

}, [navigate])

const missionLabel = MISSION_LABELS[missionCode] || '미션'
const targetLabel = MISSION_TARGETS[missionCode] || '인증 대상'

return (
<PageLayout>
<div className="verify-page">
<div className="verify-card">
<h1 className="verify-title">미션 인증을 위한 웹캠 활성화</h1>

      <div className="verify-body">
        <div className="mission-label">
          현재 미션: <strong>{missionLabel}</strong>
        </div>

        <div className="mission-target">
          감지 대상: <strong>{targetLabel}</strong>
        </div>

        <div className="webcam-placeholder">
          <video
            ref={videoRef}
            className="webcam-video"
            autoPlay
            playsInline
            muted
          />

          {!cameraReady && (
            <div className="webcam-inner">웹캠을 준비하고 있어요.</div>
          )}
        </div>

        <canvas ref={canvasRef} style={{ display: 'none' }} />

        <div className="verify-status">
          <div>{statusMessage}</div>

          <div>
            인식 상태:{' '}
            <strong>{detected ? '감지됨' : '감지 대기 중'}</strong>
          </div>

          <div>
            진행률: <strong>{progress}%</strong>
          </div>

          <div>남은 시간: {remainingTime}s</div>

          <div className="verify-progress">
            <div
              className="verify-progress-bar"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        {errorMessage && (
          <div className="verify-warning">
            {errorMessage}
          </div>
        )}
      </div>
    </div>
  </div>
</PageLayout>

)
}