import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import PageLayout from '../components/PageLayout'
import TextInput from '../components/TextInput'
import Button from '../components/Button'
import { login, setAuthToken } from '../api'

export default function LoginPage() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const handleLogin = async () => {
    if (!email.trim() || !password.trim()) {
      alert('이메일과 비밀번호를 모두 입력해주세요.')
      return
    }

    try {
      const result = await login({ email, password })

      if (result.access_token) {
        setAuthToken(result.access_token)
      }

      if (result.user) {
        localStorage.setItem('userInfo', JSON.stringify(result.user))
      }

      navigate('/intro')
    } catch (error) {
      alert(error.message || '로그인에 실패했습니다.')
    }
  }

  const handleSignUp = () => {
    navigate('/signup')
  }

  return (
    <PageLayout>
      <div className="login-page">
        <div className="login-card">
          <h1 className="title text-center">Nudge</h1>
          <div className="login-form">
            <TextInput
              label="이메일"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="이메일을 입력하세요"
              required
            />
            <TextInput
              label="비밀번호"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="비밀번호를 입력하세요"
              required
            />
            <div className="button-group">
              <Button onClick={handleLogin} variant="primary">
                로그인
              </Button>
              <Button onClick={handleSignUp} variant="secondary">
                회원가입
              </Button>
            </div>
          </div>
        </div>
      </div>
    </PageLayout>
  )
}
