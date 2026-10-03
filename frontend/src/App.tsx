import { Route, Routes } from 'react-router'
import HomePage from './pages/HomePage.tsx'

export default function App() {
  // Real routes (frontend-spec §2) are added in Phase 7.
  return (
    <Routes>
      <Route path="*" element={<HomePage />} />
    </Routes>
  )
}
