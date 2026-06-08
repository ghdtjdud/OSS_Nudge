import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import './styles/theme.css'
import './App.css'

// Pages import
import LoginPage from './pages/LoginPage'
import SignUpPage from './pages/SignUpPage'
import IntroPage from './pages/IntroPage'
import SurveyPage from './pages/SurveyPage'
import ChatPage from './pages/ChatPage'
import MissionPage from './pages/MissionPage'
import VerifyPage from './pages/VerifyPage'
import FeedbackPage from './pages/FeedbackPage'
import DashboardPage from './pages/DashboardPage'
import MyPage from './pages/MyPage'
import CrisisPage from './pages/CrisisPage'

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<LoginPage />} />
        <Route path="/signup" element={<SignUpPage />} />
        <Route path="/intro" element={<IntroPage />} />
        <Route path="/survey" element={<SurveyPage />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/mission" element={<MissionPage />} />
        <Route path="/verify" element={<VerifyPage />} />
        <Route path="/feedback" element={<FeedbackPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/mypage" element={<MyPage />} />
        <Route path="/crisis" element={<CrisisPage />} />
      </Routes>
    </Router>
  )
}

export default App
