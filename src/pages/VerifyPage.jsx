import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import PageLayout from '../components/PageLayout';

const MISSION_TARGETS = {
    drink_water: ['cup'],
    brush_teeth: ['toothbrush'],
    take_medicine: ['pill'],
    eat_meal: ['utensil', 'bowl'],
};

const MISSION_LABELS = {
    drink_water: '물 마시기',
    brush_teeth: '양치하기',
    take_medicine: '약 복용',
    eat_meal: '식사하기',
};

export default function VerifyPage() {
    const navigate = useNavigate();
    const [selectedMission, setSelectedMission] = useState('drink_water');
    const [remainingTime, setRemainingTime] = useState(15);
    const [successCount, setSuccessCount] = useState(0);
    const [statusMessage, setStatusMessage] = useState(
        '웹캠 인증을 위한 감지를 시작합니다.',
    );

    useEffect(() => {
        const stored = localStorage.getItem('selectedMission') || 'drink_water';
        setSelectedMission(stored);
    }, []);

    useEffect(() => {
        if (!selectedMission) return;

        let timer = 15;
        let localSuccessCount = 0;
        let finished = false;
        const abortController = new AbortController();

        const submitResult = (result) => {
            if (finished) return;
            finished = true;
            localStorage.setItem('missionResult', result);
            navigate('/feedback');
        };

        const updateStatus = (message) => {
            if (!finished) {
                setStatusMessage(message);
            }
        };

        const detectTarget = MISSION_TARGETS[selectedMission] || [];

        const callYoloApi = async () => {
            if (finished) return;
            try {
                updateStatus('객체 탐지를 실행 중입니다...');

                const response = await fetch(
                    'http://localhost:8000/api/detect',
                    {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ mission: selectedMission }),
                        signal: abortController.signal,
                        // TODO: react-webcam 연결 이후에는 webcam 프레임을 FormData로 보내도록 변경
                    },
                );

                if (!response.ok) {
                    throw new Error('탐지 서버 응답 실패');
                }

                const data = await response.json();
                const detectedClass = data.detected_class || '';
                const detectedSuccess =
                    data.success === true &&
                    detectTarget.includes(detectedClass);

                if (detectedSuccess) {
                    localSuccessCount += 1;
                    setSuccessCount(localSuccessCount);
                    updateStatus(
                        `감지됨: ${detectedClass} (${localSuccessCount}/3)`,
                    );
                } else {
                    localSuccessCount = 0;
                    setSuccessCount(0);
                    updateStatus('대상 객체가 감지되지 않았습니다.');
                }
            } catch (error) {
                localSuccessCount = 0;
                setSuccessCount(0);
                updateStatus('객체 탐지 서버 연결 대기 중');
            }
        };

        const intervalId = window.setInterval(() => {
            if (finished) return;
            timer -= 1;
            setRemainingTime(timer);
            callYoloApi();

            if (localSuccessCount >= 3) {
                submitResult('success');
                return;
            }

            if (timer <= 0) {
                submitResult('fail');
            }
        }, 1000);

        callYoloApi();

        return () => {
            finished = true;
            window.clearInterval(intervalId);
            abortController.abort();
        };
    }, [selectedMission, navigate]);

    const targetLabel = (MISSION_TARGETS[selectedMission] || []).join(' / ');
    const missionLabel = MISSION_LABELS[selectedMission] || '미션';

    return (
        <PageLayout>
            <div className="verify-page">
                <div className="verify-card">
                    <h1 className="verify-title">
                        미션 인증을 위한 웹캠 활성화
                    </h1>

                    <div className="verify-body">
                        <div className="mission-label">
                            현재 미션: <strong>{missionLabel}</strong>
                        </div>
                        <div className="mission-target">
                            감지 대상: <strong>{targetLabel}</strong>
                        </div>

                        <div className="webcam-placeholder" aria-hidden="true">
                            <div className="webcam-inner">웹캠 영역</div>
                        </div>

                        <div className="verify-status">
                            <div>{statusMessage}</div>
                            <div>남은 시간: {remainingTime}s</div>
                        </div>
                    </div>
                </div>
            </div>
        </PageLayout>
    );
}
