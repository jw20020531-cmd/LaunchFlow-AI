from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import select
from app.db import Session, engine
from app.models import Link, User, Workspace, now
from .conftest import PASSWORD

ROOT = "/api/v1"

def call(client, method, path, body=None, expected=200):
    args = {} if body is None else {"json": body}
    response = client.request(method, ROOT+path, **args)
    assert response.status_code == expected, response.text
    return response.json() if response.content else None

def owner(browser, account):
    email = f"{uuid4()}@example.test"
    tenant = account(email)
    client = browser()
    call(client, "POST", "/auth/login", {"email":email,"password":PASSWORD})
    return client, tenant

def setup(client, title="Website refresh"):
    project = call(client,"POST","/projects",{"title":title},201)
    path = f"/projects/{project['id']}"
    assert not project["ready"]
    item = call(client,"POST",path+"/requests",{"title":"Homepage","instructions":"Paste approved copy.","due_on":"2000-01-01"},201)
    assert item["overdue"]
    return path, item

def issue(client, path):
    return call(client,"POST",path+"/link",expected=201)["url"].split("#token=")[1]

def guest(browser, token):
    client = browser()
    call(client,"POST","/guest/exchange",{"token":token})
    assert not client.cookies.get("lf_owner")
    return client

def share(owner_client, path, item, guest_client):
    guest_path = "/guest/requests/"+item["id"]
    submitted = call(guest_client,"POST",guest_path+"/submit",{"body_text":"Client copy", "lock_version":item["lock_version"]},201)
    request = path+"/requests/"+item["id"]
    saved = call(owner_client,"POST",request+"/revisions",{"body_text":"Agency edited copy", "lock_version":submitted["lock_version"]},201)
    before = call(guest_client,"GET","/guest/requests")["items"][0]
    assert before["revision"]["body_text"] == "Client copy"
    review = call(owner_client,"POST",request+"/review",{"action":"share","revision_id":saved["revision"]["id"],"lock_version":saved["request"]["lock_version"]})
    visible = call(guest_client,"GET","/guest/requests")["items"][0]
    assert visible["revision"]["body_text"] == "Agency edited copy"
    return request, guest_path, review

def test_review_audit_and_reopen(browser, account):
    agency, _ = owner(browser, account)
    path, item = setup(agency)
    client = guest(browser, issue(agency,path))
    request, guest_path, review = share(agency,path,item,client)
    payload = {"revision_id":review["shared_revision_id"],"lock_version":review["lock_version"],"decision":"request_changes"}
    call(client,"POST",guest_path+"/decision",payload,422)
    change = call(client,"POST",guest_path+"/decision",{**payload,"note":"Update the title"},201)
    call(client,"POST",guest_path+"/decision",payload,409)
    assert not call(agency,"GET",path)["ready"]
    saved = call(agency,"POST",request+"/revisions",{"body_text":"Updated title","lock_version":change["lock_version"]},201)
    review2 = call(agency,"POST",request+"/review",{"action":"share","revision_id":saved["revision"]["id"],"lock_version":saved["request"]["lock_version"]})
    decision = {"revision_id":review2["shared_revision_id"],"lock_version":review2["lock_version"],"decision":"approve"}
    call(client,"POST",guest_path+"/decision",{**decision,"revision_id":review["shared_revision_id"]},409)
    approved = call(client,"POST",guest_path+"/decision",decision,201)
    assert call(agency,"GET",path)["ready"]
    call(agency,"POST",request+"/review",{"action":"reopen","lock_version":approved["lock_version"]})
    history = call(agency,"GET",request+"/history")
    assert {x["decision"] for x in history["decisions"]} == {"approve","request_changes"}
    export = call(agency,"GET","/workspace/export")
    assert len(export["projects"][0]["requests"][0]["revisions"]) == 3
    assert "token_hash" not in str(export)

def test_isolation_and_revocation(browser, account):
    first,_ = owner(browser,account)
    second, _ = owner(browser,account)
    p,i = setup(first)
    p2,i2 = setup(second,"Another tenant")
    same, same_item = setup(first,"Another project")
    token=issue(first,p)
    client=guest(browser,token)
    call(second,"GET",p,expected=404)
    call(second,"GET",p+"/requests/"+i["id"]+"/history",expected=404)
    call(first,"POST",p2+"/link",expected=404)
    call(client,"GET",p,expected=401)
    for other in [i2,same_item]:
        call(client,"POST","/guest/requests/"+other["id"]+"/submit",{"body_text":"No","lock_version":0},404)
    token2=issue(first,p)
    call(client,"GET","/guest/project",expected=401)
    call(browser(),"POST","/guest/exchange",{"token":token},404)
    client2=guest(browser,token2)
    call(first,"PATCH",p,{"archive":True})
    call(client2,"GET","/guest/project",expected=401)
    assert len(call(first,"GET","/projects?archived=true")["items"])==1
    assert "Another tenant" not in str(call(first,"GET","/workspace/export"))

def test_expiry_and_delete(browser,account):
    agency,tenant=owner(browser,account)
    path,item=setup(agency)
    token=issue(agency,path)
    client=guest(browser,token)
    share(agency,path,item,client)
    with Session.begin() as db:
        db.scalar(select(Link).where(Link.workspace_id==tenant)).expires_at=now()
    call(client,"GET","/guest/project",expected=401)
    with Session.begin() as db:
        db.delete(db.get(Workspace,tenant))
    call(agency,"GET",path,expected=401)

def test_origin_body_and_password(browser, account):
    agency,_=owner(browser,account)
    assert agency.post(ROOT+"/projects",headers={"Origin":"https://untrusted.example"},json={"title":"x"}).status_code==403
    assert agency.post(ROOT+"/projects",json={"title":"x"*70000}).status_code==413
    call(agency,"POST","/projects",{"title":"Example","workspace_id":"unknown"},422)
    call(agency,"POST","/auth/password",{"current_password":"bad","new_password":"test-only-new-password"},401)
    call(agency,"POST","/auth/password",{"current_password":PASSWORD,"new_password":"test-only-new-password"},204)
    call(agency,"GET","/auth/me",expected=401)

def test_ai_is_opt_in_and_minimized(browser,account,monkeypatch):
    agency,_=owner(browser,account)
    path,item=setup(agency)
    client=guest(browser,issue(agency,path))
    share(agency,path,item,client)
    class Fake:
        def draft(self,snapshot):
            assert set(snapshot)=={"counts","items"}
            assert set(snapshot["items"][0])=={"title","status","due_on"}
            assert "Agency edited copy" not in str(snapshot)
            return "Review is pending."
    from app import ai
    monkeypatch.setattr(ai,"configured_provider",lambda:Fake())
    call(agency,"POST",path+"/status-drafts",{"mode":"ai","confirmed":True},503)
    assert "Homepage" in call(agency,"POST",path+"/status-drafts",{"mode":"manual"})["text"]
    call(agency,"PATCH","/workspace",{"external_ai_enabled":True})
    call(agency,"POST",path+"/status-drafts",{"mode":"ai"},422)
    preview=call(agency,"POST",path+"/status-drafts",{"mode":"preview"})
    call(agency,"POST",path+"/status-drafts",{"mode":"ai","confirmed":True,"snapshot_digest":"0"*64},409)
    result=call(agency,"POST",path+"/status-drafts",{"mode":"ai","confirmed":True,"snapshot_digest":preview["snapshot_digest"]})
    assert result["text"]=="Review is pending."
    assert not call(agency,"GET",path)["ready"]

@pytest.mark.skipif(engine.dialect.name != "postgresql", reason="Requires PostgreSQL row locking")
def test_concurrent_approval(browser,account):
    agency,_=owner(browser,account)
    path,item=setup(agency)
    token=issue(agency,path)
    first,second=guest(browser,token),guest(browser,token)
    _,guest_path,review=share(agency,path,item,first)
    payload={"revision_id":review["shared_revision_id"],"lock_version":review["lock_version"],"decision":"approve"}
    with ThreadPoolExecutor(2) as pool:
        statuses=list(pool.map(lambda c:c.post(ROOT+guest_path+"/decision",json=payload).status_code,[first,second]))
    assert sorted(statuses)==[201,409]
