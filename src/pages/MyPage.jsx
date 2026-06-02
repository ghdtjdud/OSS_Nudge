import PageLayout from '../components/PageLayout'

export default function MyPage() {
  return (
    <PageLayout>
      <div className="container">
        <h1 className="title">마이페이지</h1>
        <p className="subtitle text-center">
          개인정보를 관리하세요
        </p>
      </div>
    </PageLayout>
  )
}
