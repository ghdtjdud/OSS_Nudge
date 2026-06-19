/**
 * Button 공통 컴포넌트
 * 
 * @component
 * @param {React.ReactNode} children - 버튼 내용
 * @param {Function} onClick - 클릭 이벤트 핸들러
 * @param {string} type - HTML button type ('button', 'submit', 'reset')
 * @param {string} variant - 버튼 스타일 ('primary', 'secondary', 'danger')
 * @param {boolean} disabled - 비활성화 여부
 * @param {string} className - 추가 CSS 클래스
 * @returns {JSX.Element}
 */
export default function Button({
  children,
  onClick,
  type = 'button',
  variant = 'primary',
  disabled = false,
  className = ''
}) {
  /**
   * variant에 따른 버튼 클래스명 결정
   */
  const getButtonClass = () => {
    let baseClass = 'primary-button';

    if (variant === 'secondary') {
      baseClass = 'secondary-button';
    } else if (variant === 'danger') {
      baseClass = 'danger-button';
    }

    return `${baseClass} ${className}`.trim();
  };

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={getButtonClass()}
    >
      {children}
    </button>
  );
}
