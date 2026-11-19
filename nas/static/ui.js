'use strict';
// The same static client runs in a browser, the NAS APK and a read-only snapshot.
const TEXT={
  map:['任務地圖','任务地图'],schedule:['時間行程','时间行程'],settings:['事項與設定','事项与设置'],
  room:['給接下來的自己，留一點空間。','给接下来的自己，留一点空间。'],
  intro:['先放好課程與私人時間，再從容安排 DDL。','先放好课程与私人时间，再从容安排 DDL。'],
  online:['已連接 NAS','已连接 NAS'],offline:['離線 · 僅供查看','离线 · 仅供查看'],refresh:['重新整理','刷新'],
  readOnly:['目前顯示最近一次快取，離線不能修改；重新連線後會先取得最新資料。','目前显示最近一次缓存，离线不能修改；重新连接后会先获取最新数据。'],
  conflict:['其他裝置已更新。請先保留你的輸入，再重新整理並檢查；本次修改尚未儲存。','其他设备已更新。请先保留你的输入，再刷新并检查；本次修改尚未保存。'],
  uncertain:['連線中斷，這次儲存結果尚未確認。重新連線後請檢查最新資料；不要重複記錄投入。','连接中断，这次保存结果尚未确认。重新连接后请检查最新数据；不要重复记录投入。'],
  signin:['登入','登录'],signout:['登出','退出'],username:['帳號','账号'],password:['密碼','密码'],
  loginNote:['以 NAS 管理員建立的帳號登入。同一帳號在所有裝置使用同一張表。','以 NAS 管理员创建的账号登录。同一账号在所有设备使用同一张表。'],
  privateNote:['每個帳號的資料獨立。此裝置會快取最近的行程，登出會清除快取。','每个账号的数据独立。此设备会缓存最近的行程，退出会清除缓存。'],
  addTask:['記一件事','记一件事'],pending:['待做任務','待办任务'],goals:['長期目標','长期目标'],done:['已完成','已完成'],
  urgentImportant:['緊急 · 重要','紧急 · 重要'],laterImportant:['重要 · 不緊急','重要 · 不紧急'],urgentOther:['緊急 · 較不重要','紧急 · 较不重要'],laterOther:['有空再看','有空再看'],
  urgent:['更緊急 ↑','更紧急 ↑'],important:['更重要 →','更重要 →'],zoomIn:['放大','放大'],zoomOut:['縮小','缩小'],
  mapNote:['點一下圓點查看或記錄投入。長期目標會隨累積投入逐漸填滿。','点一下圆点查看或记录投入。长期目标会随累计投入逐渐填满。'],
  empty:['留白，從記下一件事開始。','留白，从记下一件事开始。'],title:['名稱','名称'],course:['分類／科目','分类／科目'],
  type:['類型','类型'],deadline:['有 DDL 的任務','有 DDL 的任务'],goal:['長期目標','长期目标'],due:['截止日期','截止日期'],startDate:['最早開始日（可留空）','最早开始日（可留空）'],
  hours:['剩餘工時（小時）','剩余工时（小时）'],target:['圓點參考工時（小時）','圆点参考工时（小时）'],isImportant:['這件事很重要','这件事很重要'],
  save:['儲存','保存'],cancel:['取消','取消'],edit:['編輯','编辑'],remove:['移除任務','移除任务'],confirmDelete:['確定移除？','确定移除？'],
  effort:['這次做了多少？','这次做了多少？'],actualStart:['實際開始時間','实际开始时间'],actual:['實際投入（小時）','实际投入（小时）'],finished:['整份任務已完成','整份任务已完成'],record:['記錄投入','记录投入'],
  effortNote:['提前完成會釋放餘下時間。前移只是建議，你仍可繼續操作原安排。','提前完成会释放剩余时间。前移只是建议，你仍可继续操作原安排。'],
  invested:['累積投入','累计投入'],goalNote:['圓點填滿代表投入達到參考工時，不代表目標已完成。','圆点填满代表投入达到参考工时，不代表目标已完成。'],
  week:['七日','七日'],day:['單日','单日'],today:['今天','今天'],previous:['上一日','上一日'],next:['下一日','下一日'],
  calendarNote:['半小時一格。拖動任務可調整時間；手機長按後拖動。固定事項鎖定。','半小时一格。拖动任务可调整时间；手机长按后拖动。固定事项锁定。'],
  fixed:['固定事項','固定事项'],personal:['私人時間','私人时间'],proposal:['前移建議','前移建议'],work:['已投入','已投入'],
  proposalNote:['原安排仍然有效。展開後，半透明色顯示前移前後的位置。','原安排仍然有效。展开后，半透明色显示前移前后的位置。'],
  showSuggestion:['查看建議','查看建议'],accept:['確認前移','确认前移'],keep:['保留原安排','保留原安排'],
  missing:['尚未安排','尚未安排'],overdue:['已逾期','已逾期'],outside_week:['本週未排完','本周未排完'],deadline_capacity:['期限前空檔不足','期限前空档不足'],
  move:['調整這段安排','调整这段安排'],date:['日期','日期'],begin:['開始時間','开始时间'],end:['結束時間','结束时间'],moveSave:['移動這段任務','移动这段任务'],
  addEvent:['加入事項','添加事项'],repeat:['重複','重复'],none:['不重複','不重复'],daily:['每天','每天'],weekly:['每週','每周'],monthly:['每月同日','每月同日'],workdays:['每工作日','每工作日'],holidays:['每假日','每假日'],
  until:['重複直到（可留空）','重复直到（可留空）'],weekdays:['每週重複日期','每周重复日期'],
  eventNote:['結束早於開始代表跨午夜。每月沒有同一天時略過該月。固定事項不可拖動。','结束早于开始代表跨午夜。每月没有同一天时略过该月。固定事项不可拖动。'],
  editSeries:['編輯整個系列','编辑整个系列'],deleteSeries:['移除整個系列','移除整个系列'],deleteOnce:['只移除這一次','只移除这一次'],saveSeries:['儲存事項系列','保存事项系列'],
  life:['先留好生活的位置','先留好生活的位置'],lifeNote:['課程、輪班和私人時間由你設定；不預設朝九晚五。','课程、轮班和私人时间由你设置；不预设朝九晚五。'],
  prefs:['語言與排程','语言与排程'],language:['語言','语言'],workdayNote:['工作日用於「每工作日／每假日」重複，另扣除香港公眾假日。內置 2026–2027 年假日。','工作日用于“每工作日／每假日”重复，另扣除香港公众假日。内置 2026–2027 年假日。'],
  borrow:['允許 3 天內到期的任務借用私人時間','允许 3 天内到期的任务借用私人时间'],
  data:['匯入、匯出與離線','导入、导出与离线'],export:['匯出備份 JSON','导出备份 JSON'],import:['匯入備份','导入备份'],importConfirm:['以備份取代我目前的整張表（伺服器會保留匯入前備份）','以备份替换我目前的整张表（服务器会保留导入前备份）'],
  snapshot:['下載唯讀離線快照','下载只读离线快照'],snapshotNote:['局域網 HTTP：開著的頁面可離線查看；要關閉後再離線開啟，請先下載快照或使用 NAS APK。快照含個人行程。','局域网 HTTP：开着的页面可离线查看；要关闭后再离线打开，请先下载快照或使用 NAS APK。快照含个人行程。'],
  security:['帳號與安全','账号与安全'],currentPassword:['目前密碼','当前密码'],newPassword:['新密碼（至少 12 字元）','新密码（至少 12 字符）'],changePassword:['修改密碼並登出所有裝置','修改密码并退出所有设备'],
  admin:['建立組員帳號','创建组员账号'],createUser:['建立帳號','创建账号'],adminNote:['只建立獨立的空白表。管理員介面不提供查看其他人的行程。','只创建独立的空白表。管理员界面不提供查看他人的行程。'],
  server:['NAS 伺服器','NAS 服务器'],changeServer:['更改 NAS 地址','更改 NAS 地址'],saved:['已儲存至 NAS','已保存到 NAS'],
  created:['帳號已建立','账号已创建'],passwordChanged:['密碼已修改，請重新登入。','密码已修改，请重新登录。'],
  fileRequired:['請先選擇備份檔。','请先选择备份文件。'],fileTooLarge:['備份檔不能超過 8 MB。','备份文件不能超过 8 MB。'],
  offlineLogin:['目前無法連接 NAS。已有快取的帳號可以唯讀查看，首次登入需要連線。','目前无法连接 NAS。已有缓存的账号可以只读查看，首次登录需要连接。'],
  snapshotLabel:['唯讀快照','只读快照'],close:['關閉','关闭'],updated:['行程已更新','行程已更新'],unsupportedHolidays:['此年份尚未內置完整香港公眾假日。','此年份尚未内置完整香港公众假日。'],
  windows:['舊版自訂可用時段','旧版自定义可用时段'],windowsNote:['匯入資料使用了自訂空檔。可改回全日扣除事項，或繼續沿用。','导入数据使用了自定义空档。可改回全日扣除事项，或继续沿用。'],allDay:['改為全日扣除事項','改为全日扣除事项']
};
const EN={map:'Task map',schedule:'Schedule',settings:'Life & settings',room:'A little room for your future self.',intro:'Protect your life first. Make time for your deadlines.',online:'Connected to NAS',offline:'Offline · read only',refresh:'Refresh',readOnly:'Showing the last cached plan. Changes are disabled offline. Reconnect to load the latest data first.',conflict:'Another device updated this plan. Keep a copy of your input, then refresh and review it. This change has not been saved.',uncertain:'Connection lost. This save has not been confirmed. Reconnect and check the latest plan before recording the same effort again.',signin:'Sign in',signout:'Sign out',username:'Username',password:'Password',loginNote:'Use an account created by your NAS administrator. The same account uses the same plan on every device.',privateNote:'Each account has its own plan. This device caches the latest schedule; signing out clears it.',addTask:'Add task',pending:'Pending tasks',goals:'Long-term goals',done:'Completed',urgentImportant:'Urgent · important',laterImportant:'Important · not urgent',urgentOther:'Urgent · less important',laterOther:'When there is time',urgent:'More urgent ↑',important:'More important →',zoomIn:'Zoom in',zoomOut:'Zoom out',mapNote:'Select a dot to view or record effort. Goal dots fill as your invested time increases.',empty:'Leave a little room. Start with one task.',title:'Title',course:'Category / course',type:'Type',deadline:'Task with a deadline',goal:'Long-term goal',due:'Due date',startDate:'Earliest start (optional)',hours:'Remaining hours',target:'Reference hours for dot fill',isImportant:'This matters to me',save:'Save',cancel:'Cancel',edit:'Edit',remove:'Delete task',confirmDelete:'Delete this item?',effort:'What did you work on?',actualStart:'Actual start time',actual:'Hours invested',finished:'The whole task is completed',record:'Record effort',effortNote:'Finishing early frees the remaining time. Earlier moves are suggestions; your current plan stays usable.',invested:'Time invested',goalNote:'A full dot means the reference hours have been reached. It does not mark the goal as completed.',week:'7 days',day:'Day',today:'Today',previous:'Previous day',next:'Next day',calendarNote:'30-minute slots. Drag a task to move it; on mobile, press and hold first. Fixed events are locked.',fixed:'Fixed event',personal:'Personal time',proposal:'Earlier-move suggestion',work:'Recorded effort',proposalNote:'Your current plan remains active. Expand to preview the old and suggested positions in translucent colors.',showSuggestion:'View suggestion',accept:'Accept moves',keep:'Keep current plan',missing:'Unscheduled',overdue:'Overdue',outside_week:'Not fully scheduled this week',deadline_capacity:'Insufficient time before deadline',move:'Adjust this time block',date:'Date',begin:'Start time',end:'End time',moveSave:'Move this task block',addEvent:'Add event',repeat:'Repeat',none:'Does not repeat',daily:'Every day',weekly:'Every week',monthly:'Monthly on this date',workdays:'Every workday',holidays:'Every day off',until:'Repeat until (optional)',weekdays:'Weekly repeat days',eventNote:'An end time before the start crosses midnight. Months without this date are skipped. Fixed events cannot be dragged.',editSeries:'Edit entire series',deleteSeries:'Delete entire series',deleteOnce:'Delete this occurrence only',saveSeries:'Save event series',life:'Make room for your life first',lifeNote:'Set your own classes, shifts and personal time. There are no assumed office hours.',prefs:'Language & planning',language:'Language',workdayNote:'Workdays control workday/day-off repeats and exclude Hong Kong general holidays. Holidays for 2026–2027 are included.',borrow:'Let deadlines within 3 days use personal time',data:'Import, export & offline',export:'Export backup JSON',import:'Import backup',importConfirm:'Replace my entire plan with this backup (the server keeps a pre-import backup)',snapshot:'Download read-only offline snapshot',snapshotNote:'LAN HTTP: an open page works offline. To reopen offline later, download a snapshot or use the NAS APK. Snapshots contain your personal schedule.',security:'Account & security',currentPassword:'Current password',newPassword:'New password (12+ characters)',changePassword:'Change password & sign out all devices',admin:'Create a teammate account',createUser:'Create account',adminNote:'Creates a separate empty plan. The administrator interface does not expose other users’ schedules.',server:'NAS server',changeServer:'Change NAS address',saved:'Saved to NAS',created:'Account created',passwordChanged:'Password changed. Please sign in again.',fileRequired:'Select a backup file first.',fileTooLarge:'Backup must be under 8 MB.',offlineLogin:'Cannot connect to NAS. A previously cached account can be viewed read-only. First sign-in needs a connection.',snapshotLabel:'Read-only snapshot',close:'Close',updated:'Plan updated',unsupportedHolidays:'Full Hong Kong holidays are not included for this year.',windows:'Legacy custom availability',windowsNote:'The imported plan uses custom availability windows. Keep them, or switch to full-day availability minus events.',allDay:'Use full day minus events'};
Object.assign(TEXT,{
  register:['創建帳號','创建账号'],registerLink:['以邀請碼建立帳號','用邀请码创建账号'],backToLogin:['已有帳號？返回登入','已有账号？返回登录'],
  loginNote:['登入即可在所有裝置使用同一張表；新使用者可憑邀請碼建立帳號。','登录即可在所有设备使用同一张表；新用户可凭邀请码创建账号。'],
  registerNote:['輸入管理員給你的邀請碼，以自己的帳號及密碼建立獨立行程。此處只建立一般帳號。','输入管理员给你的邀请码，用自己的账号和密码创建独立日程。这里只创建普通账号。'],
  inviteCode:['邀請碼','邀请码'],confirmPassword:['再次輸入密碼','再次输入密码'],
  invites:['邀請碼管理','邀请码管理'],inviteNote:['每個邀請碼僅用一次，7 天內有效。完整碼只在建立當下顯示，請複製交給使用者；其他設定均屬各人自己的行程。','每个邀请码仅用一次，7 天内有效。完整码只在创建时显示，请复制给使用者；其他设置均属于个人日程。'],
  generateInvite:['產生邀請碼','生成邀请码'],inviteGenerated:['邀請碼已產生，請複製保存。','邀请码已生成，请复制保存。'],
  inviteOnce:['請複製這個邀請碼，離開帳號後不再顯示。','请复制这个邀请码，退出账号后不再显示。'],
  inviteEmpty:['還沒有邀請碼。','还没有邀请码。'],invitePending:['未使用','未使用'],used:['已使用','已使用'],expired:['已到期','已过期'],revoked:['已撤銷','已撤销'],revoke:['撤銷','撤销'],
  expires:['到期','到期'],inviteRevoked:['邀請碼已撤銷。','邀请码已撤销。'],registered:['帳號已建立並登入。','账号已创建并登录。'],
  invalidInvite:['邀請碼無效、已使用或已失效，請向管理員索取新碼。','邀请码无效、已使用或已失效，请向管理员索取新码。'],
  usernameRule:['帳號需為 3–40 個英文字母、數字、點、底線或連字號。','账号须为 3–40 个英文字母、数字、点、下划线或连字符。'],
  passwordRule:['密碼需為 12–200 字元。','密码须为 12–200 字符。'],passwordMismatch:['兩次輸入的密碼不同。','两次输入的密码不同。'],usernameTaken:['此帳號名稱已被使用，請換一個。','此账号名已被使用，请换一个。'],
  alreadySignedIn:['請先登出，才可建立另一個帳號。','请先退出，才可创建另一个账号。'],tooManyAttempts:['嘗試次數過多，請 15 分鐘後再試。','尝试次数过多，请 15 分钟后再试。'],
  registrationUncertain:['連線中斷，帳號是否建立尚未確認；重新連線後可先嘗試登入。','连接中断，账号是否创建尚未确认；重新连接后可先尝试登录。']
});
Object.assign(EN,{register:'Create account',registerLink:'Create an account with an invitation',backToLogin:'Already have an account? Sign in',loginNote:'Sign in to use the same plan on all devices, or create an account with an invitation.',registerNote:'Use an invitation from your administrator to create your own account and private plan. This creates a regular account only.',inviteCode:'Invitation code',confirmPassword:'Repeat password',invites:'Invitation management',inviteNote:'Each code can be used once within 7 days. The full code is shown only when created; copy it for the new user. Other settings belong to each user’s own plan.',generateInvite:'Generate invitation',inviteGenerated:'Invitation created. Copy and keep the code.',inviteOnce:'Copy this invitation code. Signing out clears it from this page.',inviteEmpty:'No invitations yet.',invitePending:'Unused',used:'Used',expired:'Expired',revoked:'Revoked',revoke:'Revoke',expires:'Expires',inviteRevoked:'Invitation revoked.',registered:'Account created and signed in.',invalidInvite:'Invalid, used or expired invitation. Ask your administrator for a new code.',usernameRule:'Use 3–40 letters, digits, dots, underscores or hyphens for the username.',passwordRule:'Use 12–200 characters for the password.',passwordMismatch:'The two passwords do not match.',usernameTaken:'This username is already in use.',alreadySignedIn:'Sign out before creating another account.',tooManyAttempts:'Too many attempts. Try again in 15 minutes.',registrationUncertain:'Connection lost. Account creation is unconfirmed. Reconnect and try signing in first.'});
Object.assign(TEXT,{invalidResponse:['伺服器回應格式不正確，請稍後重新整理並確認最新資料。','服务器响应格式不正确，请稍后刷新并确认最新数据。']});
Object.assign(EN,{invalidResponse:'The server returned an invalid response. Refresh later and check the latest data.'});
Object.assign(TEXT,{
  localSetupTitle:['建立本機帳號','创建本机账号'],
  localSetupNote:['第一次使用時請設定帳號和密碼。這個帳號只用於此份本機資料，無需邀請碼。','第一次使用时请设置账号和密码。这个账号只用于此份本机数据，无需邀请码。'],
  localSetupComplete:['本機帳號已建立，請登入。','本机账号已创建，请登录。']
});
Object.assign(EN,{localSetupTitle:'Create your local account',localSetupNote:'Choose a username and password to get started. This account is for this local copy and needs no invitation.',localSetupComplete:'Local setup is complete. Sign in with your account.'});
let language='zh-Hant';
try{language=localStorage.getItem('planwise-language')||language;}catch{}
const embedded=document.getElementById('offline-data');
const CACHE_KEY='planwise-nas-snapshot-v1';
let snap=embedded?JSON.parse(embedded.textContent):cached();
let offline=!!snap,busy=false,syncing=false,dirty=false,tab=new URLSearchParams(location.search).get('tab')||'map',dayIndex=0,zoom=1,showProposal=false,remoteChanged=false;
let authMode='login',authSubmitting=false,authEpoch=0,issuedInvite='';
let span=new URLSearchParams(location.search).get('span')==='day'?'day':'week';
const $=selector=>document.querySelector(selector);
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const t=key=>language==='en'?(EN[key]||key):(TEXT[key]?.[language==='zh-Hans'?1:0]||EN[key]||key);
const time=minute=>`${String(Math.floor(minute/60)).padStart(2,'0')}:${String(minute%60).padStart(2,'0')}`;
const weekday=index=>(language==='en'?['Mon','Tue','Wed','Thu','Fri','Sat','Sun']:language==='zh-Hans'?['周一','周二','周三','周四','周五','周六','周日']:['週一','週二','週三','週四','週五','週六','週日'])[index];
const locale=()=>language==='en'?'en-HK':language==='zh-Hans'?'zh-CN':'zh-HK';
function notify(message){$('#notice').textContent=message;$('#notice').classList.add('show');clearTimeout(notify.timer);notify.timer=setTimeout(()=>$('#notice').classList.remove('show'),6500);}
function cached(){try{const data=JSON.parse(localStorage.getItem(CACHE_KEY));return data?.api_version===1&&data.user&&data.view&&Array.isArray(data.state?.tasks)?data:null;}catch{return null;}}
function clearCache(){try{localStorage.removeItem(CACHE_KEY);}catch{}}
function adopt(data){
  if(data.api_version!==1)throw new Error('This server needs a newer client.');
  if(!snap||snap.user.id!==data.user.id){clearCache();issuedInvite='';}
  snap=data;language=data.state.language;offline=false;remoteChanged=false;
  authMode='login';
  const cache=structuredClone(data);delete cache.csrf;delete cache.invitations;
  try{localStorage.setItem(CACHE_KEY,JSON.stringify(cache));localStorage.setItem('planwise-language',language);}catch{}
}
async function api(path,data){
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),8000);
  try{
    const response=await fetch(path,{method:data?'POST':'GET',credentials:'same-origin',cache:'no-store',signal:controller.signal,headers:{'Content-Type':'application/json','X-Planwise-Client':'1',...(snap?.csrf?{'X-CSRF-Token':snap.csrf}:{})},...(data?{body:JSON.stringify(data)}:{})});
    let result;
    try{result=await response.json();}catch{
      const error=new Error(t('invalidResponse'));error.code='invalid_response';
      if(!response.ok)error.status=response.status;
      throw error;
    }
    if(!result||typeof result!=='object'||Array.isArray(result)){
      const error=new Error(t('invalidResponse'));error.code='invalid_response';
      if(!response.ok)error.status=response.status;
      throw error;
    }
    if(!response.ok){const error=new Error(result.error||response.statusText);error.status=response.status;error.code=result.code;throw error;}
    return result;
  }finally{clearTimeout(timer);}
}
function lockWrites(){document.querySelectorAll('[data-write],form input,form select,form textarea,form button').forEach(el=>el.disabled=offline||busy);document.body.classList.toggle('readonly',offline);}
function markOffline(message){offline=true;if(!snap){snap=cached();if(snap)language=snap.state.language;render();}else updateConnection();if(message)notify(message);}
async function sync(force=false){
  if(embedded||busy||syncing||authSubmitting)return;
  syncing=true;
  const epoch=authEpoch;
  try{
    const data=await api('/api/state');
    if(epoch!==authEpoch)return;
    if(!force&&(!$('#bubble').hidden||dirty)&&snap&&data.user.id===snap.user.id){
      if(data.version!==snap.version){remoteChanged=true;updateConnection();}
      snap.csrf=data.csrf;offline=false;updateConnection();return;
    }
    if(!force&&snap&&!offline&&data.version===snap.version&&data.user.id===snap.user.id&&JSON.stringify(data.invitations)===JSON.stringify(snap.invitations))return;
    const scrolling=$('.calendar-wrap')?.scrollTop;
    adopt(data);if(force)closeBubble();render();if(scrolling!==undefined&&$('.calendar-wrap'))$('.calendar-wrap').scrollTop=scrolling;
  }catch(error){
    if(epoch!==authEpoch)return;
    if(error.status===401){
      const hadPlan=!!snap, needsSetup=error.code==='setup_required';
      const authChanged=needsSetup!==(authMode==='setup');
      if(authChanged)authMode=needsSetup?'setup':'login';
      snap=null;offline=false;clearCache();closeBubble();
      if(hadPlan||authChanged)render();else updateConnection();
    }
    else if(!error.status)markOffline();
    else if(force)notify(error.message);
  }finally{syncing=false;}
}
function updateConnection(){
  const el=$('#connection');if(el)el.innerHTML=connection();
  if(!offline)$('#offline-banner')?.remove();
  if(offline&&snap&&!$('#offline-banner')){
    const banner=document.createElement('div');banner.id='offline-banner';banner.className='banner warn';banner.textContent=t('readOnly');
    const button=document.createElement('button');button.textContent=t('refresh');button.onclick=()=>sync(true);banner.append(button);$('#content')?.prepend(banner);
  }
  lockWrites();
}
function connection(){return `<span class="status ${offline?'off':''}">${esc(t(offline?'offline':'online'))}</span>${remoteChanged?`<button data-cmd="refresh">${esc(t('refresh'))} ↻</button>`:''}`;}
async function change(action,fields={},version=snap?.version){
  if(offline||busy){notify(t('readOnly'));return false;}
  busy=true;lockWrites();
  try{
    const requestId=globalThis.crypto?.randomUUID?.()||Array.from(crypto.getRandomValues(new Uint8Array(16)),b=>b.toString(16).padStart(2,'0')).join('');
    const data=await api('/api/actions',{action,fields,version,request_id:requestId});
    const scroll=$('.calendar-wrap')?.scrollTop;adopt(data);closeBubble();render();if(scroll!==undefined&&$('.calendar-wrap'))$('.calendar-wrap').scrollTop=scroll;notify(t('saved'));return true;
  }catch(error){
    if(error.status===409){remoteChanged=true;formError(t('conflict'));updateConnection();}
    else if(error.status===401){clearCache();snap=null;closeBubble();render();notify(error.message);}
    else if(!error.status){offline=true;formError(t('uncertain'));updateConnection();notify(t('uncertain'));}
    else formError(error.message);
    return false;
  }finally{busy=false;lockWrites();}
}
function formError(message){const el=$('#bubble .error');if(el){el.hidden=false;el.textContent=message;el.scrollIntoView({block:'nearest'});}else notify(message);}
function languageOptions(value){return ['zh-Hant','zh-Hans','en'].map((code,i)=>`<option value="${code}" ${value===code?'selected':''}>${['繁體中文','简体中文','English'][i]}</option>`).join('');}
function authPage(){
  const setup=authMode==='setup', registering=authMode!=='login';
  const disabled=registering&&offline?'disabled':'';
  return `<main class="login paper" id="content"><div class="eyebrow">PLANWISE / NAS EDITION</div><h1>${language==='en'?'Planwise':'留白'}</h1>${registering?`<h2 class="auth-title">${esc(t(setup?'localSetupTitle':'register'))}</h2>`:''}<p class="subtitle">${esc(t(setup?'localSetupNote':registering?'registerNote':'loginNote'))}</p><form id="${registering?'register-form':'login-form'}">${authMode==='register'?`<label for="invite-code">${esc(t('inviteCode'))}</label><input id="invite-code" name="invite_code" autocomplete="off" autocapitalize="none" spellcheck="false" required minlength="16" maxlength="80" ${disabled}>`:''}<label for="username">${esc(t('username'))}</label><input id="username" name="username" autocomplete="username" required maxlength="40" ${registering?'minlength="3" pattern="[A-Za-z0-9_.\\-]{3,40}"':''} ${disabled}><label for="password">${esc(t('password'))}</label><input id="password" name="password" type="password" autocomplete="${registering?'new-password':'current-password'}" required ${registering?'minlength="12"':''} maxlength="200" ${disabled}>${registering?`<label for="confirm-password">${esc(t('confirmPassword'))}</label><input id="confirm-password" name="password_confirm" type="password" autocomplete="new-password" required minlength="12" maxlength="200" ${disabled}>`:''}<button class="primary" type="submit" ${disabled}>${esc(t(registering?'register':'signin'))} →</button></form>${setup?'':`<button class="auth-switch" id="auth-switch" type="button">${esc(t(registering?'backToLogin':'registerLink'))}</button>`}<label for="login-language">${esc(t('language'))}</label><select id="login-language">${languageOptions(language)}</select><footer>${esc(t('privateNote'))}</footer>${offline?`<div id="offline-banner" class="banner warn">${esc(t('offlineLogin'))}<button id="retry-connect">${esc(t('refresh'))}</button></div>`:''}${/PlanwiseNAS/.test(navigator.userAgent)?`<p class="foot"><a href="/client/change-server">${esc(t('changeServer'))}</a></p>`:''}</main>`;
}
function bindAuth(){
  const form=$('#login-form')||$('#register-form');
  form.onsubmit=submitAuth;
  if($('#auth-switch'))$('#auth-switch').onclick=()=>{if(authSubmitting)return;authMode=authMode==='login'?'register':'login';render();};
  if($('#retry-connect'))$('#retry-connect').onclick=()=>sync(true);
  $('#login-language').onchange=event=>{language=event.target.value;render();};
}
async function submitAuth(event){
  event.preventDefault();
  if(authSubmitting)return;
  const setup=authMode==='setup', registering=authMode!=='login';
  if(registering&&offline){notify(t('offlineLogin'));return;}
  const fields=fieldsFrom(event.target);
  if(registering&&fields.password!==fields.password_confirm){notify(t('passwordMismatch'));return;}
  fields.language=language;
  authSubmitting=true;authEpoch++;
  const button=event.submitter;if(button)button.disabled=true;
  clearCache();
  try{
    await api(setup?'/api/setup':registering?'/api/register':'/api/login',fields);
    const current=await api('/api/state');
    adopt(current);render();if(registering)notify(t('registered'));
  }catch(error){
    if(setup&&error.code==='setup_complete'){
      authMode='login';render();notify(t('localSetupComplete'));return;
    }
    const key={invalid_invitation:'invalidInvite',invalid_username:'usernameRule',password_length:'passwordRule',password_mismatch:'passwordMismatch',username_taken:'usernameTaken',already_signed_in:'alreadySignedIn',rate_limited:'tooManyAttempts'}[error.code];
    notify(!error.status?t(registering?'registrationUncertain':'offlineLogin'):key?t(key):error.message);
  }finally{authSubmitting=false;if(button)button.disabled=false;}
}
function invitationPanel(){
  const rows=snap.invitations||[];
  return `<section class="paper card" id="invite-panel"><h2>${esc(t('invites'))}</h2><p class="subtitle">${esc(t('inviteNote'))}</p><button class="primary" data-invite-action="create" data-write>${esc(t('generateInvite'))}</button>${issuedInvite?`<div class="invite-code"><label for="issued-code">${esc(t('inviteOnce'))}</label><input id="issued-code" value="${esc(issuedInvite)}" readonly spellcheck="false" autocomplete="off"></div>`:''}<div class="invite-list">${rows.map(row=>`<div class="row"><div><strong>#${row.id} · ${esc(t(row.status==='pending'?'invitePending':row.status))}</strong>${row.used_by?`<small>${esc(row.used_by)}</small>`:''}<small>${esc(t('expires'))} ${new Date(row.expires_at*1000).toLocaleString(locale())}</small></div>${row.status==='pending'?`<button class="danger" data-invite-action="revoke" data-invite-id="${row.id}" data-write>${esc(t('revoke'))}</button>`:''}</div>`).join('')||`<p class="subtitle">${esc(t('inviteEmpty'))}</p>`}</div></section>`;
}
async function invitationAction(action,id){
  if(offline||busy||!snap?.user.is_admin)return;
  busy=true;lockWrites();
  try{
    const result=await api('/api/invitations',{action,...(id?{id:Number(id)}:{})});
    snap.invitations=result.invitations;
    if(result.code)issuedInvite=result.code;
    else issuedInvite='';
    render();notify(t(action==='create'?'inviteGenerated':'inviteRevoked'));
  }catch(error){notify(error.message);}
  finally{busy=false;lockWrites();}
}
function render(){
  dirty=false;
  if(snap)language=snap.state.language;
  document.documentElement.lang=language;
  if(!snap){issuedInvite='';$('#app').innerHTML=authPage();bindAuth();return;}
  if(!['map','schedule','settings'].includes(tab))tab='map';
  $('#app').innerHTML=`<div class="shell"><header><div class="brand">${language==='en'?'Planwise':'留白'} <span>PLANWISE / NAS</span></div><div class="account"><span>${esc(snap.user.username)}</span><span id="connection">${connection()}</span><button class="quiet" data-cmd="logout" data-write>${esc(t('signout'))}</button></div></header><nav aria-label="Navigation">${['map','schedule','settings'].map(key=>`<button class="${tab===key?'active':''}" data-tab="${key}">${esc(t(key))}</button>`).join('')}</nav><main id="content">${offline?`<div id="offline-banner" class="banner warn">${esc(embedded?t('snapshotLabel'):t('readOnly'))} · ${new Date(snap.saved_at*1000).toLocaleString(locale())}${!embedded?` <button data-cmd="refresh">${esc(t('refresh'))}</button>`:''}</div>`:''}${tab==='map'?mapPage():tab==='schedule'?schedulePage():settingsPage()}</main><p class="foot">${esc(t('server'))}: ${esc(embedded?'offline snapshot':location.origin)} · v${snap.version}${/PlanwiseNAS/.test(navigator.userAgent)?` · <a href="/client/change-server">${esc(t('changeServer'))}</a>`:''}</p></div>`;
  bind();lockWrites();
  if(tab==='schedule')requestAnimationFrame(()=>{const el=$('.calendar-wrap');if(el)el.scrollTop=Math.max(0,(snap.view.cutoff/60-1)*56);});
}
function mapPage(){
  const tasks=snap.state.tasks.filter(task=>!task.completed),goals=tasks.filter(task=>task.kind==='goal');
  const groups=[0,1,2,3].map(rank=>tasks.filter(task=>snap.view.ranks[task.id]===rank).sort((a,b)=>(a.due||'9999').localeCompare(b.due||'9999')||a.id.localeCompare(b.id)));
  let dots='';
  groups.forEach((items,rank)=>items.forEach((task,i)=>{
    const cols=Math.ceil(Math.sqrt(items.length)),rows=Math.ceil(items.length/cols),right=rank<2,top=rank===0||rank===2;
    const x=(right?57:8)+(i%cols+.5)/cols*35,y=(top?17:63)+(Math.floor(i/cols)+.5)/rows*25;
    const fill=task.kind==='goal'?(snap.view.progress[task.id]?.[2]||0)*100:100;
    dots+=`<button class="map-task ${top?'urgent':''}" style="left:${x}%;top:${y}%" data-task="${esc(task.id)}" title="${esc(task.title)}" aria-label="${esc(task.title)}"><i class="dot" style="--fill:${fill}%"></i><span class="map-name">${esc(task.title)}</span></button>`;
  }));
  return `<div class="heading"><div><div class="eyebrow">A LITTLE ROOM TO BREATHE</div><h1>${esc(t('room'))}</h1><p class="subtitle">${esc(t('intro'))}</p></div><button class="primary" data-cmd="add-task" data-write>＋ ${esc(t('addTask'))}</button></div><div class="stats"><div><strong>${tasks.length-goals.length}</strong>${esc(t('pending'))}</div><div><strong>${goals.length}</strong>${esc(t('goals'))}</div><div><strong>${snap.state.tasks.filter(task=>task.completed).length}</strong>${esc(t('done'))}</div></div><div class="paper map-scroll"><div class="map ${tasks.length>18?'dense':''}" style="width:${zoom*100}%;height:${Math.round((innerWidth<700?400:560)*zoom)}px"><div class="wash ul"></div><div class="wash ur"></div><div class="wash ll"></div><div class="wash lr"></div><div class="axis-x"></div><div class="axis-y"></div><span class="axis-label y">${esc(t('urgent'))}</span><span class="axis-label x">${esc(t('important'))}</span>${['urgentImportant','laterImportant','urgentOther','laterOther'].map((key,i)=>`<span class="quadrant-label q${i}">${esc(t(key))}</span>`).join('')}${dots}</div></div><div class="toolbar" style="margin-top:12px"><button data-cmd="zoom-out" aria-label="${esc(t('zoomOut'))}">−</button><small>${Math.round(zoom*100)}%</small><button data-cmd="zoom-in" aria-label="${esc(t('zoomIn'))}">＋</button><span class="foot" style="margin:0">${esc(t('mapNote'))}</span></div>${!tasks.length?`<p class="empty">${esc(t('empty'))}</p>`:''}<details class="list"><summary>${esc(t('done'))} · ${snap.state.tasks.filter(task=>task.completed).length}</summary>${snap.state.tasks.filter(task=>task.completed).map(task=>`<div class="row">${esc(task.title)}<small>${esc(task.completed_on)}</small></div>`).join('')}</details>`;
}
function blockHtml(block,kind='task',ghost=false){
  const task=snap.state.tasks.find(t=>t.id===block.task_id),urgent=task&&[0,2].includes(snap.view.ranks[task.id]);
  const title=task?.title||block.title||t('work');
  const payload=esc(JSON.stringify({...block,_kind:kind}));
  return `<button class="block ${kind==='task'?(urgent?'urgent':''):kind} ${ghost?'ghost '+ghost:''}" style="top:${block.start/1440*100}%;height:${(block.end-block.start)/1440*100}%" data-block="${payload}" ${ghost==='destination'?'tabindex="-1" aria-hidden="true"':''} title="${esc(title)} ${time(block.start)}–${time(block.end)}"><strong>${kind==='fixed'?'⌑ ':''}${esc(title)}</strong><small>${time(block.start)}–${time(block.end)}</small></button>`;
}
function schedulePage(){
  const days=span==='week'?snap.view.days:[snap.view.days[dayIndex]];
  const proposal=snap.state.proposal;
  const preview=snap.view.preview;
  const blocks=snap.state.calendar;
  const isRemoved=block=>proposal&&showProposal&&preview.removed.some(old=>old.task_id===block.task_id&&old.date===block.date&&old.start<block.end&&old.end>block.start);
  return `<div class="heading"><div><div class="eyebrow">ONE HALF-HOUR AT A TIME</div><h1>${esc(t('schedule'))}</h1><p class="subtitle">${esc(t('calendarNote'))}</p></div><button class="primary" data-cmd="add-task" data-write>＋ ${esc(t('addTask'))}</button></div><div class="toolbar" style="margin-bottom:15px"><button data-cmd="prev-day" ${dayIndex===0?'disabled':''} aria-label="${esc(t('previous'))}">←</button><button data-cmd="today">${esc(t('today'))}</button><button data-cmd="next-day" ${dayIndex===6?'disabled':''} aria-label="${esc(t('next'))}">→</button><strong>${esc(days[0].date)}${span==='week'?` — ${days.at(-1).date.slice(5)}`:''}</strong><button data-cmd="span-day" ${span==='day'?'class="primary"':''}>${esc(t('day'))}</button><button data-cmd="span-week" ${span==='week'?'class="primary"':''}>${esc(t('week'))}</button></div>${proposal?`<div class="banner"><strong>${esc(t('proposal'))}</strong><p>${esc(t('proposalNote'))}</p><button data-cmd="show-proposal">${esc(t('showSuggestion'))} ${showProposal?'−':'＋'}</button>${showProposal?`<button data-cmd="accept" data-write>${esc(t('accept'))}</button><button data-cmd="keep" data-write>${esc(t('keep'))}</button>`:''}</div>`:''}<div class="calendar-wrap ${span==='week'?'week-view':''}"><div class="cal-head"><div class="cal-corner">GMT+8</div>${days.map(day=>`<button class="day-head ${day.date===snap.view.today?'today':''} ${day.holiday?'holiday':''}" data-view-day="${snap.view.days.indexOf(day)}">${esc(weekday(day.weekday))}<b>${Number(day.date.slice(-2))}</b><small>${esc(day.holiday?language==='en'?'HK holiday':day.holiday:'')}</small></button>`).join('')}</div><div class="cal-body"><div class="times">${Array.from({length:24},(_,hour)=>`<span class="time" style="top:${hour/24*100}%">${time(hour*60)}</span>`).join('')}</div>${days.map(day=>`<div class="day-col" data-date="${day.date}">${snap.view.available.filter(([date])=>date===day.date).map(([,minute])=>`<div class="free-cell" style="top:${minute/1440*100}%"></div>`).join('')}${snap.view.occurrences.filter(b=>b.date===day.date).map(b=>blockHtml(b,b.category==='private'?'private':'fixed')).join('')}${snap.state.work_log.filter(b=>b.date===day.date&&Number.isInteger(b.start)).map(b=>blockHtml(b,'work')).join('')}${blocks.filter(b=>b.date===day.date).map(b=>blockHtml(b,'task',isRemoved(b)?"origin":false)).join('')}${proposal&&showProposal?preview.added.filter(b=>b.date===day.date).map(b=>blockHtml(b,'task','destination')).join(''):''}${day.date===snap.view.today?`<div class="now-line" style="top:${snap.view.cutoff/1440*100}%"></div>`:''}</div>`).join('')}</div></div><div class="legend">${['deadline','fixed','personal','work','proposal'].map((key,i)=>`<span><i class="${['','fixed','private','','ghost'][i]}"></i>${esc(t(key))}</span>`).join('')}</div>${snap.view.missing.length?`<details class="list"><summary>${esc(t('missing'))} · ${snap.view.missing.length}</summary>${snap.view.missing.map(row=>`<div class="row"><button data-task="${esc(row.id)}">${esc(snap.state.tasks.find(task=>task.id===row.id)?.title)}</button><small>${esc(t(row.reason))} · ${row.minutes/60} h</small></div>`).join('')}</details>`:''}`;
}
function checks(name,selected){return `<div class="weekchecks">${Array.from({length:7},(_,i)=>`<label class="check"><input type="checkbox" name="${name}" value="${i}" ${selected.includes(i)?'checked':''}>${weekday(i)}</label>`).join('')}</div>`;}
function settingsPage(){
  return `<div class="heading"><div><div class="eyebrow">LIFE COMES FIRST</div><h1>${esc(t('life'))}</h1><p class="subtitle">${esc(t('lifeNote'))}</p></div><button class="primary" data-cmd="add-event" data-write>＋ ${esc(t('addEvent'))}</button></div><div class="columns"><div><section class="paper card"><h2>${esc(t('fixed'))} & ${esc(t('personal'))}</h2>${snap.state.events.map(event=>`<div class="row"><button data-event="${esc(event.id)}">${event.category==='fixed'?'⌑':'☾'} ${esc(event.title)}<small>${time(event.start)}–${time(event.end%1440||1440)} · ${esc(t(event.repeat))}</small></button></div>`).join('')||`<p class="empty">${esc(t('empty'))}</p>`}</section><section class="paper card"><h2>${esc(t('prefs'))}</h2><form id="prefs-form"><label for="language">${esc(t('language'))}</label><select name="language" id="language">${languageOptions(language)}</select><p class="subtitle">${esc(t('workdayNote'))}</p>${checks('workdays',snap.state.workdays)}<button class="primary" data-write>${esc(t('save'))}</button></form><form id="policy-form"><label class="check"><input name="borrow_private" type="checkbox" value="yes" ${snap.state.borrow_private?'checked':''} data-write>${esc(t('borrow'))}</label><button data-write>${esc(t('save'))}</button></form>${snap.state.time_model==='custom'?`<hr><h3>${esc(t('windows'))}</h3><p class="subtitle">${esc(t('windowsNote'))}</p><button data-cmd="full-day" data-write>${esc(t('allDay'))}</button>`:''}${!snap.view.holidays_supported?`<p class="subtitle">${esc(t('unsupportedHolidays'))}</p>`:''}</section></div><div><section class="paper card"><h2>${esc(t('data'))}</h2><div class="form-actions"><a href="/api/export" data-download="backup">${esc(t('export'))}</a><a href="/api/offline" data-download="offline">${esc(t('snapshot'))}</a></div><p class="subtitle">${esc(t('snapshotNote'))}</p><form id="import-form"><label for="backup-file">JSON</label><input type="file" accept=".json,application/json" id="backup-file" data-write required><label class="check"><input type="checkbox" name="replace_confirm" value="yes" required data-write>${esc(t('importConfirm'))}</label><button data-write>${esc(t('import'))}</button></form></section><section class="paper card"><h2>${esc(t('security'))}</h2><form id="password-form"><label for="current-password">${esc(t('currentPassword'))}</label><input id="current-password" name="current" type="password" autocomplete="current-password" required maxlength="200" data-write><label for="new-password">${esc(t('newPassword'))}</label><input id="new-password" name="password" type="password" minlength="12" maxlength="200" autocomplete="new-password" required data-write><button data-write>${esc(t('changePassword'))}</button></form></section>${snap.user.is_admin?invitationPanel():''}</div></div>`;
}
function openBubble(html,anchor){
  const bubble=$('#bubble');bubble.innerHTML=`<button class="close" aria-label="${esc(t('close'))}">×</button><div class="error" role="alert" hidden></div>${html}`;bubble.hidden=false;
  const rect=anchor?.getBoundingClientRect()||{left:innerWidth/2,top:innerHeight/3,width:0,height:0};
  const x=Math.max(10,Math.min(innerWidth-bubble.offsetWidth-10,rect.left+rect.width/2-bubble.offsetWidth/2));
  const y=Math.max(10,Math.min(innerHeight-bubble.offsetHeight-12,rect.top+rect.height/2-30));
  bubble.style.left=`${x}px`;bubble.style.top=`${y}px`;bubble.style.setProperty('--origin',`${rect.left+rect.width/2-x}px ${rect.top+rect.height/2-y}px`);
  bubble.querySelector('.close').onclick=closeBubble;lockWrites();bubble.querySelector('.close').focus({preventScroll:true});
}
function closeBubble(){$('#bubble').hidden=true;$('#bubble').innerHTML='';}
const input=(key,label,value='',type='text',extra='')=>`<label for="field-${key}">${esc(t(label))}</label><input id="field-${key}" name="${key}" type="${type}" value="${esc(value)}" ${extra}>`;
function times(name,value=0){return `<select name="${name}">${Array.from({length:49},(_,i)=>`<option value="${time(i*30)}" ${i*30===value?'selected':''}>${time(i*30)}</option>`).join('')}</select>`;}
function fieldsFrom(form){const result={};for(const [key,value] of new FormData(form)){if(result[key]!==undefined)result[key]=[].concat(result[key],value);else result[key]=value;}return result;}
function editTask(task,anchor){
  task=task||{id:'',title:'',course:'',kind:'deadline',due:snap.view.today,start:'',minutes:60,important:true,target_minutes:600};
  const version=snap.version;
  openBubble(`<div class="eyebrow">A LITTLE THING ON YOUR MIND</div><h2>${esc(t(task.id?'edit':'addTask'))}</h2><form id="task-form"><input type="hidden" name="id" value="${esc(task.id)}">${input('title','title',task.title,'text','required maxlength="100"')}${input('course','course',task.course,'text','maxlength="60"')}<label>${esc(t('type'))}</label><select name="kind"><option value="deadline" ${task.kind==='deadline'?'selected':''}>${esc(t('deadline'))}</option><option value="goal" ${task.kind==='goal'?'selected':''}>${esc(t('goal'))}</option></select><div id="deadline-fields">${input('due','due',task.due||snap.view.today,'date')}${input('hours','hours',task.minutes/60||1,'number','min="0.5" max="1000" step="0.5"')}</div><div id="goal-fields">${input('target_hours','target',task.target_minutes/60||10,'number','min="0.5" max="1000" step="0.5"')}</div>${input('start','startDate',task.start,'date')}<label class="check"><input type="checkbox" name="important" value="yes" ${task.important?'checked':''}>${esc(t('isImportant'))}</label><button class="primary" data-write>${esc(t('save'))}</button></form>${task.id?`<div class="form-actions"><button class="danger" id="delete-task" data-write>${esc(t('remove'))}</button></div>`:''}`,anchor);
  const form=$('#task-form');const toggle=()=>{$('#deadline-fields').hidden=form.elements.kind.value!=='deadline';$('#goal-fields').hidden=form.elements.kind.value!=='goal';};form.elements.kind.onchange=toggle;toggle();
  form.onsubmit=event=>{event.preventDefault();const data=fieldsFrom(form);data.important=data.important||'no';change('save',data,version);};
  if($('#delete-task'))$('#delete-task').onclick=()=>{if(confirm(t('confirmDelete')))change('delete',{id:task.id},version);};
}
function taskBubble(id,anchor,block){
  const task=snap.state.tasks.find(task=>task.id===id);if(!task)return;const version=snap.version;
  const progress=snap.view.progress[id];
  openBubble(`<div class="eyebrow">${esc(task.course||t(task.kind==='goal'?'goal':'deadline'))}</div><h2>${esc(task.title)}</h2><p class="subtitle">${task.kind==='goal'?esc(t('goal')):`${esc(t('due'))} ${esc(task.due)} · ${task.minutes/60} h`}</p>${progress?`<p class="subtitle">${esc(t('invested'))} ${progress[0]/60} / ${progress[1]/60} h · ${Math.round(progress[2]*100)}%</p><p class="subtitle">${esc(t('goalNote'))}</p>`:''}<button class="quiet" id="edit-task" data-write>${esc(t('edit'))} ↗</button><hr><h3>${esc(t('effort'))}</h3><form id="progress-form"><label>${esc(t('actualStart'))}</label>${times('session_start',block?.start??snap.view.cutoff)}${input('actual','actual',.5,'number','min="0.5" max="24" step="0.5" required')}<label class="check"><input type="checkbox" name="finished" value="yes">${esc(t('finished'))}</label><p class="subtitle">${esc(t('effortNote'))}</p><button class="primary" data-write>${esc(t('record'))}</button></form>${block?`<details><summary>${esc(t('move'))}</summary><form id="move-form">${input('new_date','date',block.date,'date',`min="${snap.view.today}" max="${snap.view.days.at(-1).date}" required`)}<label>${esc(t('begin'))}</label>${times('new_start',block.start)}<button class="primary" data-write>${esc(t('moveSave'))}</button></form></details>`:''}`,anchor);
  $('#edit-task').onclick=()=>editTask(task,anchor);
  $('#progress-form').onsubmit=event=>{event.preventDefault();change('progress',{...fieldsFrom(event.target),id:task.id},version);};
  if(block)$('#move-form').onsubmit=event=>{event.preventDefault();change('move_block',{...fieldsFrom(event.target),id,source_date:block.date,source_start:time(block.start),source_end:time(block.end)},version);};
}
function editEvent(item,anchor){
  item=item||{id:'',title:'',category:'fixed',date:snap.view.today,start:540,end:600,repeat:'none',until:'',weekdays:[]};const version=snap.version;
  openBubble(`<div class="eyebrow">LIFE COMES FIRST</div><h2>${esc(t(item.id?'editSeries':'addEvent'))}</h2><form id="event-form"><input type="hidden" name="id" value="${esc(item.id)}">${input('title','title',item.title,'text','required maxlength="100"')}<label>${esc(t('type'))}</label><select name="category">${['fixed','private'].map(key=>`<option value="${key}" ${item.category===key?'selected':''}>${esc(t(key==='private'?'personal':key))}</option>`).join('')}</select>${input('date','date',item.date,'date','required')}<div class="form-grid"><div><label>${esc(t('begin'))}</label>${times('event_start',item.start)}</div><div><label>${esc(t('end'))}</label>${times('event_end',item.end>1440?item.end-1440:item.end)}</div></div><label>${esc(t('repeat'))}</label><select name="repeat">${['none','daily','weekly','monthly','workdays','holidays'].map(rule=>`<option value="${rule}" ${item.repeat===rule?'selected':''}>${esc(t(rule))}</option>`).join('')}</select><div id="weekly-days"><label>${esc(t('weekdays'))}</label>${checks('weekdays',item.weekdays)}</div>${input('until','until',item.until,'date')}<p class="subtitle">${esc(t('eventNote'))}</p><button class="primary" data-write>${esc(t('saveSeries'))}</button></form>${item.id?`<div class="form-actions"><button class="danger" id="delete-event" data-write>${esc(t('deleteSeries'))}</button></div>`:''}`,anchor);
  const form=$('#event-form');const toggle=()=>$('#weekly-days').hidden=form.elements.repeat.value!=='weekly';form.elements.repeat.onchange=toggle;toggle();
  form.onsubmit=event=>{event.preventDefault();change('save_event',fieldsFrom(form),version);};
  if(item.id)$('#delete-event').onclick=()=>{if(confirm(t('confirmDelete')))change('delete_event',{id:item.id},version);};
}
function eventBubble(block,anchor){
  const event=snap.state.events.find(event=>event.id===block.event_id);if(!event)return;const version=snap.version;
  openBubble(`<div class="eyebrow">${esc(t(event.category==='private'?'personal':'fixed'))}</div><h2>${esc(event.title)}</h2><p class="subtitle">${esc(block.date)} · ${time(block.start)}–${time(block.end)}</p><button id="edit-series" class="quiet" data-write>${esc(t('editSeries'))} ↗</button><hr><button id="cancel-once" class="danger" data-write>${esc(t('deleteOnce'))}</button>`,anchor);
  $('#edit-series').onclick=()=>editEvent(event,anchor);
  $('#cancel-once').onclick=()=>change('cancel_occurrence',{id:event.id,occurrence_date:block.occurrence_date},version);
}
function bind(){
  document.querySelectorAll('[data-tab]').forEach(el=>el.onclick=()=>{tab=el.dataset.tab;closeBubble();render();window.scrollTo(0,0);if(!embedded)history.replaceState(null,'',`/?tab=${tab}`);});
  document.querySelectorAll('[data-view-day]').forEach(el=>el.onclick=()=>{dayIndex=Number(el.dataset.viewDay);span='day';closeBubble();render();});
  document.querySelectorAll('[data-task]').forEach(el=>el.onclick=()=>taskBubble(el.dataset.task,el));
  document.querySelectorAll('[data-event]').forEach(el=>el.onclick=()=>editEvent(snap.state.events.find(item=>item.id===el.dataset.event),el));
  document.querySelectorAll('[data-cmd]').forEach(el=>el.onclick=()=>command(el.dataset.cmd,el));
  document.querySelectorAll('[data-block]').forEach(el=>{
    const block=JSON.parse(el.dataset.block);el.onclick=()=>{if(el.dataset.dragged==='yes'){delete el.dataset.dragged;return;}if(block._kind==='task')taskBubble(block.task_id,el,block);else if(block._kind==='fixed'||block._kind==='private')eventBubble(block,el);};
    if(!offline&&(block._kind==='task'||block._kind==='private')&&!el.classList.contains('destination'))drag(el,block);
  });
  if($('#prefs-form'))$('#prefs-form').onsubmit=event=>{event.preventDefault();const fields=fieldsFrom(event.target);fields.workdays=[].concat(fields.workdays||[]);change('save_settings',fields);};
  if($('#policy-form'))$('#policy-form').onsubmit=event=>{event.preventDefault();change('save_policy',fieldsFrom(event.target));};
  if($('#import-form'))$('#import-form').onsubmit=async event=>{event.preventDefault();const file=$('#backup-file').files[0];if(!file)return notify(t('fileRequired'));if(file.size>8_000_000)return notify(t('fileTooLarge'));const version=snap.version;const text=await file.text();change('import_data',{backup_json:text,replace_confirm:'yes'},version);};
  if($('#password-form'))$('#password-form').onsubmit=event=>accountAction(event,'/api/password',true);
  document.querySelectorAll('[data-invite-action]').forEach(el=>el.onclick=()=>invitationAction(el.dataset.inviteAction,el.dataset.inviteId));
  if($('#issued-code'))$('#issued-code').onfocus=event=>event.target.select();
  document.querySelectorAll('[data-download]').forEach(el=>el.onclick=event=>{if(offline){event.preventDefault();notify(t('readOnly'));}});
}
async function accountAction(event,path,logout){event.preventDefault();if(offline||busy)return;busy=true;lockWrites();try{await api(path,fieldsFrom(event.target));event.target.reset();if(logout){authEpoch++;clearCache();snap=null;render();}notify(t(logout?'passwordChanged':'created'));}catch(error){notify(error.message);}finally{busy=false;lockWrites();}}
async function command(cmd,anchor){
  if(cmd==='refresh')return sync(true);
  if(cmd==='logout'){if(offline)return;authEpoch++;try{await api('/api/logout',{});snap=null;clearCache();closeBubble();render();}catch(error){notify(error.message);}return;}
  if(cmd==='add-task')return editTask(null,anchor);
  if(cmd==='add-event')return editEvent(null,anchor);
  if(cmd==='zoom-in')zoom=Math.min(2,zoom+.25);
  if(cmd==='zoom-out')zoom=Math.max(.75,zoom-.25);
  if(cmd==='span-day')span='day';if(cmd==='span-week')span='week';
  if(cmd==='today'){dayIndex=0;}
  if(cmd==='prev-day'){dayIndex=Math.max(0,dayIndex-1);span='day';}
  if(cmd==='next-day'){dayIndex=Math.min(6,dayIndex+1);span='day';}
  if(cmd==='show-proposal')showProposal=!showProposal;
  if(cmd==='accept'||cmd==='keep')return change(cmd==='accept'?'confirm_move':'keep_plan',{revision:snap.state.proposal.id});
  if(cmd==='full-day')return change('full_day',{});
  render();
}
function drag(el,block){
  el.addEventListener('pointerdown',event=>{
    if(event.button!==0||offline||busy)return;
    const startX=event.clientX,startY=event.clientY,rect=el.getBoundingClientRect(),offsetY=event.clientY-rect.top,version=snap.version;
    let active=false,target=null,timer=null;
    const activate=()=>{active=true;el.setPointerCapture(event.pointerId);el.classList.add('dragging');};
    if(event.pointerType==='touch')timer=setTimeout(activate,400);
    function move(e){
      if(!active){if(Math.hypot(e.clientX-startX,e.clientY-startY)>7){clearTimeout(timer);if(event.pointerType!=='touch')activate();}else return;}
      if(!active)return;e.preventDefault();el.style.pointerEvents='none';const col=document.elementFromPoint(e.clientX,e.clientY)?.closest('.day-col');el.style.pointerEvents='';
      if(col){const colRect=col.getBoundingClientRect();const begin=Math.round((e.clientY-colRect.top-offsetY)/colRect.height*48)*30;target={new_date:col.dataset.date,new_start:time(Math.max(0,Math.min(1410,begin)))};el.style.transform=`translate(${e.clientX-startX}px,${e.clientY-startY}px)`;}
      const wrap=$('.calendar-wrap'),r=wrap.getBoundingClientRect();if(e.clientY<r.top+70)wrap.scrollTop-=10;else if(e.clientY>r.bottom-35)wrap.scrollTop+=10;
    }
    function end(e){clearTimeout(timer);el.removeEventListener('pointermove',move);el.removeEventListener('pointerup',end);el.removeEventListener('pointercancel',abort);el.style.transform='';el.classList.remove('dragging');if(active){el.dataset.dragged='yes';try{el.releasePointerCapture(event.pointerId);}catch{}}
      if(active&&target&&(target.new_date!==block.date||target.new_start!==time(block.start))&&e.type!=='pointercancel'){
        const fields=block._kind==='task'?{id:block.task_id,source_date:block.date,source_start:time(block.start),source_end:time(block.end),...target}:{id:block.event_id,occurrence_date:block.occurrence_date,...target};
        change(block._kind==='task'?'move_block':'move_event',fields,version);
      }
    }
    function abort(e){end(e);}
    el.addEventListener('pointermove',move,{passive:false});el.addEventListener('pointerup',end);el.addEventListener('pointercancel',abort);
  });
}
document.addEventListener('input',event=>{if(event.target.closest('form'))dirty=true;});
document.addEventListener('keydown',event=>{if(event.key==='Escape')closeBubble();});
document.addEventListener('pointerdown',event=>{if(!$('#bubble').hidden&&!$('#bubble').contains(event.target)&&!event.target.closest('[data-task],[data-block],[data-event],[data-cmd]'))closeBubble();});
document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible')sync();});
window.addEventListener('online',()=>sync());window.addEventListener('offline',()=>{if(!embedded)markOffline();});
setInterval(()=>{if(document.visibilityState==='visible')sync();},15000);
if(embedded){language=snap.state.language;render();}else{
  render();sync(true);
  if('serviceWorker'in navigator&&window.isSecureContext&&!/PlanwiseNAS/.test(navigator.userAgent))navigator.serviceWorker.register('/sw.js').catch(()=>{});
}
