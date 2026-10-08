import { BrowserRouter, Outlet, Route, Routes } from 'react-router-dom'

import Footer from './components/Footer'
import Navbar from './components/Navbar'
import ProtectedRoute from './components/ProtectedRoute'
import ScrollToTop from './components/ScrollToTop'
import Booking from './pages/Booking'
import BookingDetail from './pages/BookingDetail'
import Contact from './pages/Contact'
import ContentPage from './pages/ContentPage'
import Dashboard from './pages/Dashboard'
import Home from './pages/Home'
import HotelDetail from './pages/HotelDetail'
import Hotels from './pages/Hotels'
import Login from './pages/Login'
import NotFound from './pages/NotFound'
import OfferDetail from './pages/OfferDetail'
import Offers from './pages/Offers'
import Register from './pages/Register'

/** Public shell: CMS-driven header + footer around the routed page. */
function SiteLayout() {
  return (
    <div className="page-shell">
      <Navbar />
      <main className="page-main">
        <Outlet />
      </main>
      <Footer />
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <ScrollToTop />
      <Routes>
        {/* Auth pages render full-screen without the marketing chrome. */}
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />

        <Route element={<SiteLayout />}>
          <Route index element={<Home />} />
          <Route path="hotels" element={<Hotels />} />
          <Route path="hotels/:slug" element={<HotelDetail />} />
          <Route
            path="hotels/:slug/book"
            element={
              <ProtectedRoute>
                <Booking />
              </ProtectedRoute>
            }
          />
          <Route
            path="dashboard"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="dashboard/bookings"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="dashboard/bookings/:reference"
            element={
              <ProtectedRoute>
                <BookingDetail />
              </ProtectedRoute>
            }
          />
          <Route
            path="dashboard/profile"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="dashboard/reviews"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />

          <Route path="about" element={<ContentPage page="about" />} />
          {/* Offers is a dedicated deals marketplace, not a CMS text page. */}
          <Route path="offers" element={<Offers />} />
          <Route path="offers/:slug" element={<OfferDetail />} />
          {/* The Contact page is its own CMS-driven screen, not a text section. */}
          <Route path="contact" element={<Contact />} />
          <Route path="privacy" element={<ContentPage page="privacy" />} />
          <Route path="terms" element={<ContentPage page="terms" />} />
          <Route path="cookies" element={<ContentPage page="cookies" />} />

          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
