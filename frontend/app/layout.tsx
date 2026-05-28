import type { Metadata, Viewport } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Base Navigator',
  description: 'Calm ecosystem intelligence for Base.'
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  themeColor: '#070b12'
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
