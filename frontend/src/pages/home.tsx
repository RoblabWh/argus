import { Routes, Route } from "react-router-dom";
import { useState } from 'react'
import reactLogo from '@/assets/react.svg'
import argusLogo from '@/assets/Argus_icon_Light_crop.png'
import whLogo from '@/assets/Westfälische_Hochschule_Logo.svg'
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



export default function Home() {
  return (
    <>


      {/* [{ label: "Home", href: "/" }]} /> */}
      <Card className="flex flex-col justify-center max-w-md mx-auto mt-10 p-6 bg-white shadow-lg rounded-lg">
        <CardHeader>
          <CardTitle>ARGUS 2.0</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between p-4  text-white h-20">
            <a href="https://github.com/RoblabWh/argus" target="_blank">
              <img src={argusLogo} className="max-w-20 p-2 m-2" alt="ARGUS logo" />
            </a>
            <Separator orientation="vertical" />
            <a href="https://w-hs.de" target="_blank">
              <img src={whLogo} className="max-w-40 m-2" alt="Westfälische Hochschule logo" />
            </a>
          </div>
        </CardContent>
        <CardFooter>
          <p>New Version with redesigned Frontend coming soon! </p>
        </CardFooter>
      </Card>
    </>
  )
}
