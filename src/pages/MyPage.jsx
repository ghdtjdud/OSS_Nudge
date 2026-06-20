import { useEffect, useState } from 'react'
import PageLayout from '../components/PageLayout'
import Button from '../components/Button'
import TextInput from '../components/TextInput'

const DEFAULT_USER = {
  name: '홍길동',
  email: '12345@gmail.com',
  password: '12345678',
  phone: '010-1234-5678',
  emergencyContact: '010-0000-0000'
}

export default function MyPage() {
  const [user, setUser] = useState(DEFAULT_USER)
  const [editMode, setEditMode] = useState(false)

  useEffect(() => {
    try {
      const raw = localStorage.getItem('userInfo')
      if (raw) {
        const parsed = JSON.parse(raw)
        setUser({ ...DEFAULT_USER, ...parsed })
      } else {
        setUser(DEFAULT_USER)
      }
    } catch (e) {
      setUser(DEFAULT_USER)
    }
  }, [])

  const handleSave = () => {
    localStorage.setItem('userInfo', JSON.stringify(user))
    setEditMode(false)
  }

  const handleToggle = () => {
    if (editMode) {
      handleSave()
    } else {
      setEditMode(true)
    }
  }

  return (
    <PageLayout>
      <div className="container">
        <h1 className="title">마이페이지</h1>
        <p className="subtitle text-center">개인정보를 관리하세요</p>

        <div className="mypage-card">
          <div className="field-row">
            <div className="field-label">이름:</div>
            <div className="field-value">
              {editMode ? (
                <TextInput
                  label={null}
                  value={user.name}
                  onChange={(e) => setUser({ ...user, name: e.target.value })}
                  placeholder="이름을 입력하세요"
                />
              ) : (
                <span>{user.name}</span>
              )}
            </div>
          </div>

          <div className="field-row">
            <div className="field-label">이메일:</div>
            <div className="field-value">
              {editMode ? (
                <TextInput
                  label={null}
                  type="email"
                  value={user.email}
                  onChange={(e) => setUser({ ...user, email: e.target.value })}
                  placeholder="이메일을 입력하세요"
                />
              ) : (
                <span>{user.email}</span>
              )}
            </div>
          </div>

          <div className="field-row">
            <div className="field-label">비밀번호:</div>
            <div className="field-value">
              {editMode ? (
                <TextInput
                  label={null}
                  type="password"
                  value={user.password}
                  onChange={(e) => setUser({ ...user, password: e.target.value })}
                  placeholder="비밀번호를 입력하세요"
                />
              ) : (
                <span>●●●●●●●●</span>
              )}
            </div>
          </div>

          <div className="field-row">
            <div className="field-label">전화번호:</div>
            <div className="field-value">
              {editMode ? (
                <TextInput
                  label={null}
                  type="tel"
                  value={user.phone}
                  onChange={(e) => setUser({ ...user, phone: e.target.value })}
                  placeholder="전화번호를 입력하세요"
                />
              ) : (
                <span>{user.phone}</span>
              )}
            </div>
          </div>

          <div className="field-row">
            <div className="field-label">보호자 및 주치의 연락처:</div>
            <div className="field-value">
              {editMode ? (
                <TextInput
                  label={null}
                  type="tel"
                  value={user.emergencyContact}
                  onChange={(e) => setUser({ ...user, emergencyContact: e.target.value })}
                  placeholder="긴급 연락처를 입력하세요"
                />
              ) : (
                <span>{user.emergencyContact}</span>
              )}
            </div>
          </div>

          <div className="mypage-actions">
            <Button onClick={handleToggle} variant={editMode ? 'primary' : 'secondary'}>
              {editMode ? '완료' : '정보수정'}
            </Button>
          </div>
        </div>
      </div>
    </PageLayout>
  )
}
