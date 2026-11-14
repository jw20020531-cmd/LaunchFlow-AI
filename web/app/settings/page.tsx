'use client';
import { useEffect,useState } from 'react';
import { api,Space } from '../../lib/api';
import { ErrorNote,Frame,useAction } from '../../components/common';

export default function Settings() {
  const [space,setSpace]=useState<Space|null>(null);
  const [saved,setSaved]=useState(false);
  const action=useAction();
  useEffect(()=>{void action.run(async()=>setSpace(await api<Space>('/auth/me')));},[]);
  return <Frame><h1 className="mb-5 text-3xl">Workspace settings</h1><ErrorNote text={action.error}/>
    {space&&<form className="card mb-4 grid max-w-xl gap-3" onSubmit={e=>{
      e.preventDefault();const fields=new FormData(e.currentTarget);
      const external_ai_enabled=fields.get('ai')==='on';
      if(external_ai_enabled&&!space.external_ai_enabled&&!confirm('Allow sending project counts, request titles, states and dates to the configured model?'))return;
      void action.run(async()=>{setSpace(await api<Space>('/workspace','PATCH',{name:fields.get('name'),timezone:fields.get('timezone'),external_ai_enabled}));setSaved(true);});
    }}><label>Workspace name<input name="name" defaultValue={space.name} maxLength={120} required/></label>
      <label>Time zone<input name="timezone" defaultValue={space.timezone} placeholder="America/New_York" required maxLength={80}/></label>
      <label className="flex items-center gap-2"><input className="w-auto" name="ai" type="checkbox" defaultChecked={space.ai_available&&space.external_ai_enabled} disabled={!space.ai_available}/>Allow optional external AI drafts</label>
      {!space.ai_available&&<p className="muted text-sm">The server operator has not configured a model.</p>}
      <button className="primary" disabled={action.pending}>Save settings</button>{saved&&<p role="status">Settings saved.</p>}</form>}
    <form className="card mb-4 grid max-w-xl gap-3" onSubmit={e=>{
      e.preventDefault();const fields=new FormData(e.currentTarget);
      void action.run(async()=>{await api('/auth/password','POST',Object.fromEntries(fields));location.assign('/login');});
    }}><h2 className="text-lg">Change password</h2>
      <label>Current password<input name="current_password" type="password" autoComplete="current-password" required/></label>
      <label>New password<input name="new_password" type="password" autoComplete="new-password" required minLength={12} maxLength={256}/></label>
      <button disabled={action.pending}>Change password and sign out</button></form>
    <section className="card max-w-xl"><h2 className="text-lg">Workspace data</h2>
      <a href="/api/v1/workspace/export">Download JSON export</a><p className="muted mt-2 text-sm">Contact your server operator to request deletion.</p></section>
  </Frame>;
}
