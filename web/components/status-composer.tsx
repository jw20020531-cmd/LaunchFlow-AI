'use client';
import { useState } from 'react';
import { api, Item } from '../lib/api';
import { ErrorNote, useAction } from './common';

export function StatusComposer({path,canUseAI,items}: {path:string;canUseAI:boolean;items:Item[]}) {
  const [text,setText] = useState('');
  const [snapshot,setSnapshot] = useState('');
  const [key,setKey] = useState('');
  const [consent,setConsent] = useState(false);
  const [reviewed,setReviewed] = useState(false);
  const [copied,setCopied] = useState(false);
  const [preview,setPreview] = useState<{snapshot_digest:string;snapshot:{counts:{total:number;approved:number;overdue:number};items:{title:string;status:string;due_on:string|null}[]}}|null>(null);
  const action=useAction();
  const stateKey=items.map(i=>i.id+':'+i.lock_version).join(',');
  const stale=Boolean(snapshot)&&key!==stateKey;
  function generate(mode:'manual'|'ai') {
    void action.run(async()=>{
      const value=await api<{text:string;snapshot_at:string}>(path+'/status-drafts','POST',{mode,confirmed:consent,snapshot_digest:mode==='ai'?preview?.snapshot_digest:null});
      setText(value.text);setSnapshot(value.snapshot_at);setKey(stateKey);setReviewed(false);setCopied(false);setConsent(false);
    });
  }
  return <section className="card grid gap-3"><h2 className="text-lg">Status note</h2>
    <p className="muted text-sm">Prepare a note to share through your usual channel.</p>
    <ErrorNote text={action.error}/>
    <button disabled={action.pending} onClick={()=>generate('manual')}>Draft from checklist</button>
    {canUseAI && <details className="text-sm"><summary className="cursor-pointer font-semibold">Optional AI draft</summary>
      <p className="muted mt-2">The model receives project counts and the request titles, states and dates listed below.</p>
      <button className="my-2" disabled={action.pending} onClick={()=>void action.run(async()=>{setConsent(false);setPreview(await api(path+'/status-drafts','POST',{mode:'preview'}));})}>Load fields for review</button>
      {preview && <><p className="muted text-sm">{preview.snapshot.counts.approved} of {preview.snapshot.counts.total} approved · {preview.snapshot.counts.overdue} overdue</p>
      <ul className="my-2 max-h-36 overflow-auto">{preview.snapshot.items.map((i,index)=><li key={index}>{i.title} · {i.status} · {i.due_on||'No date'}</li>)}</ul>
      <label className="mb-2 flex items-start gap-2"><input className="mt-1 w-auto" type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)}/>These titles contain no confidential names and may be sent to the model.</label>
      <button disabled={!consent||action.pending} onClick={()=>generate('ai')}>Draft with AI</button></>}
    </details>}
    {snapshot && <><p className="muted text-xs">Snapshot {new Date(snapshot).toLocaleString()}</p>
      {stale&&<p className="error text-sm">Checklist changed. Generate a fresh draft.</p>}
      <label>Draft text<textarea rows={7} value={text} onChange={e=>{setText(e.target.value);setReviewed(false);setCopied(false);}}/></label>
      <label className="flex items-center gap-2"><input className="w-auto" type="checkbox" checked={reviewed} onChange={e=>setReviewed(e.target.checked)}/>I reviewed this draft</label>
      <button disabled={!reviewed||!text.trim()||stale||action.pending} onClick={()=>void action.run(async()=>{await navigator.clipboard.writeText(text);setCopied(true);})}>Copy note</button>
      {copied&&<p role="status" className="muted text-sm">Copied.</p>}</>}
  </section>;
}
