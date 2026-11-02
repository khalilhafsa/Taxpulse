import { BrowserRouter, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import Alerts from './pages/Alerts'
import ClientDetail from './pages/ClientDetail'
import Clients from './pages/Clients'
import NewClient from './pages/NewClient'
import Matrix from './pages/Matrix'
import Outreach from './pages/Outreach'
import Overview from './pages/Overview'
import Quality from './pages/Quality'
import Runs from './pages/Runs'
import Settings from './pages/Settings'
import NewUpdate from './pages/NewUpdate'
import UpdateDetail from './pages/UpdateDetail'
import Updates from './pages/Updates'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Overview />} />
          <Route path="clients" element={<Clients />} />
          <Route path="clients/new" element={<NewClient />} />
          <Route path="clients/:id" element={<ClientDetail />} />
          <Route path="updates" element={<Updates />} />
          <Route path="updates/new" element={<NewUpdate />} />
          <Route path="updates/:id" element={<UpdateDetail />} />
          <Route path="matrix" element={<Matrix />} />
          <Route path="alerts" element={<Alerts />} />
          <Route path="outreach" element={<Outreach />} />
          <Route path="runs" element={<Runs />} />
          <Route path="quality" element={<Quality />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
