import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import PageLayout from '../components/PageLayout'
import TextInput from '../components/TextInput'
import Button from '../components/Button'

export default function SignUpPage() {
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [phone, setPhone] = useState('')
  const [guardianContact, setGuardianContact] = useState('')

  const handleSignUp = () => {
    if (
      !name.trim() ||
      !email.trim() ||
      !password.trim() ||
      !phone.trim() ||
      !guardianContact.trim()
    ) {
      alert('모든 필수 항목을 입력해주세요.')
      return
    }

    const userInfo = {
      name,
      email,
      password,
      phone,
      guardianContact
    }

    localStorage.setItem('userInfo', JSON.stringify(userInfo))
    alert('회원가입이 완료되었습니다.')
    navigate('/')
  }

  return (
    <PageLayout>
      <div className="signup-page">
        <div className="signup-card">
          <h1 className="title text-center">Nudge</h1>
          <div className="signup-form">
            <TextInput
              label="이름"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="이름을 입력하세요"
              required
            />
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
            <TextInput
              label="전화번호"
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="전화번호를 입력하세요"
              required
            />
            <TextInput
              label="보호자 및 주치의 연락처"
              value={guardianContact}
              onChange={(e) => setGuardianContact(e.target.value)}
              placeholder="보호자 및 주치의 연락처를 입력하세요"
              required
            />
            <div className="button-group">
              <Button onClick={handleSignUp} variant="primary">
                회원가입
              </Button>
            </div>
          </div>
        </div>
      </div>
    </PageLayout>
  )
}
