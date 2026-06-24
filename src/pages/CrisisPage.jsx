import { useEffect, useMemo, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import PageLayout from '../components/PageLayout';
import Button from '../components/Button';

const DEFAULT_CRISIS_SUPPORT = {
title: '도움을 요청하세요',
message:
'지금 혼자 감당하지 말고 바로 연락 가능한 사람이나 전문 상담기관에 도움을 요청해주세요.',
primary_contact: null,
secondary_contacts: [
{
contact_type: 'SUICIDE_HOTLINE',
label: '자살예방 상담전화',
phone: '109',
display_phone: '109',
phone_uri: 'tel:109',
},
{
contact_type: 'POLICE_EMERGENCY',
label: '경찰 긴급신고',
phone: '112',
display_phone: '112',
phone_uri: 'tel:112',
},
{
contact_type: 'MEDICAL_EMERGENCY',
label: '구급·응급신고',
phone: '119',
display_phone: '119',
phone_uri: 'tel:119',
},
],
has_registered_contact: false,
nearby_hospital_search_enabled: false,
tts_text:
'도움을 요청하세요. 지금 혼자 있지 말고 화면의 연락처로 바로 도움을 요청해주세요. 즉각적인 위험이 있다면 112 또는 119에 연락해주세요.',
};

function getStoredCrisisSupport() {
const stored = localStorage.getItem('crisisSupport');

if (!stored) {
    return DEFAULT_CRISIS_SUPPORT;
}

try {
    const parsed = JSON.parse(stored);

    return {
        ...DEFAULT_CRISIS_SUPPORT,
        ...parsed,
        secondary_contacts:
            parsed.secondary_contacts ||
            DEFAULT_CRISIS_SUPPORT.secondary_contacts,
    };
} catch (error) {
    return DEFAULT_CRISIS_SUPPORT;
}

}

function getKoreanVoice() {
if (!window.speechSynthesis) return null;

const voices = window.speechSynthesis.getVoices();

return (
    voices.find((voice) => voice.lang === 'ko-KR') ||
    voices.find((voice) => voice.lang?.includes('ko')) ||
    voices.find((voice) => voice.name?.includes('Korean')) ||
    null
);

}

function speakCrisisText(text) {
if (!text || !window.speechSynthesis) return;

const utterance = new SpeechSynthesisUtterance(text);
const koreanVoice = getKoreanVoice();

utterance.lang = 'ko-KR';

if (koreanVoice) {
    utterance.voice = koreanVoice;
}

utterance.rate = 1;
utterance.pitch = 1;
utterance.volume = 1;

utterance.onstart = () => {
    console.log('위기 지원 TTS 시작');
};

utterance.onerror = (event) => {
    console.error('위기 지원 TTS 오류:', event);
};

window.speechSynthesis.cancel();
window.speechSynthesis.speak(utterance);
window.speechSynthesis.resume();

}

export default function CrisisPage() {
const navigate = useNavigate();
const hasSpokenRef = useRef(false);

const crisisSupport = useMemo(() => getStoredCrisisSupport(), []);

const contacts = useMemo(() => {
    const result = [];

    if (crisisSupport.primary_contact) {
        result.push({
            ...crisisSupport.primary_contact,
            isPrimary: true,
        });
    }

    if (Array.isArray(crisisSupport.secondary_contacts)) {
        crisisSupport.secondary_contacts.forEach((contact) => {
            result.push({
                ...contact,
                isPrimary: false,
            });
        });
    }

    return result;
}, [crisisSupport]);

useEffect(() => {
    if (hasSpokenRef.current) return;

    hasSpokenRef.current = true;

    if (window.speechSynthesis?.getVoices().length > 0) {
        speakCrisisText(crisisSupport.tts_text);
    } else if (window.speechSynthesis) {
        window.speechSynthesis.onvoiceschanged = () => {
            speakCrisisText(crisisSupport.tts_text);
            window.speechSynthesis.onvoiceschanged = null;
        };
    }

    return () => {
        if (window.speechSynthesis) {
            window.speechSynthesis.onvoiceschanged = null;
            window.speechSynthesis.cancel();
        }
    };
}, [crisisSupport]);

const handleBackToChat = () => {
    navigate('/chat');
};

return (
    <PageLayout>
        <div className="crisis-page">
            <div className="crisis-card">
                <h1 className="crisis-title">{crisisSupport.title}</h1>

                <p className="crisis-message">{crisisSupport.message}</p>

                <div className="crisis-contact-list">
                    {contacts.map((contact) => (
                        <a
                            key={`${contact.contact_type}-${contact.phone}`}
                            href={contact.phone_uri}
                            className={
                                contact.isPrimary
                                    ? 'crisis-contact-button crisis-contact-button-primary'
                                    : 'crisis-contact-button'
                            }
                        >
                            <span className="crisis-contact-label">
                                {contact.label}
                            </span>
                            <span className="crisis-contact-number">
                                {contact.display_phone}
                            </span>
                        </a>
                    ))}
                </div>

                <div className="crisis-actions">
                    <Button
                        onClick={() => speakCrisisText(crisisSupport.tts_text)}
                        variant="primary"
                    >
                        음성안내 다시 듣기
                    </Button>

                    <Button onClick={handleBackToChat} variant="secondary">
                        채팅으로 돌아가기
                    </Button>
                </div>
            </div>
        </div>
    </PageLayout>
);

}