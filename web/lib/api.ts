export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}
export async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const result = await fetch('/api/v1' + path, {
    method, cache: 'no-store',
    ...(body === undefined ? {} : { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  });
  if (!result.ok) {
    const data = await result.json().catch(() => null);
    throw new ApiError(result.status, data?.error?.message ?? 'Request failed. Refresh and try again.');
  }
  return result.status === 204 ? undefined as T : result.json();
}

export type List<T> = {items: T[]; next_cursor: string | null};
export async function all<T>(path: string): Promise<T[]> {
  const records: T[] = [];
  let cursor: string | null = null;
  do {
    const query: string = (path.includes('?') ? '&' : '?') + 'limit=100' + (cursor ? '&cursor=' + encodeURIComponent(cursor) : '');
    const page: List<T> = await api<List<T>>(path + query);
    records.push(...page.items);
    cursor = page.next_cursor;
  } while (cursor);
  return records;
}

export type Space = {name:string; timezone:string; external_ai_enabled:boolean; ai_available:boolean};
export type Counts = {total:number; approved:number; overdue:number; ready:boolean};
export type Project = Counts & {id:string; title:string; target_launch_on:string|null; archived_at:string|null};
export type Revision = {id:string; revision_no:number; body_text:string; source_role:string; created_at:string};
export type Item = {id:string; title:string; instructions:string; due_on:string|null; overdue:boolean;
  status:string; lock_version:number; revision:Revision|null; shared_revision_id:string|null; cancelled_at?:string|null};
