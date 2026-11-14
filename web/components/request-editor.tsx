'use client';
import { useState } from 'react';
import { api, Item, Revision } from '../lib/api';
import { ErrorNote, ItemHeader, useAction } from './common';

type History = {revisions:Revision[]; next_cursor:string|null; decisions:{revision_id:string;review_cycle:number;decision:string;note:string|null;created_at:string}[]};

export function RequestEditor({path,item,readOnly,reload}: {path:string;item:Item;readOnly:boolean;reload:()=>Promise<void>}) {
  const [history,setHistory] = useState<History|null>(null);
  const action=useAction();
  const url=path+'/requests/'+item.id;
  const lock_version=item.lock_version;
  const editable=['submitted','changes_requested'].includes(item.status);
  function change(segment:string, method:string, body:object) {
    void action.run(async()=>{await api(url+segment,method,{...body,lock_version});await reload();});
  }
  async function loadHistory(cursor?:string) {
    const page=await api<History>(url+'/history?limit=100'+(cursor?'&cursor='+cursor:''));
    setHistory(previous=>cursor&&previous?{revisions:[...previous.revisions,...page.revisions],decisions:[...previous.decisions,...page.decisions],next_cursor:page.next_cursor}:page);
  }
  return <article className="card"><ItemHeader item={item}/><ErrorNote text={action.error}/>
    {action.error && <button onClick={()=>void action.run(reload)}>Refresh request</button>}
    {item.revision && <p className="muted mt-3 text-xs">Latest revision · v{item.revision.revision_no}</p>}
    {editable && !readOnly ? <form className="mt-2 grid gap-2" onSubmit={e=>{e.preventDefault();change('/revisions','POST',{body_text:new FormData(e.currentTarget).get('body')});}}>
      <label>Edit copy<textarea name="body" required maxLength={12000} defaultValue={item.revision?.body_text}/></label>
      <button disabled={action.pending} className="justify-self-start">Save revision</button></form> :
      item.revision && <pre className="mt-2 whitespace-pre-wrap break-words rounded-lg bg-[#f3f5ef] p-3 font-sans text-sm">{item.revision.body_text}</pre>}
    {!readOnly && <div className="my-3 flex flex-wrap gap-2">
      {editable && item.revision && <button disabled={action.pending} className="primary" onClick={()=>{if(confirm('Share the saved revision with the client? Unsaved edits will not be shared.'))change('/review','POST',{action:'share',revision_id:item.revision!.id});}}>Share saved version</button>}
      {item.status==='in_review' && <button disabled={action.pending} onClick={()=>change('/review','POST',{action:'withdraw'})}>Withdraw review</button>}
      {item.status==='approved' && <button disabled={action.pending} onClick={()=>{if(confirm('Reopen the approved request?'))change('/review','POST',{action:'reopen'});}}>Reopen request</button>}
    </div>}
    {!readOnly&&item.status!=='in_review'&&<details className="my-2">
      <summary className="cursor-pointer text-sm">Edit request or cancel</summary>
      <form className="my-2 grid gap-2" onSubmit={e=>{e.preventDefault();const fields=new FormData(e.currentTarget);
        change('','PATCH',{title:fields.get('title'),instructions:fields.get('instructions'),due_on:fields.get('date')||null});}}>
        <label>Title<input name="title" maxLength={120} required defaultValue={item.title}/></label>
        <label>Instructions<textarea name="instructions" maxLength={2000} required defaultValue={item.instructions}/></label>
        <label>Due date<input name="date" type="date" defaultValue={item.due_on||''}/></label><button disabled={action.pending}>Save request details</button></form>
      <button disabled={action.pending} onClick={()=>{if(confirm('Cancel this request? It will be hidden from the client.'))change('','PATCH',{cancel:true});}}>Cancel request</button>
    </details>}
    <button onClick={()=>history?setHistory(null):void action.run(()=>loadHistory())} disabled={action.pending}>{history?'Hide history':'View history'}</button>
    {history && <div className="mt-3 grid gap-2">
      {!history.revisions.length&&<p className="muted text-sm">No submitted versions.</p>}
      {history.revisions.slice().sort((a,b)=>b.revision_no-a.revision_no).map(v=><details key={v.id} className="rounded border border-[#d6ded6] p-2 text-sm">
        <summary className="cursor-pointer">Version {v.revision_no} · {v.source_role} · {new Date(v.created_at).toLocaleString()}</summary>
        <p className="mt-2 whitespace-pre-wrap break-words">{v.body_text}</p>
        {history.decisions.filter(d=>d.revision_id===v.id).map(d=><p key={d.review_cycle} className="mt-1 font-semibold">{d.decision==='approve'?'Approved':'Changes requested'} · {new Date(d.created_at).toLocaleString()}{d.note&&' · '+d.note}</p>)}
      </details>)}
      {history.next_cursor && <button disabled={action.pending} onClick={()=>void action.run(()=>loadHistory(history.next_cursor!))}>Load more history</button>}
    </div>}
  </article>;
}
