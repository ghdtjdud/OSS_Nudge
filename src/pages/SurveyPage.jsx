import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import PageLayout from '../components/PageLayout';
import Button from '../components/Button';
import { authFetch } from '../api';

const QUESTION_MAP = {
<<<<<<< HEAD
    sleepTime: {
        text: '최근 주로 잠드는 시간은 언제인가요?',
        options: [
            { label: '22시 이전', value: 'BEFORE_22' },
            { label: '22 ~ 24시', value: 'BETWEEN_22_24' },
            { label: '24 ~ 02시', value: 'BETWEEN_00_02' },
            { label: '02시 이후', value: 'AFTER_02' },
        ],
    },
    sleepDuration: {
        text: '최근 평균 수면 시간은 어느 정도인가요?',
        options: [
            { label: '4시간 미만', value: 'UNDER_4' },
            { label: '4 ~ 6시간', value: 'BETWEEN_4_6' },
            { label: '6 ~ 8시간', value: 'BETWEEN_6_8' },
            { label: '8시간 이상', value: 'OVER_8' },
        ],
    },
    mealRoutine: {
        text: '식사는 보통 얼마나 규칙적으로 챙기시나요?',
        options: [
            {
                label: '하루 식사가 전반적으로 불규칙하거나 두 끼 이상 자주 거름',
                value: 'IRREGULAR_MEALS',
            },
            {
                label: '아침/점심/저녁을 대체로 규칙적으로 챙김',
                value: 'REGULAR_MEALS',
            },
            {
                label: '아침은 가끔 거르지만 점심/저녁은 대체로 챙김',
                value: 'SOMETIMES_SKIP_BREAKFAST',
            },
            {
                label: '점심이나 저녁 중 한끼를 자주 거름',
                value: 'SOMETIMES_SKIP_LUNCH_OR_DINNER',
            },
        ],
    },
    hasMedication: {
        text: '정기적으로 복용하는 약이 있나요?',
        options: [
            { label: '현재는 없지만 과거에 있었음', value: 'PAST' },
            { label: '있음', value: 'CURRENT' },
            { label: '없음', value: 'NONE' },
        ],
    },
    medicationTime: {
        text: '약을 어느 시간에 복용하시나요?',
        options: [
            { label: '아침', value: 'MORNING' },
            { label: '점심', value: 'LUNCH' },
            { label: '저녁', value: 'EVENING' },
            { label: '자기 전', value: 'BEFORE_SLEEP' },
        ],
    },
    activityEnergy: {
        text: '최근 일상 활동을 시작하는 데 드는 힘은 어느 정도인가요?',
        options: [
            { label: '쉽게 시작함', value: 'NO_MAJOR_ISSUE' },
            { label: '조금 힘듦', value: 'DIFFICULT_TO_FALL_ASLEEP' },
            { label: '많이 힘듦', value: 'WAKE_FREQUENTLY' },
            { label: '거의 시작하기 어려움', value: 'SLEEP_TOO_MUCH' },
        ],
    },
};

const MEAL_ROUTINE_TO_BREAKFAST_FREQUENCY = {
    IRREGULAR_MEALS: 'VARIES',
    REGULAR_MEALS: 'REGULAR',
    SOMETIMES_SKIP_BREAKFAST: 'SOMETIMES',
    SOMETIMES_SKIP_LUNCH_OR_DINNER: 'REGULAR',
};

const MEAL_ROUTINE_TO_LUNCH_DINNER_PATTERN = {
    IRREGULAR_MEALS: 'SKIP_BOTH_OFTEN',
    REGULAR_MEALS: 'BOTH_REGULAR',
    SOMETIMES_SKIP_BREAKFAST: 'BOTH_REGULAR',
    SOMETIMES_SKIP_LUNCH_OR_DINNER: 'SKIP_LUNCH_OFTEN',
};

function getStepsSequence(answers) {
    const seq = ['sleepTime', 'sleepDuration', 'mealRoutine', 'hasMedication'];
    if (answers.hasMedication === 'CURRENT') seq.push('medicationTime');
    seq.push('activityEnergy');
    return seq;
}

function buildRequestBody(answers) {
    return {
        sleep_bedtime: answers.sleepTime,
        sleep_duration: answers.sleepDuration,
        sleep_condition: answers.activityEnergy || 'NO_MAJOR_ISSUE',
        breakfast_frequency:
            MEAL_ROUTINE_TO_BREAKFAST_FREQUENCY[answers.mealRoutine] ||
            'VARIES',
        lunch_dinner_pattern:
            MEAL_ROUTINE_TO_LUNCH_DINNER_PATTERN[answers.mealRoutine] ||
            'BOTH_REGULAR',
        appetite_change: 'UNKNOWN',
        medication_status: answers.hasMedication,
        medication_timing:
            answers.hasMedication === 'CURRENT' ? answers.medicationTime : null,
        medication_forget_frequency:
            answers.hasMedication === 'CURRENT' ? 'SOMETIMES' : null,
    };
}

export default function SurveyPage() {
    const navigate = useNavigate();

    const [answers, setAnswers] = useState({
        sleepTime: '',
        sleepDuration: '',
        mealRoutine: '',
        hasMedication: '',
        medicationTime: '',
        activityEnergy: '',
    });

    const [stepIndex, setStepIndex] = useState(0);

    const sequence = getStepsSequence(answers);
    const currentKey = sequence[stepIndex];
    const question = QUESTION_MAP[currentKey];

    const handleSelect = async (option) => {
        const nextAnswers = { ...answers, [currentKey]: option.value };

        if (currentKey === 'hasMedication' && option.value !== 'CURRENT') {
            nextAnswers.medicationTime = '';
        }

        setAnswers(nextAnswers);

        const nextSequence = getStepsSequence(nextAnswers);
        const curPos = nextSequence.indexOf(currentKey);
        const nextPos = curPos + 1;

        if (nextPos >= nextSequence.length) {
            localStorage.setItem('initialSurvey', JSON.stringify(nextAnswers));

            try {
                await authFetch('/api/v1/users/me/status', {
                    method: 'PUT',
                    body: JSON.stringify(buildRequestBody(nextAnswers)),
                });

                navigate('/chat');
            } catch (error) {
                alert(error.message);
            }

            return;
        }

        setStepIndex(nextPos);
    };

    const handlePrev = () => {
        if (stepIndex === 0) return;
        setStepIndex(stepIndex - 1);
    };

    return (
        <PageLayout>
            <div className="survey-page">
                <div className="survey-card">
                    <div className="survey-header">
                        <div className="survey-title">설문</div>
                        <div className="survey-progress">
                            {stepIndex + 1} / {sequence.length}
                        </div>
                    </div>

                    <h2 className="survey-question">{question.text}</h2>

                    <div className="survey-options">
                        <div className="survey-options">
                            {question.options.map((opt) => {
                                const isSelected =
                                    answers[currentKey] === opt.value;

                                return (
                                    <div
                                        key={opt.value}
                                        className="survey-option-item"
                                    >
                                        <Button
                                            onClick={() => handleSelect(opt)}
                                            variant={
                                                isSelected
                                                    ? 'primary'
                                                    : 'secondary'
                                            }
                                        >
                                            {opt.label}
                                        </Button>
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    <div className="survey-actions">
                        <Button
                            onClick={handlePrev}
                            variant="secondary"
                            disabled={stepIndex === 0}
                        >
                            이전
                        </Button>
                    </div>
                </div>
            </div>
        </PageLayout>
    );
=======
sleepTime: {
text: '최근 주로 잠드는 시간은 언제인가요?',
options: [
{ label: '22시 이전', value: 'BEFORE_22' },
{ label: '22 ~ 24시', value: 'BETWEEN_22_24' },
{ label: '24 ~ 02시', value: 'BETWEEN_00_02' },
{ label: '02시 이후', value: 'AFTER_02' },
],
},
sleepDuration: {
text: '최근 평균 수면 시간은 어느 정도인가요?',
options: [
{ label: '4시간 미만', value: 'UNDER_4' },
{ label: '4 ~ 6시간', value: 'BETWEEN_4_6' },
{ label: '6 ~ 8시간', value: 'BETWEEN_6_8' },
{ label: '8시간 이상', value: 'OVER_8' },
],
},
mealRoutine: {
  text: '식사는 보통 얼마나 규칙적으로 챙기시나요?',
  options: [
    {
      label: '하루 식사가 전반적으로 불규칙하거나 두 끼 이상 자주 거름',
      value: 'GENERALLY_IRREGULAR',
    },
    {
      label: '아침/점심/저녁을 대체로 규칙적으로 챙김',
      value: 'ALL_MEALS_REGULAR',
    },
    {
      label: '아침은 가끔 거르지만 점심/저녁은 대체로 챙김',
      value: 'SOMETIMES_SKIP_BREAKFAST',
    },
    {
      label: '점심이나 저녁 중 한끼를 자주 거름',
      value: 'OFTEN_SKIP_ONE_MEAL',
    },
  ],
},
hasMedication: {
text: '정기적으로 복용하는 약이 있나요?',
options: [
{ label: '현재는 없지만 과거에 있었음', value: 'PAST' },
{ label: '있음', value: 'CURRENT' },
{ label: '없음', value: 'NONE' },
],
},
medicationTime: {
text: '약을 어느 시간에 복용하시나요?',
options: [
{ label: '아침', value: 'MORNING' },
{ label: '점심', value: 'LUNCH' },
{ label: '저녁', value: 'EVENING' },
{ label: '자기 전', value: 'BEFORE_SLEEP' },
],
},
activityEnergy: {
  text: '최근 일상 활동을 시작하는 데 드는 힘은 어느 정도인가요?',
  options: [
    { label: '쉽게 시작함', value: 'EASY' },
    { label: '조금 힘듦', value: 'SOMEWHAT_DIFFICULT' },
    { label: '많이 힘듦', value: 'VERY_DIFFICULT' },
    { label: '거의 시작하기 어려움', value: 'ALMOST_UNABLE_TO_START' },
  ],
},
}

function getStepsSequence(answers) {
const seq = ['sleepTime', 'sleepDuration', 'mealRoutine', 'hasMedication']

if (answers.hasMedication === 'CURRENT') {
seq.push('medicationTime')
}

seq.push('activityEnergy')

return seq
}

function buildRequestBody(answers) {
return {
sleep_bedtime: answers.sleepTime,
sleep_duration: answers.sleepDuration,
meal_regularity: answers.mealRoutine,
medication_status: answers.hasMedication,
medication_times:
answers.hasMedication === 'CURRENT' && answers.medicationTime
? [answers.medicationTime]
: [],
activity_start_difficulty: answers.activityEnergy,
}
}

export default function SurveyPage() {
const navigate = useNavigate()

const [answers, setAnswers] = useState({
sleepTime: '',
sleepDuration: '',
mealRoutine: '',
hasMedication: '',
medicationTime: '',
activityEnergy: '',
})

const [stepIndex, setStepIndex] = useState(0)
const [isSubmitting, setIsSubmitting] = useState(false)

const sequence = getStepsSequence(answers)
const currentKey = sequence[stepIndex]
const question = QUESTION_MAP[currentKey]

const handleSelect = async (option) => {
if (isSubmitting) return

const nextAnswers = {
  ...answers,
  [currentKey]: option.value,
>>>>>>> 909245a54ec2be43736ef616a7d463261d6c2484
}

if (currentKey === 'hasMedication' && option.value !== 'CURRENT') {
  nextAnswers.medicationTime = ''
}

setAnswers(nextAnswers)

const nextSequence = getStepsSequence(nextAnswers)
const curPos = nextSequence.indexOf(currentKey)
const nextPos = curPos + 1

if (nextPos >= nextSequence.length) {
  localStorage.setItem('initialSurvey', JSON.stringify(nextAnswers))

  try {
    setIsSubmitting(true)

    await authFetch('/api/v1/users/me/status', {
      method: 'PUT',
      body: JSON.stringify(buildRequestBody(nextAnswers)),
    })

    navigate('/chat')
  } catch (error) {
    alert(error.message || '설문 저장에 실패했습니다.')
  } finally {
    setIsSubmitting(false)
  }

  return
}

setStepIndex(nextPos)

}

const handlePrev = () => {
if (stepIndex === 0 || isSubmitting) return
setStepIndex(stepIndex - 1)
}

return (
<PageLayout>
<div className="survey-page">
<div className="survey-card">
<div className="survey-header">
<div className="survey-title">설문</div>
<div className="survey-progress">
{stepIndex + 1} / {sequence.length}
</div>
</div>

      <h2 className="survey-question">{question.text}</h2>

      <div className="survey-options">
        {question.options.map((opt) => {
          const isSelected = answers[currentKey] === opt.value

          return (
            <div key={opt.value} style={{ marginBottom: 8 }}>
              <Button
                onClick={() => handleSelect(opt)}
                variant={isSelected ? 'primary' : 'secondary'}
                disabled={isSubmitting}
              >
                {opt.label}
              </Button>
            </div>
          )
        })}
      </div>

      <div className="survey-actions" style={{ marginTop: 16 }}>
        <Button
          onClick={handlePrev}
          variant="secondary"
          disabled={stepIndex === 0 || isSubmitting}
        >
          이전
        </Button>
      </div>
    </div>
  </div>
</PageLayout>

)
}