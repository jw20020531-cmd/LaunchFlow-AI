'use client';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { api, all, Project } from '../../lib/api';
import { ErrorNote, Frame, Readiness, useAction } from '../../components/common';

export default function Projects() {
  const [projects,setProjects] = useState<Project[]|null>(null);
  const [archived,setArchived] = useState(false);
  const action = useAction();
  useEffect(()=>{
    let active = true;
    void action.run(async()=>{const rows=await all<Project>('/projects?archived='+archived); if(active)setProjects(rows);});
    return ()=>{active=false;};
  },[archived]);
  return <Frame><h1 className="text-3xl">Website projects</h1>
    <p className="muted mb-6 mt-1">Track client content from request through sign-off.</p>
    <ErrorNote text={action.error}/>
    <form className="card mb-6 grid gap-3 sm:grid-cols-[1fr_180px_auto] sm:items-end" onSubmit={e=>{
      e.preventDefault();const fields=new FormData(e.currentTarget);
      void action.run(async()=>{const p=await api<Project>('/projects','POST',{title:fields.get('title'),target_launch_on:fields.get('date')||null});location.assign('/projects/'+p.id);});
    }}><label>Project name<input name="title" required maxLength={120} placeholder="Example website refresh"/></label>
      <label>Target launch date<input name="date" type="date"/></label><button className="primary" disabled={action.pending}>Create project</button></form>
    <div className="mb-3 flex gap-2"><button aria-pressed={!archived} onClick={()=>{if(archived){setProjects(null);setArchived(false);}}}>Active</button>
      <button aria-pressed={archived} onClick={()=>{if(!archived){setProjects(null);setArchived(true);}}}>Archived</button></div>
    {projects===null ? <p>Loading projects…</p> : !projects.length ? <p className="card muted">{archived?'No archived projects.':'Create your first project to request content.'}</p> :
      <div className="grid gap-3 sm:grid-cols-2">{projects.map(p=><article key={p.id} className="card"><h2 className="mb-2 text-xl"><Link href={'/projects/'+p.id}>{p.title}</Link></h2>
        <Readiness value={p}/>{p.target_launch_on && <p className="muted mt-2 text-sm">Launch target {p.target_launch_on}</p>}</article>)}</div>}
  </Frame>;
}
