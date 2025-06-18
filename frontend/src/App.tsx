import { Routes, Route } from "react-router-dom";
import { useState } from 'react'
import reactLogo from './assets/react.svg'
import argusLogo from './assets/Argus_icon_Light_crop.png'
import whLogo from './assets/Westfälische_Hochschule_Logo.svg'
import './App.css'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import TopMenuBar from "@/components/menubar"
import Home from "@/pages/home";
import About from "@/pages/about";
import Settings from "@/pages/settings";
import Overview from "@/pages/overview";


function App() {
  const [count, setCount] = useState(0)

  return (
    <>
      <TopMenuBar breadcrumbs={[]}/>
      
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/about" element={<About />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/overview" element={<Overview />} />
        <Route path="*" element={<div>404 Not Found</div>} />
      </Routes>
    </>
  )
}

export default App
