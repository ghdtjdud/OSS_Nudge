import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import PageLayout from '../components/PageLayout'

function getMessageText(message, fallback = '응답을 불러왔습니다.') {
if (!message) return fallback

if (typeof message === 'string') {
return message
}

if (typeof message === 'object') {
return (
message.content ||
message.text ||
message.message ||
message.assistant_message ||
message.assistantMessage ||
fallback
)
}

return fallback
}

function getSessionId(response) {
return (
response.session_id ||
response.sessionId ||
response.id ||
response.session?.id ||
response.chat_session?.id
)
}

function getRecommendedMission(response) {
return response.recommendedMission || response.recommended_mission || null
}

function shouldOpenMission(response) {
const recommendedMission = getRecommendedMission(response)

return (
response.action === 'OPEN_MISSION_VERIFICATION' &&
(response.shouldNavigateToMission === true ||
response.should_navigate_to_mission === true) &&
recommendedMission !== null
)
}

function saveMissionData(response) {
const recommendedMission = getRecommendedMission(response)

if (!recommendedMission) return

const missionData = {
...recommendedMission,

card_title:
  recommendedMission.card_title ||
  response.card_title ||
  recommendedMission.cardTitle ||
  response.cardTitle,

card_subtitle:
  recommendedMission.card_subtitle ||
  response.card_subtitle ||
  recommendedMission.cardSubtitle ||
  response.cardSubtitle,

verification_title:
  recommendedMission.verification_title ||
  response.verification_title ||
  recommendedMission.verificationTitle ||
  response.verificationTitle,

verification_subtitle:
  recommendedMission.verification_subtitle ||
  response.verification_subtitle ||
  recommendedMission.verificationSubtitle ||
  response.verificationSubtitle,

user_mission_id:
  recommendedMission.user_mission_id ||
  response.user_mission_id ||
  recommendedMission.userMissionId ||
  response.userMissionId,

mission_code:
  recommendedMission.mission_code ||
  response.mission_code ||
  recommendedMission.missionCode ||
  response.missionCode,

verification_code:
  recommendedMission.verification_code ||
  response.verification_code ||
  recommendedMission.verificationCode ||
  response.verificationCode,

instance_key:
  recommendedMission.instance_key ||
  response.instance_key ||
  recommendedMission.instanceKey ||
  response.instanceKey,

status: recommendedMission.status || response.status,
title: recommendedMission.title || response.title,
description: recommendedMission.description || response.description,
reason: recommendedMission.reason || response.reason,

mission_type:
  recommendedMission.mission_type ||
  response.mission_type ||
  recommendedMission.missionType ||
  response.missionType,

}

localStorage.setItem('recommendedMission', JSON.stringify(missionData))
console.log('저장된 미션 데이터:', missionData)
}

function speakText(text, onEnd) {
if (!text || !window.speechSynthesis) {
onEnd?.()
return
}

window.speechSynthesis.cancel()

const utterance = new SpeechSynthesisUtterance(text)
utterance.lang = 'ko-KR'
utterance.rate = 1
utterance.pitch = 1

utterance.onend = () => {
onEnd?.()
}

utterance.onerror = () => {
onEnd?.()
}

window.speechSynthesis.speak(utterance)
}

export default function ChatPage() {
const navigate = useNavigate()

const hasCreatedSession = useRef(false)
const mediaRecorderRef = useRef(null)
const audioChunksRef = useRef([])
const streamRef = useRef(null)

const [messages, setMessages] = useState([])
const [sessionId, setSessionId] = useState(null)
const [loading, setLoading] = useState(true)
const [recording, setRecording] = useState(false)
const [sending, setSending] = useState(false)
const [errorMessage, setErrorMessage] = useState('')

useEffect(() => {
const createChatSession = async () => {
if (hasCreatedSession.current) return
hasCreatedSession.current = true

  try {
    setLoading(true)
    setErrorMessage('')

    const token = localStorage.getItem('access_token')

    const response = await fetch('http://localhost:8000/api/v1/chat/sessions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
    })

    const data = await response.json()

    console.log('채팅 세션 생성 응답:', data)

    if (!response.ok) {
      throw new Error(JSON.stringify(data.detail || data, null, 2))
    }

    const newSessionId = getSessionId(data)

    const initialMessage = getMessageText(
      data.initial_message ||
        data.initialMessage ||
        data.message ||
        data.assistant_message ||
        data.assistantMessage,
      '오늘은 어떤 하루를 보내고 계신가요?'
    )

    if (!newSessionId) {
      throw new Error('채팅 세션 ID를 찾을 수 없습니다.')
    }

    setSessionId(newSessionId)
    localStorage.setItem('chatSessionId', newSessionId)

    setMessages([
      {
        role: 'ai',
        text: initialMessage,
      },
    ])
  } catch (error) {
    console.error('채팅 세션 생성 실패:', error)

    setErrorMessage(error.message || '채팅 세션을 생성하지 못했습니다.')
    setMessages([
      {
        role: 'ai',
        text: '채팅을 불러오지 못했어요. 잠시 후 다시 시도해주세요.',
      },
    ])
  } finally {
    setLoading(false)
  }
}

createChatSession()

return () => {
  if (streamRef.current) {
    streamRef.current.getTracks().forEach((track) => track.stop())
  }

  if (window.speechSynthesis) {
    window.speechSynthesis.cancel()
  }
}

}, [])

const sendVoiceMessage = async (audioBlob) => {
if (!sessionId) {
alert('채팅 세션이 아직 준비되지 않았습니다.')
return
}

setSending(true)
setErrorMessage('')

try {
  const token = localStorage.getItem('access_token')

  const formData = new FormData()
  formData.append('audio', audioBlob, 'voice.webm')

  const response = await fetch(
    `http://localhost:8000/api/v1/chat/sessions/${sessionId}/voice-messages`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: formData,
    }
  )

  const data = await response.json()

  console.log('음성 채팅 응답:', data)

  if (!response.ok) {
    throw new Error(JSON.stringify(data.detail || data, null, 2))
  }

  const userText = getMessageText(
    data.user_message || data.userMessage,
    '음성 입력을 인식했습니다.'
  )

  const assistantText = getMessageText(
    data.assistant_message || data.assistantMessage || data.message,
    '응답을 불러왔습니다.'
  )

  setMessages((prevMessages) => [
    ...prevMessages,
    {
      role: 'user',
      text: userText,
    },
    {
      role: 'ai',
      text: assistantText,
    },
  ])

  localStorage.setItem(
    'todayChat',
    JSON.stringify({
      text: userText,
      timestamp: new Date().toISOString(),
    })
  )

  if (shouldOpenMission(data)) {
    saveMissionData(data)

    speakText(assistantText, () => {
      setTimeout(() => {
        navigate('/mission')
      }, 500)
    })

    return
  }

  speakText(assistantText)
} catch (error) {
  console.error('음성 메시지 전송 실패:', error)

  const message = error.message || '음성 메시지 전송에 실패했습니다.'

  setErrorMessage(message)
  setMessages((prevMessages) => [
    ...prevMessages,
    {
      role: 'ai',
      text: message,
    },
  ])
} finally {
  setSending(false)
}

}

const startRecording = async () => {
try {
setErrorMessage('')

  const stream = await navigator.mediaDevices.getUserMedia({ audio: true })

  streamRef.current = stream
  audioChunksRef.current = []

  const mediaRecorder = new MediaRecorder(stream, {
    mimeType: 'audio/webm',
  })

  mediaRecorderRef.current = mediaRecorder

  mediaRecorder.ondataavailable = (event) => {
    if (event.data && event.data.size > 0) {
      audioChunksRef.current.push(event.data)
    }
  }

  mediaRecorder.onstop = async () => {
    const audioBlob = new Blob(audioChunksRef.current, {
      type: 'audio/webm',
    })

    stream.getTracks().forEach((track) => track.stop())
    streamRef.current = null

    if (audioBlob.size === 0) {
      alert('녹음된 음성이 없습니다. 다시 시도해주세요.')
      return
    }

    await sendVoiceMessage(audioBlob)
  }

  mediaRecorder.start()
  setRecording(true)
} catch (error) {
  console.error('마이크 권한 오류:', error)
  alert('마이크 권한을 허용해주세요.')
}

}

const stopRecording = () => {
const recorder = mediaRecorderRef.current

if (recorder && recorder.state !== 'inactive') {
  recorder.stop()
}

setRecording(false)

}

const handleVoiceClick = async () => {
if (loading || sending) return

if (!sessionId) {
  alert('채팅 세션이 아직 준비되지 않았습니다. 새로고침 후 다시 시도해주세요.')
  return
}

if (recording) {
  stopRecording()
  return
}

await startRecording()

}

const handleRetry = () => {
window.location.reload()
}

return (
<PageLayout>
<div className="chat-page">
<div className="chat-window">
{loading && (
<div className="chat-message chat-message--ai">
<div className="chat-bubble">채팅을 준비하고 있어요...</div>
</div>
)}

      {messages.map((message, index) => (
        <div
          key={index}
          className={`chat-message chat-message--${message.role}`}
        >
          <div className="chat-bubble">{message.text}</div>
        </div>
      ))}

      {sending && (
        <div className="chat-message chat-message--ai">
          <div className="chat-bubble">음성을 분석하고 답변을 생성하고 있어요...</div>
        </div>
      )}

      {errorMessage && (
        <div className="chat-message chat-message--ai">
          <div className="chat-bubble">오류: {errorMessage}</div>
        </div>
      )}
    </div>

    <div className="chat-footer">
      <button
        type="button"
        onClick={handleVoiceClick}
        className="voice-button"
        disabled={loading || sending}
      >
        {loading
          ? '채팅 준비 중...'
          : sending
            ? '전송 중...'
            : recording
              ? '⏹️ 녹음 종료'
              : '🎙️ 음성 입력'}
      </button>

      {errorMessage && (
        <button
          type="button"
          onClick={handleRetry}
          className="voice-button"
          style={{ marginTop: 8 }}
        >
          다시 시도
        </button>
      )}
    </div>
  </div>
</PageLayout>

)
}