'use client';
import { use, useEffect, useState } from 'react';
import Link from 'next/link';
import { api, all, Item, Project, Space } from '../../../lib/api';
import { ErrorNote, Frame, Readiness, useAction } from '../../../components/common';
import { RequestEditor } from '../../../components/request-editor';
import { StatusComposer } from '../../../components/status-composer';

export default function ProjectPage({params}: {params:Promise<{id:string}>}) {
  const {id} = use(params);
  const path = '/projects/'+id;
  const [project,setProject] = useState<Project|null>(null);
  const [items,setItems] = useState<Item[]>([]);
  const [space,setSpace] = useState<Space|null>(null);
  const [share,setShare] = useState<{url:string;expires_at:string}|null>(null);
  const [notice,setNotice] = useState('');
  const action=useAction();
  async function reload() {
    const [p,requests,w] = await Promise.all([api<Project>(path),all<Item>(path+'/requests'),api<Space>('/auth/me')]);
    setProject(p);setItems(requests);setSpace(w);
  }
  useEffect(()=>{void action.run(reload);},[path]);
  return <Frame><Link href="/projects" className="text-sm">All projects</Link>
    <ErrorNote text={action.error}/>
    {!project ? <p className="mt-4">Loading project…</p> : <>
    <div className="my-5 flex flex-wrap items-start justify-between gap-3"><div>
      <h1 className="text-3xl">{project.title}</h1>
      <p className="muted my-2 text-sm">{project.archived_at ? 'Archived project' : project.target_launch_on ? 'Launch target '+project.target_launch_on : 'Content checklist'}</p><Readiness value={project}/></div>
      <button disabled={action.pending} onClick={()=>void action.run(reload)}>Refresh project</button></div>
    {!project.archived_at && <section className="card mb-5">
      <h2 className="mb-2 text-lg">Client access</h2>
      <p className="muted mb-3 text-sm">Anyone with the active link can review this project. A new link replaces the old one and expires in 14 days.</p>
      <div className="flex flex-wrap gap-2"><button className="primary" disabled={action.pending} onClick={()=>void action.run(async()=>{
        setShare(await api(path+'/link','POST'));setNotice('New client link created.');
      })}>Create or rotate link</button><button disabled={action.pending} onClick={()=>{if(confirm('Revoke all client access to this project?'))void action.run(async()=>{
        await api(path+'/link','DELETE');setShare(null);setNotice('Client access revoked.');
      });}}>Revoke link</button></div>
      {share && <label className="mt-3">Client link<input readOnly value={share.url} onFocus={e=>e.currentTarget.select()}/><span className="muted">Expires {new Date(share.expires_at).toLocaleString()}</span></label>}
      {notice && <p className="muted mt-2 text-sm" role="status">{notice}</p>}
    </section>}
    <div className="grid items-start gap-5 lg:grid-cols-[2fr_1fr]"><div className="grid gap-3">
      {!project.archived_at && <form className="card grid gap-3" onSubmit={e=>{
        e.preventDefault();const form=e.currentTarget;const fields=new FormData(form);
        void action.run(async()=>{await api(path+'/requests','POST',{title:fields.get('title'),instructions:fields.get('instructions'),due_on:fields.get('due_on')||null});form.reset();await reload();});
      }}><h2 className="text-lg">Add a content request</h2>
        <label>Page or item title<input name="title" required maxLength={120} placeholder="Homepage headline"/></label>
        <label>Client instructions<textarea name="instructions" required maxLength={2000} placeholder="What should your client provide?"/></label>
        <label>Due date<input name="due_on" type="date"/></label><button className="primary justify-self-start" disabled={action.pending}>Add request</button></form>}
      {!items.length && <p className="card muted">No content requests yet.</p>}
      {items.map(item=><RequestEditor key={item.id+':'+item.lock_version} path={path} item={item} readOnly={Boolean(project.archived_at||item.cancelled_at)} reload={reload}/>)}
    </div><aside className="grid gap-3"><StatusComposer path={path} canUseAI={Boolean(space?.external_ai_enabled&&space.ai_available)} items={items}/>
    {!project.archived_at && <details className="card"><summary className="cursor-pointer text-sm font-semibold">Project settings</summary>
      <form className="my-3 grid gap-2" onSubmit={e=>{e.preventDefault();const fields=new FormData(e.currentTarget);
        void action.run(async()=>{await api(path,'PATCH',{title:fields.get('title'),target_launch_on:fields.get('date')||null});await reload();});
      }}><label>Project title<input name="title" required maxLength={120} defaultValue={project.title}/></label>
      <label>Target date<input name="date" type="date" defaultValue={project.target_launch_on||''}/></label><button disabled={action.pending}>Save project</button></form>
      <button disabled={action.pending} onClick={()=>{if(confirm('Archive this project and revoke its client link?'))void action.run(async()=>{await api(path,'PATCH',{archive:true});setShare(null);await reload();});}}>Archive project</button>
    </details>}</aside></div></>}
  </Frame>;
}
