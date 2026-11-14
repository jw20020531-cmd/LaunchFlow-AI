import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = { title: 'LaunchFlow AI', description: 'Website content requests and approvals for small agencies' };
export default function Layout({ children }: {children: React.ReactNode}) {
  return <html lang="en"><body>{children}</body></html>;
}
