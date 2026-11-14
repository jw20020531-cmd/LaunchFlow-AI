'use client';
import { api } from '../../lib/api';
import { ErrorNote, Frame, useAction } from '../../components/common';

export default function Login() {
  const action = useAction();
  return <Frame guest><div className="mx-auto mt-10 max-w-md card">
    <h1 className="text-2xl">Sign in to your workspace</h1>
    <p className="muted mb-5 mt-2 text-sm">Manage website content requests and client approvals.</p>
    <ErrorNote text={action.error}/>
    <form className="grid gap-4" onSubmit={e=>{e.preventDefault(); const fields=new FormData(e.currentTarget);
      void action.run(async()=>{await api('/auth/login','POST',Object.fromEntries(fields)); location.assign('/projects');}, false);
    }}>
      <label>Email<input required name="email" type="email" autoComplete="username"/></label>
      <label>Password<input required name="password" type="password" autoComplete="current-password"/></label>
      <button disabled={action.pending} className="primary">Sign in</button>
    </form>
  </div></Frame>;
}
