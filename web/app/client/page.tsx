'use client';
import { useEffect,useState } from 'react';
import { api,all,Counts,Item } from '../../lib/api';
import { ErrorNote,Frame,ItemHeader,Readiness,useAction } from '../../components/common';

export default function ClientReview() {
  const [project,setProject] = useState<(Counts&{title:string})|null>(null);
  const [items,setItems] = useState<Item[]>([]);
  const action=useAction();
  async function reload() {
    const [p,requests]=await Promise.all([api<Counts&{title:string}>('/guest/project'),all<Item>('/guest/requests')]);
    setProject(p);setItems(requests);
  }
  useEffect(()=>{void action.run(reload,false);},[]);
  return <Frame guest>
    <h1 className="text-3xl">{project?.title||'Client review'}</h1>
    <ErrorNote text={action.error}/>
    {project ? <><div className="my-4 flex flex-wrap justify-between gap-2"><Readiness value={project}/>
      <button disabled={action.pending} onClick={()=>void action.run(reload,false)}>Refresh project</button></div>
      {!items.length && <p className="card muted">Your agency has not added any requests yet.</p>}
      <div className="grid gap-3">{items.map(item=><GuestItem key={item.id+':'+item.lock_version} item={item} reload={reload}/>)}</div></> :
    <p className="muted mt-4">{action.error?'Ask your agency for a fresh link.':'Loading project…'}</p>}
  </Frame>;
}
function GuestItem({item,reload}: {item:Item;reload:()=>Promise<void>}) {
  const action=useAction();
  const base='/guest/requests/'+item.id;
  const initial=item.revision?.source_role==='guest'?item.revision.body_text:'';
  return <article className="card"><ItemHeader item={item}/><ErrorNote text={action.error}/>
    {item.status==='in_review'&&item.revision&&<form className="mt-3 grid gap-2" onSubmit={e=>{
      e.preventDefault();const submitter=(e.nativeEvent as SubmitEvent).submitter as HTMLButtonElement;
      const decision=submitter?.value;if(!decision)return;
      const note=new FormData(e.currentTarget).get('note');
      void action.run(async()=>{await api(base+'/decision','POST',{decision,note,revision_id:item.revision!.id,lock_version:item.lock_version});await reload();},false);
    }}>
      <p className="muted text-sm">Review version {item.revision.revision_no}</p>
      <p className="whitespace-pre-wrap break-words rounded bg-[#f3f5ef] p-3">{item.revision.body_text}</p>
      <label>Review note (required for changes)<textarea name="note" maxLength={2000}/></label>
      <div className="flex flex-wrap gap-2"><button className="primary" value="approve" disabled={action.pending}>Approve version</button>
        <button value="request_changes" disabled={action.pending}>Request changes</button></div>
    </form>}
    {item.status==='approved'&&item.revision&&<div className="mt-3"><p className="muted text-sm">Approved version {item.revision.revision_no}</p><p className="whitespace-pre-wrap break-words">{item.revision.body_text}</p></div>}
    {['awaiting_input','submitted','changes_requested'].includes(item.status)&&<form className="mt-3 grid gap-2" onSubmit={e=>{
      e.preventDefault();const body_text=new FormData(e.currentTarget).get('copy');
      void action.run(async()=>{await api(base+'/submit','POST',{body_text,lock_version:item.lock_version});await reload();},false);
    }}><label>Website copy or reference URL<textarea name="copy" required maxLength={12000} defaultValue={initial}/></label>
      <button className="primary justify-self-start" disabled={action.pending}>Submit content</button></form>}
    {action.error&&<button className="mt-2" onClick={()=>void action.run(reload,false)}>Refresh request</button>}
  </article>;
}
