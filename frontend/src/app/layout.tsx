import type { Metadata } from 'next';
import { Inter, Manrope } from 'next/font/google';
import './globals.css';
import { AuthProvider } from '../contexts/AuthContext';
import { ThemeProvider } from '../contexts/ThemeContext';

const manrope = Manrope({
  subsets: ['latin'],
  variable: '--font-manrope',
  display: 'swap',
});

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'CELTM',
  description: 'Premium SaaS Analytics Interface',
  icons: {
    icon: [
      { url: '/favicon.ico', sizes: 'any' },
      { url: '/celtm-logo-cropped.png', type: 'image/png' },
    ],
    shortcut: '/favicon.ico',
    apple: '/celtm-logo-cropped.png',
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning data-scroll-behavior="smooth" className={`light ${manrope.variable} ${inter.variable}`}>
      <body
        suppressHydrationWarning
        className="bg-surface text-on-surface selection:bg-primary-container selection:text-on-primary-container min-h-screen font-['Manrope'] transition-colors duration-300 ease-in-out"
      >
        <ThemeProvider>
          <AuthProvider>{children}</AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
