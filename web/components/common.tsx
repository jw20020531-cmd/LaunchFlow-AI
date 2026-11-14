'use client';
import Link from 'next/link';
import { useState } from 'react';
import { ApiError, api, Counts, Item } from '../lib/api';

export function useAction() {
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);
  async function run(task: () => Promise<void>, redirect = true) {
    setError(''); setPending(true);
    try { await task(); }
    catch (e) {
      if (redirect && e instanceof ApiError && e.status === 401) location.assign('/login');
      else setError(e instanceof Error ? e.message : 'Something went wrong.');
    } finally { setPending(false); }
  }
  return {error, pending, run};
}
export function ErrorNote({text}: {text:string}) {
  return text ? <p className="error mb-4" role="alert">{text}</p> : null;
}
export function Frame({children, guest = false}: {children: React.ReactNode; guest?: boolean}) {
  return <><header className="border-b border-[#d6ded6] bg-white"><div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-4 px-4 py-4">
    <span className="font-bold tracking-tight">LaunchFlow <span className="text-[#2b7962]">AI</span></span>
    {!guest && <nav aria-label="Workspace" className="flex items-center gap-4 text-sm"><Link href="/projects">Projects</Link><Link href="/settings">Settings</Link><button onClick={async()=>{try {await api('/auth/logout','POST',{scope:'owner'}); location.assign('/login');} catch {alert('Could not sign out. Try again.');}}}>Sign out</button></nav>}
  </div></header><main className="mx-auto max-w-5xl px-4 py-8">{children}</main></>;
}
export function Readiness({value}: {value:Counts}) {
  return <div className="flex flex-wrap gap-2"><span className="badge">{value.approved} / {value.total} approved</span>
    <span className="badge">{value.overdue} overdue</span>{value.ready && <span className="badge">Content ready</span>}</div>;
}
export function ItemHeader({item}: {item:Item}) {
  return <><div className="flex flex-wrap items-center justify-between gap-2"><h2 className="text-lg">{item.title}</h2><span className="badge">{item.cancelled_at ? 'Cancelled' : item.status.replaceAll('_',' ')}</span></div>
    <p className="mt-2 whitespace-pre-wrap break-words text-sm">{item.instructions}</p>
    {item.due_on && <p className="muted mt-1 text-sm">Due {item.due_on}{item.overdue && ' · Overdue'}</p>}</>;
}
