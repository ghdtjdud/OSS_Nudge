import React from 'react'
import { useNavigate } from 'react-router-dom'

export default function BackButton({ onClick, to, className = 'back-button' }) {
	const navigate = useNavigate()

	const handleClick = (e) => {
		if (onClick) onClick(e)
		if (to) navigate(to)
		else navigate(-1)
	}

	return (
		<button type="button" className={className} onClick={handleClick} aria-label="뒤로가기">
			<svg
				width="36"
				height="36"
				viewBox="0 0 48 36"
				xmlns="http://www.w3.org/2000/svg"
				role="img"
				aria-hidden="false"
			>
				<title>뒤로가기</title>
				<path d="M22 11l-8 7.5L22 26" stroke="#4B6B2B" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" fill="none" />
				<path d="M32 18.5H14" stroke="#4B6B2B" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" fill="none" />
			</svg>
		</button>
	)
}
