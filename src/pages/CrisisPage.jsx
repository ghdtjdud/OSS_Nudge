import { useEffect, useState } from 'react'
import PageLayout from '../components/PageLayout'

const DEFAULT_USER = {
  emergencyContact: '연락처 정보 없음'
}

export default function CrisisPage() {
  const [emergencyContact, setEmergencyContact] = useState(DEFAULT_USER.emergencyContact)

  useEffect(() => {
    try {
      const raw = localStorage.getItem('userInfo')
      if (raw) {
        const parsed = JSON.parse(raw)
        setEmergencyContact(parsed?.emergencyContact || DEFAULT_USER.emergencyContact)
      }
    } catch (error) {
      setEmergencyContact(DEFAULT_USER.emergencyContact)
    }
  }, [])

  return (
    <PageLayout>
      <div className="container">
        <div className="crisis-card">
          <h1 className="crisis-title">도움을 요청하세요</h1>
          <p className="crisis-contact-label">보호자 및 주치의</p>
          <p className="crisis-contact-number">{emergencyContact}</p>
        </div>
      </div>
    </PageLayout>
  )
}
