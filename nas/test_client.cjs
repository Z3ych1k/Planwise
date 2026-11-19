// Browser-free checks for the cache-first client with an unreachable or stalled NAS.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'static/ui.js'),'utf8');

function snapshot(version=1){
  return {api_version:1,user:{id:1,username:'demo',is_admin:false},version,saved_at:1,
    state:{language:'en',tasks:[{id:'task',title:'Cached essay',kind:'deadline',due:'2026-11-14',start:'',minutes:60,important:true,completed:false}],events:[],work_log:[],calendar:[],proposal:null,workdays:[0,1,2,3,4]},
    view:{today:'2026-11-12',cutoff:540,days:Array.from({length:7},(_,i)=>({date:`2026-11-${12+i}`,weekday:i%7,holiday:''})),ranks:{task:0},progress:{},available:[],occurrences:[],missing:[],preview:{same:[],removed:[],added:[]}}};
}
function boot(cache=snapshot(),query=''){
  const nodes=new Map(),timers=new Map(),calls=[],writes=[];let next=0,reply=null,replyStatus=200,hasReply=false;
  const node=()=>({innerHTML:'',hidden:true,textContent:'',disabled:false,classList:{toggle(){},add(){},remove(){}},append(){},prepend(){},remove(){},scrollIntoView(){}});
  for(const key of ['#app','#bubble','#notice','#content','#offline-banner','#connection','#login-form','#register-form','#login-language','#auth-switch'])nodes.set(key,node());
  const writeButton=node();
  const storage=new Map(cache===null?[]:[['planwise-nas-snapshot-v1',typeof cache==='string'?cache:JSON.stringify(cache)]]);
  const context=vm.createContext({console,FormData:class {constructor(form){return form;}},URLSearchParams,AbortController,structuredClone,Date,crypto:require('node:crypto').webcrypto,
    location:{search:query,origin:'http://nas.test:9473'},navigator:{userAgent:'PlanwiseNAS/0.3.0'},
    localStorage:{getItem:key=>storage.get(key)||null,setItem:(key,value)=>{storage.set(key,value);writes.push(key);},removeItem:key=>storage.delete(key)},
    document:{getElementById:()=>null,documentElement:{},body:{classList:{toggle(){}}},visibilityState:'visible',querySelector:key=>{
      if((key==='#login-form'||key==='#register-form')&&!nodes.get('#app').innerHTML.includes('id="'+key.slice(1)+'"'))return null;
      return nodes.get(key)||null;
    },querySelectorAll:selector=>selector.includes('[data-write]')?[writeButton]:[],createElement:node,addEventListener(){}},
    window:{addEventListener(){},isSecureContext:false,scrollTo(){}},history:{replaceState(){}},innerWidth:390,
    requestAnimationFrame:()=>{},setInterval:()=>1,
    setTimeout:(callback,delay)=>{const id=++next;timers.set(id,{callback,delay});return id;},clearTimeout:id=>timers.delete(id),
    fetch:(url,options)=>{calls.push({url,options});return hasReply?Promise.resolve({ok:replyStatus<400,status:replyStatus,json:async()=>{if(reply instanceof Error)throw reply;return reply;}}):new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(new Error('aborted'))));}
  });
  vm.runInContext(source+'\nglobalThis.client={api,sync,change,command,render,isOffline:()=>offline,current:()=>snap};',context);
  return {client:context.client,nodes,calls,writes,writeButton,
    respond:(data,status=200)=>{reply=data;replyStatus=status;hasReply=true;},advance:ms=>{for(const [id,timer] of timers)if(timer.delay<=ms){timers.delete(id);timer.callback();}},
    flush:()=>new Promise(resolve=>setImmediate(resolve)),timerDelays:()=>[...timers.values()].map(timer=>timer.delay)};
}

test('cold offline launch paints cached plan immediately, before any network result',async()=>{
  const app=boot();
  assert.match(app.nodes.get('#app').innerHTML,/Cached essay/);
  assert.match(app.nodes.get('#app').innerHTML,/Showing the last cached plan/);
  assert.equal(app.client.isOffline(),true);
  assert.equal(app.writeButton.disabled,true);
  assert.equal(app.calls.length,1);
  assert.deepEqual(app.writes,[]);
  assert.equal(await app.client.change('save',{title:'Offline attempt'}),false);
  assert.equal(app.calls.length,1);
});

test('stalled connection is aborted at eight seconds and keeps cached data visible',async()=>{
  const app=boot();
  assert.ok(app.timerDelays().includes(8000));
  app.advance(8000);await app.flush();
  assert.equal(app.calls[0].options.signal.aborted,true);
  assert.equal(app.client.isOffline(),true);
  assert.equal(app.client.current().state.tasks[0].title,'Cached essay');
  assert.equal(app.writeButton.disabled,true);
});

test('refresh reconnects, loads latest version, then enables editing',async()=>{
  const app=boot();app.advance(8000);await app.flush();
  const latest=snapshot(2);latest.csrf='online-session-token';app.respond(latest);
  await app.client.sync(true);
  assert.equal(app.client.current().version,2);
  assert.equal(app.client.isOffline(),false);
  assert.equal(app.writeButton.disabled,false);
  const saved=app.nodes.get('#app').innerHTML;
  assert.doesNotMatch(saved,/Showing the last cached plan/);
});

test('mobile defaults to all seven columns and retains explicit day view',async()=>{
  const app=boot(snapshot(),'?tab=schedule');
  assert.equal((app.nodes.get('#app').innerHTML.match(/class="day-head /g)||[]).length,7);
  assert.match(app.nodes.get('#app').innerHTML,/week-view/);
  await app.client.command('span-day');
  assert.equal((app.nodes.get('#app').innerHTML.match(/class="day-head /g)||[]).length,1);
  await app.client.command('span-week');
  assert.equal((app.nodes.get('#app').innerHTML.match(/class="day-head /g)||[]).length,7);
});

test('first use without cache shows sign-in immediately and a retry after timeout',async()=>{
  const app=boot(null);
  assert.match(app.nodes.get('#app').innerHTML,/login-form/);
  app.advance(8000);await app.flush();
  assert.match(app.nodes.get('#app').innerHTML,/retry-connect/);
  assert.match(app.nodes.get('#app').innerHTML,/首次登入需要連線/);
});

test('invalid cache cannot turn a cold launch into an empty page',()=>{
  for(const broken of ['{bad json','{"api_version":1,"user":{},"view":{},"state":{"tasks":2}}']){
    const app=boot(broken);assert.match(app.nodes.get('#app').innerHTML,/login-form/);
  }
});

test('sign-in offers invite-only registration with password confirmation',()=>{
  const app=boot(null);
  assert.match(app.nodes.get('#app').innerHTML,/以邀請碼建立帳號/);
  app.nodes.get('#auth-switch').onclick();
  const html=app.nodes.get('#app').innerHTML;
  assert.match(html,/name="invite_code"/);
  assert.match(html,/name="password_confirm"/);
  assert.doesNotMatch(html,/name="is_admin"/);
});

test('fresh local setup omits invitations and submits to the local setup endpoint',async()=>{
  const app=boot(null);app.advance(8000);await app.flush();
  app.respond({code:'setup_required',error:'Create your first local account.'},401);
  await app.client.sync(true);
  const html=app.nodes.get('#app').innerHTML;
  assert.match(html,/建立本機帳號/);
  assert.match(html,/name="password_confirm"/);
  assert.doesNotMatch(html,/name="invite_code"/);
  app.respond(snapshot());
  const password='Temporary-test-password';
  const form=app.nodes.get('#register-form');
  await form.onsubmit({preventDefault(){},target:[['username','first-user'],
    ['password',password],['password_confirm',password]]});
  assert.deepEqual(app.calls.slice(-2).map(({url})=>url),['/api/setup','/api/state']);
  assert.equal(JSON.parse(app.calls.at(-2).options.body).username,'first-user');
  assert.match(app.nodes.get('#app').innerHTML,/Cached essay/);
});

test('regular settings keep personal preferences and hide administrator management',()=>{
  const member=boot(snapshot(),'?tab=settings');
  assert.match(member.nodes.get('#app').innerHTML,/prefs-form/);
  assert.match(member.nodes.get('#app').innerHTML,/password-form/);
  assert.doesNotMatch(member.nodes.get('#app').innerHTML,/invite-panel/);
  const admin=snapshot();admin.user.is_admin=true;admin.invitations=[];
  const owner=boot(admin,'?tab=settings');
  assert.match(owner.nodes.get('#app').innerHTML,/invite-panel/);
  assert.match(owner.nodes.get('#app').innerHTML,/Generate invitation/);
});

test('unauthenticated polling preserves the registration form instead of replacing typed fields',async()=>{
  const app=boot(null);app.advance(8000);await app.flush();
  app.nodes.get('#auth-switch').onclick();
  app.nodes.get('#app').innerHTML+='<!-- existing typed form -->';
  const before=app.nodes.get('#app').innerHTML;
  app.respond({code:'unauthorized',error:'Please sign in again.'},401);
  await app.client.sync();
  assert.equal(app.nodes.get('#app').innerHTML,before);
});

test('invitation usage refreshes even when the administrator plan version is unchanged',async()=>{
  const initial=snapshot();initial.user.is_admin=true;
  initial.invitations=[{id:1,status:'pending',expires_at:1900000000}];
  const app=boot(initial,'?tab=settings');app.advance(8000);await app.flush();
  app.respond(initial);await app.client.sync(true);
  const latest=structuredClone(initial);latest.invitations[0].status='used';latest.invitations[0].used_by='newmember';
  app.respond(latest);await app.client.sync();
  assert.match(app.nodes.get('#app').innerHTML,/#1 · Used/);
  assert.match(app.nodes.get('#app').innerHTML,/newmember/);
});


test('HTML server errors keep their HTTP status and show a readable error',async()=>{
  const app=boot();app.advance(8000);await app.flush();
  app.respond(new SyntaxError('Unexpected token <'),503);
  await assert.rejects(app.client.api('/api/state'),error=>{
    assert.equal(error.status,503);assert.equal(error.code,'invalid_response');
    assert.match(error.message,/invalid response/);assert.doesNotMatch(error.message,/Unexpected token/);return true;
  });
});

test('invalid success JSON cannot be mistaken for a confirmed save',async()=>{
  const app=boot();app.advance(8000);await app.flush();
  for(const value of [new SyntaxError('bad json'),'text',[],null]){
    app.respond(value,200);
    await assert.rejects(app.client.api('/api/actions',{}),error=>error.code==='invalid_response'&&!error.status);
  }
});

test('a failed save preserves plan and input and releases buttons for retry',async()=>{
  const app=boot();app.advance(8000);await app.flush();
  app.respond(snapshot());await app.client.sync(true);
  const before=JSON.stringify(app.client.current());
  app.nodes.get('#bubble').innerHTML='typed input retained';
  app.respond({error:'Invalid date',code:'invalid'},400);
  assert.equal(await app.client.change('save',{due:'2026-02-30'}),false);
  assert.equal(JSON.stringify(app.client.current()),before);
  assert.equal(app.nodes.get('#bubble').innerHTML,'typed input retained');
  assert.equal(app.writeButton.disabled,false);
  app.respond(snapshot(2));
  assert.equal(await app.client.change('save_policy',{}),true);
  assert.equal(app.client.current().version,2);
});

test('an unreadable save response keeps old data and requires reconnection',async()=>{
  const app=boot();app.advance(8000);await app.flush();
  app.respond(snapshot());await app.client.sync(true);
  app.respond(new SyntaxError('bad json'),200);
  assert.equal(await app.client.change('save_policy',{}),false);
  assert.equal(app.client.current().version,1);
  assert.equal(app.client.isOffline(),true);
  assert.equal(app.writeButton.disabled,true);
});
