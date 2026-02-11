import { Routes, Route } from 'react-router-dom'
import { PageLayout } from './components/layout/PageLayout'
import Dashboard from './pages/Dashboard'
import PropertySearch from './pages/PropertySearch'
import PropertyDetail from './pages/PropertyDetail'
import Pipeline from './pages/Pipeline'
import FinancialCalc from './pages/FinancialCalc'
import Demographics from './pages/Demographics'
import ScrapingAdmin from './pages/ScrapingAdmin'

function App() {
  return (
    <PageLayout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/search" element={<PropertySearch />} />
        <Route path="/property/:id" element={<PropertyDetail />} />
        <Route path="/pipeline" element={<Pipeline />} />
        <Route path="/calculator" element={<FinancialCalc />} />
        <Route path="/demographics" element={<Demographics />} />
        <Route path="/admin/scraping" element={<ScrapingAdmin />} />
      </Routes>
    </PageLayout>
  )
}

export default App
