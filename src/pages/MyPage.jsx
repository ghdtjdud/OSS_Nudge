import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import PageLayout from '../components/PageLayout';
import Button from '../components/Button';
import TextInput from '../components/TextInput';
import { authFetch, clearAuthToken } from '../api';

const EMPTY_PROFILE_FORM = {
name: '',
email: '',
phone: '',
guardian_phone: '',
current_password: '',
};

const EMPTY_PASSWORD_FORM = {
current_password: '',
new_password: '',
new_password_confirm: '',
};

export default function MyPage() {
const navigate = useNavigate();

const [user, setUser] = useState(null);
const [profileForm, setProfileForm] = useState(EMPTY_PROFILE_FORM);
const [passwordForm, setPasswordForm] = useState(EMPTY_PASSWORD_FORM);

const [viewMode, setViewMode] = useState('profile'); // profile | edit | password

const [isLoading, setIsLoading] = useState(true);
const [isSavingProfile, setIsSavingProfile] = useState(false);
const [isChangingPassword, setIsChangingPassword] = useState(false);
const [isLoggingOut, setIsLoggingOut] = useState(false);

const [errorMessage, setErrorMessage] = useState('');
const [successMessage, setSuccessMessage] = useState('');

const emailChanged = user && profileForm.email !== user.email;

useEffect(() => {
    fetchMyPage();
}, []);

const fetchMyPage = async () => {
    try {
        setIsLoading(true);
        setErrorMessage('');

        const data = await authFetch('/api/v1/users/me');
        const userInfo = data.user;

        setUser(userInfo);
        setProfileForm({
            name: userInfo.name || '',
            email: userInfo.email || '',
            phone: userInfo.phone || '',
            guardian_phone: userInfo.guardian_phone || '',
            current_password: '',
        });
    } catch (error) {
        console.error('마이페이지 조회 실패:', error);
        setErrorMessage(error.message || '마이페이지 정보를 불러오지 못했습니다.');
    } finally {
        setIsLoading(false);
    }
};

const clearLocalSession = () => {
    clearAuthToken();
    localStorage.removeItem('chatSessionId');
    localStorage.removeItem('recommendedMission');
    localStorage.removeItem('selectedMission');
    localStorage.removeItem('userMissionId');
    localStorage.removeItem('verificationCode');
    localStorage.removeItem('missionResult');
    localStorage.removeItem('missionFeedback');
};

const handleProfileChange = (field, value) => {
    setProfileForm((prev) => ({
        ...prev,
        [field]: value,
    }));
};

const handlePasswordChange = (field, value) => {
    setPasswordForm((prev) => ({
        ...prev,
        [field]: value,
    }));
};

const handleStartEdit = () => {
    setViewMode('edit');
    setErrorMessage('');
    setSuccessMessage('');
};

const handleCancelProfileEdit = () => {
    if (!user) return;

    setProfileForm({
        name: user.name || '',
        email: user.email || '',
        phone: user.phone || '',
        guardian_phone: user.guardian_phone || '',
        current_password: '',
    });

    setViewMode('profile');
    setErrorMessage('');
    setSuccessMessage('');
};

const handleGoPasswordMode = () => {
    setViewMode('password');
    setPasswordForm(EMPTY_PASSWORD_FORM);
    setErrorMessage('');
    setSuccessMessage('');
};

const handleCancelPasswordMode = () => {
    setViewMode('profile');
    setPasswordForm(EMPTY_PASSWORD_FORM);
    setErrorMessage('');
    setSuccessMessage('');
};

const handleSaveProfile = async () => {
    if (!profileForm.name.trim()) {
        setErrorMessage('이름을 입력해주세요.');
        return;
    }

    if (!profileForm.email.trim()) {
        setErrorMessage('이메일을 입력해주세요.');
        return;
    }

    if (!profileForm.phone.trim()) {
        setErrorMessage('전화번호를 입력해주세요.');
        return;
    }

    if (emailChanged && !profileForm.current_password.trim()) {
        setErrorMessage('이메일 변경 시 현재 비밀번호를 입력해야 합니다.');
        return;
    }

    try {
        setIsSavingProfile(true);
        setErrorMessage('');
        setSuccessMessage('');

        const payload = {
            name: profileForm.name.trim(),
            email: profileForm.email.trim(),
            phone: profileForm.phone.trim(),
            guardian_phone: profileForm.guardian_phone.trim() || null,
        };

        if (emailChanged) {
            payload.current_password = profileForm.current_password;
        }

        const data = await authFetch('/api/v1/users/me', {
            method: 'PATCH',
            body: JSON.stringify(payload),
        });

        const updatedUser = data.user;

        setUser(updatedUser);
        setProfileForm({
            name: updatedUser.name || '',
            email: updatedUser.email || '',
            phone: updatedUser.phone || '',
            guardian_phone: updatedUser.guardian_phone || '',
            current_password: '',
        });

        setViewMode('profile');
        setSuccessMessage('회원정보가 수정되었습니다.');
    } catch (error) {
        console.error('회원정보 수정 실패:', error);
        setErrorMessage(error.message || '회원정보 수정에 실패했습니다.');
    } finally {
        setIsSavingProfile(false);
    }
};

const handleChangePassword = async () => {
    if (!passwordForm.current_password) {
        setErrorMessage('현재 비밀번호를 입력해주세요.');
        return;
    }

    if (!passwordForm.new_password) {
        setErrorMessage('새 비밀번호를 입력해주세요.');
        return;
    }

    if (!passwordForm.new_password_confirm) {
        setErrorMessage('새 비밀번호 확인을 입력해주세요.');
        return;
    }

    if (passwordForm.new_password !== passwordForm.new_password_confirm) {
        setErrorMessage('새 비밀번호와 비밀번호 확인이 일치하지 않습니다.');
        return;
    }

    if (passwordForm.current_password === passwordForm.new_password) {
        setErrorMessage('현재 비밀번호와 동일한 비밀번호는 사용할 수 없습니다.');
        return;
    }

    try {
        setIsChangingPassword(true);
        setErrorMessage('');
        setSuccessMessage('');

        const data = await authFetch('/api/v1/users/me/password', {
            method: 'PATCH',
            body: JSON.stringify({
                current_password: passwordForm.current_password,
                new_password: passwordForm.new_password,
                new_password_confirm: passwordForm.new_password_confirm,
            }),
        });

        setPasswordForm(EMPTY_PASSWORD_FORM);
        setViewMode('profile');
        setSuccessMessage(data.message || '비밀번호가 변경되었습니다.');
    } catch (error) {
        console.error('비밀번호 변경 실패:', error);
        setErrorMessage(error.message || '비밀번호 변경에 실패했습니다.');
    } finally {
        setIsChangingPassword(false);
    }
};

const handleLogout = async () => {
    try {
        setIsLoggingOut(true);
        setErrorMessage('');
        setSuccessMessage('');

        await authFetch('/api/v1/auth/logout', {
            method: 'POST',
        });
    } catch (error) {
        console.error('로그아웃 API 실패:', error);
    } finally {
        clearLocalSession();
        setIsLoggingOut(false);
        navigate('/');
    }
};

if (isLoading) {
    return (
        <PageLayout>
            <div className="mypage-page">
                <div className="mypage-card">
                    <h1 className="page-title">마이페이지</h1>
                    <p className="page-subtitle">회원 정보를 불러오는 중입니다...</p>
                </div>
            </div>
        </PageLayout>
    );
}

const renderProfileView = () => (
    <>
        <h1 className="page-title">마이페이지</h1>
        <p className="page-subtitle">개인정보를 관리하세요</p>

        <div className="field-row">
            <div className="field-label">이름:</div>
            <div className="field-value">
                <div className="display-value">{user?.name}</div>
            </div>
        </div>

        <div className="field-row">
            <div className="field-label">이메일:</div>
            <div className="field-value">
                <div className="display-value">{user?.email}</div>
            </div>
        </div>

        <div className="field-row">
            <div className="field-label">전화번호:</div>
            <div className="field-value">
                <div className="display-value">{user?.phone}</div>
            </div>
        </div>

        <div className="field-row">
            <div className="field-label">보호자/주치의 연락처:</div>
            <div className="field-value">
                <div className="display-value">
                    {user?.guardian_phone || '등록된 연락처가 없습니다.'}
                </div>
            </div>
        </div>

        <div className="mypage-actions mypage-actions-column">
            <Button onClick={handleStartEdit} variant="secondary">
                정보수정
            </Button>

            <Button onClick={handleGoPasswordMode} variant="secondary">
                비밀번호 변경
            </Button>

            <Button
                onClick={handleLogout}
                variant="secondary"
                disabled={isLoggingOut}
            >
                {isLoggingOut ? '로그아웃 중...' : '로그아웃'}
            </Button>
        </div>
    </>
);

const renderEditView = () => (
    <>
        <h1 className="page-title">정보수정</h1>
        <p className="page-subtitle">변경할 회원정보를 입력하세요</p>

        <div className="field-row">
            <div className="field-label">이름:</div>
            <div className="field-value">
                <TextInput
                    label={null}
                    value={profileForm.name}
                    onChange={(e) => handleProfileChange('name', e.target.value)}
                    placeholder="이름을 입력하세요"
                />
            </div>
        </div>

        <div className="field-row">
            <div className="field-label">이메일:</div>
            <div className="field-value">
                <TextInput
                    label={null}
                    type="email"
                    value={profileForm.email}
                    onChange={(e) => handleProfileChange('email', e.target.value)}
                    placeholder="이메일을 입력하세요"
                />
            </div>
        </div>

        {emailChanged && (
            <div className="field-row">
                <div className="field-label">현재 비밀번호:</div>
                <div className="field-value">
                    <TextInput
                        label={null}
                        type="password"
                        value={profileForm.current_password}
                        onChange={(e) =>
                            handleProfileChange('current_password', e.target.value)
                        }
                        placeholder="이메일 변경 시 현재 비밀번호를 입력하세요"
                    />
                </div>
            </div>
        )}

        <div className="field-row">
            <div className="field-label">전화번호:</div>
            <div className="field-value">
                <TextInput
                    label={null}
                    type="tel"
                    value={profileForm.phone}
                    onChange={(e) => handleProfileChange('phone', e.target.value)}
                    placeholder="전화번호를 입력하세요"
                />
            </div>
        </div>

        <div className="field-row">
            <div className="field-label">보호자/주치의 연락처:</div>
            <div className="field-value">
                <TextInput
                    label={null}
                    type="tel"
                    value={profileForm.guardian_phone}
                    onChange={(e) =>
                        handleProfileChange('guardian_phone', e.target.value)
                    }
                    placeholder="보호자 또는 주치의 연락처를 입력하세요"
                />
            </div>
        </div>

        <div className="mypage-actions mypage-actions-column">
            <Button
                onClick={handleSaveProfile}
                variant="primary"
                disabled={isSavingProfile}
            >
                {isSavingProfile ? '저장 중...' : '저장'}
            </Button>

            <Button
                onClick={handleCancelProfileEdit}
                variant="secondary"
                disabled={isSavingProfile}
            >
                취소
            </Button>
        </div>
    </>
);

const renderPasswordView = () => (
    <>
        <h1 className="page-title">비밀번호 변경</h1>
        <p className="page-subtitle">
            현재 비밀번호 확인 후 새 비밀번호로 변경할 수 있습니다.
        </p>

        <div className="field-row">
            <div className="field-label">현재 비밀번호:</div>
            <div className="field-value">
                <TextInput
                    label={null}
                    type="password"
                    value={passwordForm.current_password}
                    onChange={(e) =>
                        handlePasswordChange('current_password', e.target.value)
                    }
                    placeholder="현재 비밀번호를 입력하세요"
                />
            </div>
        </div>

        <div className="field-row">
            <div className="field-label">새 비밀번호:</div>
            <div className="field-value">
                <TextInput
                    label={null}
                    type="password"
                    value={passwordForm.new_password}
                    onChange={(e) =>
                        handlePasswordChange('new_password', e.target.value)
                    }
                    placeholder="새 비밀번호를 입력하세요"
                />
            </div>
        </div>

        <div className="field-row">
            <div className="field-label">새 비밀번호 확인:</div>
            <div className="field-value">
                <TextInput
                    label={null}
                    type="password"
                    value={passwordForm.new_password_confirm}
                    onChange={(e) =>
                        handlePasswordChange(
                            'new_password_confirm',
                            e.target.value
                        )
                    }
                    placeholder="새 비밀번호를 다시 입력하세요"
                />
            </div>
        </div>

        <div className="mypage-actions mypage-actions-column">
            <Button
                onClick={handleChangePassword}
                variant="primary"
                disabled={isChangingPassword}
            >
                {isChangingPassword ? '변경 중...' : '비밀번호 변경'}
            </Button>

            <Button
                onClick={handleCancelPasswordMode}
                variant="secondary"
                disabled={isChangingPassword}
            >
                취소
            </Button>
        </div>
    </>
);

return (
    <PageLayout>
        <div className="mypage-page">
            <div className="mypage-card">
                {errorMessage && (
                    <p className="error-message">{errorMessage}</p>
                )}

                {successMessage && (
                    <p className="success-message">{successMessage}</p>
                )}

                {viewMode === 'profile' && renderProfileView()}
                {viewMode === 'edit' && renderEditView()}
                {viewMode === 'password' && renderPasswordView()}
            </div>
        </div>
    </PageLayout>
);

}