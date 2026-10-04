import test from 'node:test';
import assert from 'node:assert/strict';

async function client() {
  globalThis.document = {querySelector: () => ({content: 'old'})};
  globalThis.DOMParser = class { parseFromString() { return {querySelector: () => ({content: 'new'})}; } };
  return (await import(`./local-api.js?test=${Math.random()}`)).localFetch;
}

test('concurrent controls refresh once after restart and each action executes once', async () => {
  let pages = 0, executed = 0;
  globalThis.fetch = async (path, options) => {
    if (path === '/') { pages++; await new Promise(resolve => setTimeout(resolve, 5)); return {ok:true,text:async()=>'<html>'}; }
    if (options.headers['X-Helmetd'] === 'old') return {status:403};
    executed++; return {status:200};
  };
  const request = await client();
  const replies = await Promise.all([request('/api/hud'),request('/api/navigation')]);
  assert.deepEqual(replies.map(r=>r.status),[200,200]);
  assert.equal(pages,1); assert.equal(executed,2);
  await assert.rejects(request('https://example.com/api/'),/Local API/);
});

test('server failures are returned without replaying an action', async () => {
  let calls=0;
  globalThis.fetch=async()=>{calls++;return {status:500};};
  const request=await client();
  assert.equal((await request('/api/hud')).status,500);
  assert.equal(calls,1);
});
