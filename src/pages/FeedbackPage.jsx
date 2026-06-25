import { useEffect, useMemo, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import PageLayout from '../components/PageLayout'
import Button from '../components/Button'

const DEFAULT_SUCCESS_FEEDBACK = {
result_type: 'SUCCESS',
result_title: '오늘의 Nudge 성공🎉',
result_message: '오늘의 Nudge로 천천히 한 걸음씩 나아가요!',
tts_title: '오늘의 Nudge 성공',
tts_text: '오늘의 Nudge로 천천히 한 걸음씩 나아가요!',
button_text: '대시보드로 이동',
next_screen: 'DASHBOARD',
}

const DEFAULT_FAILURE_FEEDBACK = {
result_type: 'FAILURE',
result_title: '미션 확인이 어려워요',
result_message: '다시 한번 미션을 수행해주세요',
tts_title: null,
tts_text: null,
button_text: '미션카드로 이동',
next_screen: 'MISSION_CARD',
}

function getStoredFeedback(missionResult) {
const stored = localStorage.getItem('missionFeedback')

if (!stored) {
return missionResult === 'success'
? DEFAULT_SUCCESS_FEEDBACK
: DEFAULT_FAILURE_FEEDBACK
}

try {
return JSON.parse(stored)
} catch (error) {
return missionResult === 'success'
? DEFAULT_SUCCESS_FEEDBACK
: DEFAULT_FAILURE_FEEDBACK
}
}

function getKoreanVoice() {
if (!window.speechSynthesis) return null

const voices = window.speechSynthesis.getVoices()

return (
voices.find((voice) => voice.lang === 'ko-KR' && voice.name.includes('유나')) ||
voices.find((voice) => voice.lang === 'ko-KR') ||
voices.find((voice) => voice.lang?.includes('ko')) ||
voices.find((voice) => voice.name?.includes('Korean')) ||
null
)
}

export default function FeedbackPage() {
const navigate = useNavigate()
const location = useLocation()

const hasSpokenRef = useRef(false)
const utteranceRef = useRef(null)

const missionResult = useMemo(() => {
const fromState = location.state?.missionResult
const stored = localStorage.getItem('missionResult')

if (fromState === 'success' || stored === 'success') {
  return 'success'
}

return 'fail'

}, [location.state])

const feedback = useMemo(() => {
return location.state?.resultScreen || getStoredFeedback(missionResult)
}, [location.state, missionResult])

useEffect(() => {
if (missionResult !== 'success') return
if (!window.speechSynthesis) return
if (hasSpokenRef.current) return

const speakFeedback = () => {
  if (hasSpokenRef.current) return

  const sentence = [feedback.tts_title, feedback.tts_text]
    .filter(Boolean)
    .join('. ')

  if (!sentence) return

  hasSpokenRef.current = true

  const utterance = new SpeechSynthesisUtterance(sentence)
  const koreanVoice = getKoreanVoice()

  utterance.lang = 'ko-KR'

  if (koreanVoice) {
    utterance.voice = koreanVoice
  }

  utterance.rate = 1
  utterance.pitch = 1
  utterance.volume = 1

  utterance.onstart = () => {
    console.log('TTS 시작:', sentence)
  }

  utterance.onend = () => {
    console.log('TTS 종료')
  }

  utterance.onerror = (event) => {
    console.error('TTS 오류:', event)
  }

  utteranceRef.current = utterance

  console.log('TTS 실행:', {
    sentence,
    koreanVoice,
    voicesCount: window.speechSynthesis.getVoices().length,
  })

  window.speechSynthesis.resume()
  window.speechSynthesis.speak(utterance)
}

if (window.speechSynthesis.getVoices().length > 0) {
  speakFeedback()
} else {
  window.speechSynthesis.onvoiceschanged = speakFeedback
}

return () => {
  if (window.speechSynthesis) {
    window.speechSynthesis.onvoiceschanged = null
  }
}

}, [missionResult, feedback])

const handleClick = () => {
const nextScreen = feedback.next_screen

if (nextScreen === 'DASHBOARD') {
  navigate('/dashboard')
  return
}

if (nextScreen === 'MISSION_CARD') {
  navigate('/mission')
  return
}

if (missionResult === 'success') {
  navigate('/dashboard')
} else {
  navigate('/mission')
}

}

const title =
feedback.result_title ||
(missionResult === 'success'
? DEFAULT_SUCCESS_FEEDBACK.result_title
: DEFAULT_FAILURE_FEEDBACK.result_title)

const message =
feedback.result_message ||
(missionResult === 'success'
? DEFAULT_SUCCESS_FEEDBACK.result_message
: DEFAULT_FAILURE_FEEDBACK.result_message)

const buttonText =
feedback.button_text ||
(missionResult === 'success'
? DEFAULT_SUCCESS_FEEDBACK.button_text
: DEFAULT_FAILURE_FEEDBACK.button_text)

return (
<PageLayout>
<div className="feedback-page">
<div className="feedback-card">
<h1 className="feedback-title">{title}</h1>

      <p className="feedback-subtitle">{message}</p>

      <div className="feedback-actions">
        <Button onClick={handleClick} variant="primary">
          {buttonText}
        </Button>
      </div>
    </div>
  </div>
</PageLayout>

)
}