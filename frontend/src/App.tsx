import { Link, Navigate, Route, Routes } from 'react-router'
import { AppLayout, GuestOnly, RequireAuth } from './components/AppLayout'
import { btn } from './components/ui'
import AccountPage from './pages/AccountPage'
import AuthPage from './pages/AuthPage'
import ComparePage from './pages/ComparePage'
import PlannerPage from './pages/PlannerPage'
import TripFormPage from './pages/TripFormPage'
import TripsPage from './pages/TripsPage'

// Routes — frontend-spec.md §2
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/trips" replace />} />
      <Route path="/login" element={<GuestOnly><AuthPage mode="login" /></GuestOnly>} />
      <Route path="/signup" element={<GuestOnly><AuthPage mode="signup" /></GuestOnly>} />
      <Route element={<RequireAuth><AppLayout /></RequireAuth>}>
        <Route path="/trips" element={<TripsPage />} />
        <Route path="/trips/new" element={<TripFormPage />} />
        <Route path="/trips/:tripId" element={<PlannerPage />} />
        <Route path="/trips/:tripId/edit" element={<TripFormPage />} />
        <Route path="/trips/:tripId/compare" element={<ComparePage />} />
        <Route path="/account" element={<AccountPage />} />
      </Route>
      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}

function NotFound() {
  return (
    <main className="grid min-h-screen place-items-center px-4 text-center">
      <div className="grid justify-items-center gap-3">
        <img src="/favicon.svg" alt="" className="size-16" />
        <h1 className="text-2xl font-bold">Page not found</h1>
        <p className="text-slate-600">This page doesn't exist or has moved.</p>
        <Link to="/trips" className={btn.primary}>Go to my trips</Link>
      </div>
    </main>
  )
}
