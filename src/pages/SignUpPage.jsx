import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import PageLayout from '../components/PageLayout';
import TextInput from '../components/TextInput';
import Button from '../components/Button';
import { signup } from '../api';

export default function SignUpPage() {
    const navigate = useNavigate();
    const [name, setName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [phone, setPhone] = useState('');
    const [guardianContact, setGuardianContact] = useState('');
    const [alertMessage, setAlertMessage] = useState('');
    const [signUpSuccess, setSignUpSuccess] = useState(false);

    const handleSignUp = async () => {
        if (
            !name.trim() ||
            !email.trim() ||
            !password.trim() ||
            !phone.trim() ||
            !guardianContact.trim()
        ) {
            setAlertMessage('모든 필수 항목을 입력해주세요.');
            return;
        }

        try {
            const requestBody = {
                name,
                email,
                password,
                phone,
                guardian_phone: guardianContact,
            };

            const result = await signup(requestBody);

            setSignUpSuccess(true);
            setAlertMessage(result.message || '회원가입이 완료되었습니다.');
        } catch (error) {
            setAlertMessage(error.message || '회원가입에 실패했습니다.');
        }
    };

    return (
        <PageLayout>
            <div className="signup-page">
                <div className="signup-card">
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
            {alertMessage && (
                <div className="modal-overlay" role="dialog" aria-modal="true">
                    <div className="modal-card">
                        <div className="modal-text">{alertMessage}</div>
                        <div className="modal-actions">
                            <Button
                                onClick={() => {
                                    setAlertMessage('');
                                    if (signUpSuccess) navigate('/');
                                }}
                                variant="primary"
                            >
                                확인
                            </Button>
                        </div>
                    </div>
                </div>
            )}
        </PageLayout>
    );
}
