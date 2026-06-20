import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import PageLayout from '../components/PageLayout'
import Button from '../components/Button'

const DUMMY_USER_TEXT = '나 오늘 물도 안마시고 기운이 없어'
const AI_FOLLOW_UP = '많이 지쳐 보이네요. 지금은 작은 행동부터 시작해볼까요?'
const AI_NUDGE = 'Nudge!'
const DANGER_KEYWORDS = ['죽고 싶', '사라지고 싶', '자해', '끝내고 싶']

export default function ChatPage() {
  const navigate = useNavigate()
  const [userName, setUserName] = useState('사용자')
  const [messages, setMessages] = useState([])
  const [listening, setListening] = useState(false)
  const [actionCompleted, setActionCompleted] = useState(false)

  useEffect(() => {
    const storedUser = localStorage.getItem('userInfo')
    let name = '사용자'

    if (storedUser) {
      try {
        const parsed = JSON.parse(storedUser)
        if (parsed?.name?.trim()) {
          name = parsed.name.trim()
        }
      } catch (error) {
        // ignore invalid JSON
      }
    }

    setUserName(name)
    setMessages([{ role: 'ai', text: `${name}님 오늘 어떠세요?` }])
  }, [])

  const handleVoiceClick = () => {
    if (listening || actionCompleted) {
      return
    }

    setListening(true)

    setTimeout(() => {
      setMessages((prevMessages) => [
        ...prevMessages,
        { role: 'user', text: DUMMY_USER_TEXT }
      ])

      localStorage.setItem(
        'todayChat',
        JSON.stringify({ text: DUMMY_USER_TEXT, timestamp: new Date().toISOString() })
      )

      setListening(false)
      setActionCompleted(true)

      const hasDangerKeyword = DANGER_KEYWORDS.some((keyword) =>
        DUMMY_USER_TEXT.includes(keyword)
      )

      setTimeout(() => {
        setMessages((prevMessages) => [
          ...prevMessages,
          { role: 'ai', text: AI_FOLLOW_UP }
        ])

        setTimeout(() => {
          if (hasDangerKeyword) {
            navigate('/crisis')
            return
          }

          setMessages((prevMessages) => [
            ...prevMessages,
            { role: 'ai', text: AI_NUDGE }
          ])

          localStorage.setItem('recommendedMission', 'drink_water')

          setTimeout(() => {
            navigate('/mission')
          }, 3000)
        }, 1000)
      }, 1000)
    }, 1000)
  }

  return (
    <PageLayout>
      <div className="chat-page">
        <div className="chat-window">
          {messages.map((message, index) => (
            <div
              key={index}
              className={`chat-message chat-message--${message.role}`}
            >
              <div className="chat-bubble">
                {message.text}
              </div>
            </div>
          ))}
        </div>

        <div className="chat-footer">
          <Button
            onClick={handleVoiceClick}
            className="voice-button"
            disabled={listening || actionCompleted}
          >
            {listening ? '듣는 중...' : '🎙️ 음성 입력'}
          </Button>
        </div>
      </div>
    </PageLayout>
  )
}
