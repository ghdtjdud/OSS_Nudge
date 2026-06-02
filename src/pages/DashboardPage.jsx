import PageLayout from '../components/PageLayout'

export default function DashboardPage() {
  return (
    <PageLayout>
      <div className="container">
        <h1 className="title">대시보드</h1>
        <p className="subtitle text-center">
          당신의 진행 상황을 확인하세요
        </p>
      </div>
    </PageLayout>
  )
}
