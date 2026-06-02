/**
 * TextInput 공통 컴포넌트
 * 
 * label이 있는 텍스트 입력 필드
 * 이메일, 비밀번호, 전화번호 등 다양한 타입을 지원합니다.
 * 
 * @component
 * @param {string} label - 입력 필드 라벨
 * @param {string} value - 입력 필드 값
 * @param {Function} onChange - 값 변경 이벤트 핸들러
 * @param {string} type - 입력 필드 타입 ('text', 'email', 'password', 'tel')
 * @param {string} placeholder - 입력 필드 플레이스홀더
 * @param {boolean} required - 필수 입력 여부
 * @param {string} className - 추가 CSS 클래스
 * @returns {JSX.Element}
 */
export default function TextInput({
  label,
  value,
  onChange,
  type = 'text',
  placeholder = '',
  required = false,
  className = ''
}) {
  return (
    <div className="text-input-wrapper">
      {label && (
        <label className="text-input-label">
          {label}
          {required && <span className="text-input-required">*</span>}
        </label>
      )}
      <input
        type={type}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        required={required}
        className={`input ${className}`.trim()}
      />
    </div>
  );
}
