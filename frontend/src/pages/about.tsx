import { useEffect } from "react";
import { useBreadcrumbs } from "@/contexts/BreadcrumbContext";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Drone, MapPinned, ShieldCheck, FileText, Workflow, Wrench, Link } from "lucide-react";
// import { Instagram, Youtube, Github, Mail } from "lucide-react";

// Logos (paths as provided / commonly used)
// Adjust the DRZ logo import to your actual asset path if different.
import bmftrLogo from "@/assets/Logo-BMFTR.png";
import whLogoLight from "@/assets/Westfälische_Hochschule_Logo.svg";
import whLogoDark from "@/assets/w-hs_pagelogo-inv.png";
import argusLogolarge from "@/assets/Argus_icon_dark_title-long_white_BG_scaled.PNG";
import drzLogo from "@/assets/DRZ_Logo.jpg"; // TODO: update path/name if needed

export default function About() {
  const { setBreadcrumbs } = useBreadcrumbs();

  useEffect(() => {
    setBreadcrumbs([{ label: "About", href: "/about" }]);
  }, [setBreadcrumbs]);

  return (
    <div className="container mx-auto px-4 pt-6 pb-12">
      <div className="flex flex-wrap items-center gap-6 text-sm text-muted-foreground">
        <div className="min-w-[220px] flex-[1_1_20rem]">
          <img
            src={argusLogolarge}
            alt="Screenshot of Argus application"
            className="mt-2 w-full rounded-md border object-contain md:mt-6"
          />
        </div>
        <div className="min-w-[320px] flex-[2_1_32rem]">
          <header className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <h1 className="text-3xl font-bold tracking-tight">
              About <span className="text-primary">Argus</span>
            </h1>

          </header>

          <p className="mt-4 text-muted-foreground">
            Argus is a modern, reliable tool for <em>documenting</em> and <em>analyzing</em> UAV
            datasets from fire and rescue operations. It evolved from an internal tool that generated
            simple HTML flight reports and stitched images into coarse orthomosaics. Today, Argus
            offers a growing set of features, supports more UAV platforms, and provides a
            user-friendly interface for incident documentation, quality assurance, and analysis.
          </p>

          <p className="mt-4 text-sm text-muted-foreground">
            <strong>What’s in a name?</strong> ARGUS stands for <em>Aerial Rescue and Geospatial
              Utility System</em> and nods to the many-eyed guardian from Greek mythology —
            a fitting reference for a system that brings comprehensive, situational awareness to
            complex missions.
          </p>
        </div>

      </div>

      <div className="mt-8 grid gap-6 md:grid-cols-1">


        <Card className="shadow-sm">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck className="h-5 w-5" />
              Research Project – E-DRZ
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap items-center gap-16 justify-center">
              <a href="https://rettungsrobotik.de/" target="_blank">
                <img
                  src={bmftrLogo}
                  alt="Förderlogo Bundesministerium"
                  className="h-36 w-auto  border-4 border-white rounded-md object-contain"
                />
              </a>
              {/* Light/Dark logo swap for WH */}
              <a href="https://www.w-hs.de/service/informationen-zur-person/person/surmann/" target="_blank">
                <img
                  src={whLogoLight}
                  alt="Westfälische Hochschule Logo"
                  className="block h-22 w-auto object-contain dark:hidden"
                />

                <img
                  src={whLogoDark}
                  alt="Westfälische Hochschule Logo (invertiert)"
                  className="hidden h-22 w-auto object-contain dark:block"
                />
              </a>
              <a href="https://rettungsrobotik.de/" target="_blank">
                <img
                  src={drzLogo}
                  alt="Deutsches Rettungsrobotik-Zentrum (DRZ) Logo"
                  className="h-22 w-auto border-4 border-white rounded-md object-contain"
                />
              </a>
            </div>

            <Separator />

            <p className="text-sm leading-relaxed">
              <strong>E-DRZ – Establishing the German Rescue Robotics Center</strong>
              <br />
              “Etablierung des Deutschen Rettungsrobotik-Zentrums (DRZ)” is the follow-up to the
              project “Aufbau des DRZ (A-DRZ)”, successfully completed in September 2022.
              A-DRZ founded the DRZ e.V. as a non-profit association and equipped it with
              personnel, facilities, test areas, and robotic systems. The Dortmund Fire Service,
              a founding member, significantly shaped the center’s development. In the DRZ
              Living-Lab, member organizations test robotic systems under realistic conditions and
              further develop them for civil protection.
            </p>

            <p className="text-sm leading-relaxed">
              E-DRZ aims to expand the network, close capability gaps, and harden robotic systems
              for regular deployment by BOS (public safety organizations). A key objective is to
              design a <em>Robotic Task Force</em> at the Dortmund site, deploying rescue
              robotics when risks to responders are high, specialized sensors are required, or
              human capabilities are at their limits.
            </p>

            <div className="flex flex-wrap items-center gap-3">
              <Badge variant="outline">Duration: Oct 2022 – Sep 2026</Badge>
            </div>


          </CardContent>
        </Card>
      </div>



      <Card className="mt-8 shadow-sm">
        <CardHeader>
          <CardTitle>Contact & Links</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground space-y-4">
          <p>
            <strong> Westfälischen Hochschule Gelsenkirchen</strong>, Robotics Lab unter{" "}
            <strong>Prof. Surmann</strong>, im Rahmen des Forschungsprojekts{" "}
            <strong>E-DRZ</strong>.
          </p>

          <div className="flex flex-wrap items-center gap-3">
            <a
              href="https://www.youtube.com/user/RoblabFhGe"
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm hover:bg-accent"
              aria-label="YouTube channel"
            >
              <YoutubeIcon className="h-4 w-4" />
              YouTube
            </a>

            {/* <a
              href="https://instagram.com/roblabfhge" // TODO: replace with the correct Instagram profile if different
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm hover:bg-accent"
              aria-label="Instagram profile"
            >
              <Instagram className="h-4 w-4" />
              Instagram
            </a> */}

            <a
              href="https://github.com/RoblabWh/argus" // TODO: replace with your repo's Issues URL
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm hover:bg-accent"
              aria-label="GitHub"
            >
              <GithubIcon className="h-4 w-4" />
              GitHub
            </a>

            {/* <a
              href="mailto:argus@w-hs.de" // TODO: replace with your preferred contact email
              className="inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm hover:bg-accent"
              aria-label="Email contact"
            >
              <Mail className="h-4 w-4" />
              Email
            </a> */}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

const GithubIcon = ({
  size = 24,
  strokeWidth = 2,
  className,
  ...props
}) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 16 16"
    width={size}
    height={size}
    fill="currentColor"
    className={className}
    {...props}
  >
    <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8" />
  </svg>
)

const YoutubeIcon = ({
  size = 24,
  strokeWidth = 2,
  className,
  ...props
}) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 16 16"
    width={size}
    height={size}
    fill="currentColor"
    className={className}
    {...props}
  >
    <path d="M8.051 1.999h.089c.822.003 4.987.033 6.11.335a2.01 2.01 0 0 1 1.415 1.42c.101.38.172.883.22 1.402l.01.104.022.26.008.104c.065.914.073 1.77.074 1.957v.075c-.001.194-.01 1.108-.082 2.06l-.008.105-.009.104c-.05.572-.124 1.14-.235 1.558a2.01 2.01 0 0 1-1.415 1.42c-1.16.312-5.569.334-6.18.335h-.142c-.309 0-1.587-.006-2.927-.052l-.17-.006-.087-.004-.171-.007-.171-.007c-1.11-.049-2.167-.128-2.654-.26a2.01 2.01 0 0 1-1.415-1.419c-.111-.417-.185-.986-.235-1.558L.09 9.82l-.008-.104A31 31 0 0 1 0 7.68v-.123c.002-.215.01-.958.064-1.778l.007-.103.003-.052.008-.104.022-.26.01-.104c.048-.519.119-1.023.22-1.402a2.01 2.01 0 0 1 1.415-1.42c.487-.13 1.544-.21 2.654-.26l.17-.007.172-.006.086-.003.171-.007A100 100 0 0 1 7.858 2zM6.4 5.209v4.818l4.157-2.408z" />
  </svg>
)