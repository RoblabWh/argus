import { Routes, Route } from "react-router-dom";
import './App.css'
import TopMenuBar from "@/components/menubar"
import Home from "@/pages/home";
import About from "@/pages/about";
import Settings from "@/pages/settings";
import Overview from "@/pages/overview";
import Report from "@/pages/report";
import Group from "./pages/group";
import { BreadcrumbProvider } from "@/contexts/BreadcrumbContext";
import { ThemeProvider } from "@/components/ui/theme-provider";


function App() {

  return (
    <ThemeProvider defaultTheme="system" storageKey="vite-ui-theme">
      <BreadcrumbProvider>
        <div className="min-h-screen bg-gray-100 dark:bg-black ">
          <TopMenuBar />

          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/about" element={<About />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/overview" element={<Overview />} />
            <Route path="/group/:id" element={<Group />} />
            <Route path="/report/:report_id" element={<Report />} />
            <Route path="*" element={<div>404 Not Found</div>} />
          </Routes>
        </div>
      </BreadcrumbProvider>
    </ThemeProvider>
  )
}

export default App
