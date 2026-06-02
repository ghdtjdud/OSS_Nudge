/**
 * PageLayout 공통 컴포넌트
 * 
 * 자연 친화적 배경을 가진 페이지 레이아웃 래퍼
 * 화면 중앙 정렬 및 세로 방향 정렬을 제공합니다.
 * 
 * @component
 * @param {React.ReactNode} children - 페이지 콘텐츠
 * @param {string} className - 추가 CSS 클래스
 * @returns {JSX.Element}
 */
export default function PageLayout({ children, className = '' }) {
  return (
    <div className={`page ${className}`.trim()}>
      {children}
    </div>
  );
}
