import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import { Shell } from './components/layout/Shell'
import { ProtectedRoute } from './routes/ProtectedRoute'
import { Landing } from './pages/Landing'
import { Auth } from './pages/Auth'
import { Dashboard } from './pages/Dashboard'
import { Identity } from './pages/Identity'
import { Placeholder } from './pages/Placeholder'
import './styles/index.css'

export default function App() { return <BrowserRouter><AuthProvider><Shell><Routes><Route path="/" element={<Landing />} /><Route path="/login" element={<Auth mode="login" />} /><Route path="/register" element={<Auth mode="register" />} /><Route element={<ProtectedRoute />}><Route path="/dashboard" element={<Dashboard />} /><Route path="/identity" element={<Identity />} /><Route path="/profile" element={<Placeholder title="Identity profile" detail="Profile claims and permitted profile updates are not enabled by the current backend yet." />} /><Route path="/agentx" element={<Placeholder title="AgentX" detail="AgentX tool APIs are not enabled by the current backend yet. This route is reserved for the authorized tool foundation." />} /><Route path="/admin/reviews" element={<Placeholder title="Admin review" detail="The backend review endpoints are available to authorized admin accounts; the dashboard UI will be added in a later frontend step." />} /></Route><Route path="*" element={<Landing />} /></Routes></Shell></AuthProvider></BrowserRouter> }
