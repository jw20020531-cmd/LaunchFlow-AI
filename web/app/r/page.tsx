'use client';
import { useEffect, useRef } from 'react';
import { api } from '../../lib/api';
import { ErrorNote, Frame, useAction } from '../../components/common';

export default function LinkLanding() {
  const action=useAction();
  const started=useRef(false);
  useEffect(()=>{
    if(started.current)return;
    started.current=true;
    const token=new URLSearchParams(location.hash.slice(1)).get('token');
    history.replaceState(null,'',location.pathname);
    void action.run(async()=>{if(!token)throw new Error('This review link is unavailable.');
      try { await api('/guest/exchange','POST',{token}); } catch { throw new Error('This review link is unavailable.'); }
      location.replace('/client');
    },false);
  },[]);
  return <Frame guest><section className="card mx-auto max-w-md"><h1 className="text-xl">Client review</h1>
    <p className="muted my-2 text-sm">{action.error?'Ask your agency for a fresh link.':'Opening your project…'}</p><ErrorNote text={action.error}/></section></Frame>;
}
