(()=>{
'use strict';
const $=id=>document.getElementById(id), state={owner:false,userId:null,topic:null,subscriber:null,channel:null,generation:0,oldest:null,latest:0,loading:false,sending:false,requestId:null,requestBody:null,unread:{},offset:0,searchGeneration:0,lastMarked:0,readPending:false};
const box=$('messages');
async function api(path,options={}){
 const response=await fetch('/api/messages'+path,{credentials:'same-origin',cache:'no-store',...options,headers:{'Content-Type':'application/json',...(options.headers||{})}});
 if(!response.ok){let detail='Messages unavailable. Please try again.';try{const data=await response.json();if(typeof data.detail==='string')detail=data.detail;}catch{}
 if(response.status===401)detail='Your session expired. Sign in again.';throw Error(detail);}
 return response.json();
}
function url(){return '/'+state.topic+(state.subscriber?'?subscriber_id='+encodeURIComponent(state.subscriber):'');}
function nearBottom(){return box.scrollHeight-box.scrollTop-box.clientHeight<70;}
function badge(button,count){const old=button.querySelector('.badge');if(old)old.remove();if(count){const n=document.createElement('span');n.className='badge';n.textContent=count>99?'99+':String(count);button.append(n);}}
async function inbox(){const data=await api('/inbox');state.owner=data.owner;state.userId=data.user_id;state.unread=data.unread;
 $('ownerTools').hidden=!data.owner;$('private').hidden=data.owner;badge($('group'),data.unread.group);badge($('private'),data.unread['private:'+data.user_id]);
 document.querySelectorAll('[data-subscriber]').forEach(b=>badge(b,data.unread['private:'+b.dataset.subscriber]));return data;}
function draw(item){const node=document.createElement('article');node.className='message'+(item.mine?' mine':'')+(item.removed?' removed':'');node.dataset.id=String(item.id);
 const meta=document.createElement('div');meta.className='message-meta';const date=new Date(item.created_at);meta.textContent=item.sender+(item.owner?' · Owner':'')+' · '+date.toLocaleString([],{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'});
 const body=document.createElement('div');body.className='message-body';body.textContent=item.removed?'Message removed by owner':item.body;node.append(meta,body);
 if(state.owner&&!item.removed){const b=document.createElement('button');b.type='button';b.className='remove';b.textContent='Remove message';b.onclick=async()=>{if(!confirm('Remove this message from the conversation?'))return;b.disabled=true;try{await api('/items/'+item.id,{method:'DELETE'});await refresh();}catch(e){$('sendStatus').textContent=e.message;b.disabled=false;}};node.append(b);}return node;}
async function read(){if(!state.channel||!state.latest||state.lastMarked>=state.latest||state.readPending||document.hidden||!nearBottom())return;const generation=state.generation, path=url(), readId=state.latest;state.readPending=true;try{await api(path.replace('?', '/read?')+(path.includes('?')?'':'/read'),{method:'POST',body:JSON.stringify({last_read_id:readId})});if(generation===state.generation){state.lastMarked=readId;$('newMessage').hidden=true;await inbox();}}catch{/* Keep unread state until next successful poll. */}finally{if(generation===state.generation)state.readPending=false;}}
async function refresh(older=false){if(!state.topic||state.loading)return;state.loading=true;const generation=state.generation,path=url(),wasBottom=nearBottom(),oldHeight=box.scrollHeight,oldTop=box.scrollTop;
 try{const data=await api(path+(older?(path.includes('?')?'&':'?')+'before='+state.oldest:''));if(generation!==state.generation)return;
 const nodes=data.messages.map(draw);
 if(older){box.prepend(...nodes);box.scrollTop=box.scrollHeight-oldHeight+oldTop;}else{
 // Preserve older loaded history while refreshing the latest window, including removals.
 if(state.latest && data.messages.length && data.messages[0].id>state.latest){box.replaceChildren();$('older').hidden=!data.has_more;}
 const ids=new Set(data.messages.map(m=>String(m.id)));box.querySelectorAll('.empty').forEach(n=>n.remove());
 box.querySelectorAll('[data-id]').forEach(n=>{if(ids.has(n.dataset.id))n.remove();});
 box.append(...nodes);if(wasBottom)box.scrollTop=box.scrollHeight;else box.scrollTop=oldTop;
 if(!data.messages.length&&!box.children.length){const empty=document.createElement('p');empty.className='empty';empty.textContent=state.topic==='group'?'Start a conversation in the lounge.':'No messages yet. Say hello.';box.append(empty);}
 state.latest=data.messages.at(-1)?.id||state.latest;
 }
 const first=box.querySelector('[data-id]');state.oldest=first?Number(first.dataset.id):null;
 // Keep the older button after a latest refresh if older history was loaded.
 if(older||box.querySelectorAll('[data-id]').length<=50)$('older').hidden=!data.has_more;
 state.channel=data.channel;$('connection').textContent='Connected · refreshes every 10s';$('notice').textContent=state.topic==='group'?'Subscriber lounge · Messages are visible to eligible members.':'Private conversation · Visible only to this subscriber and the BXK owner.';$('notice').classList.remove('error');
 if(!older){$('newMessage').hidden=wasBottom;await read();}
 }catch(e){if(generation===state.generation){$('connection').textContent='Reconnecting';$('notice').textContent=e.message;$('notice').classList.add('error');}}
 finally{if(generation===state.generation)state.loading=false;}
}
async function choose(topic,subscriber=null,name=''){
 if(state.sending)return;
 if($('body').value.trim()&&!confirm('Discard your unsent draft and switch conversations?'))return;
 state.generation++;state.topic=topic;state.subscriber=subscriber;state.channel=null;state.oldest=null;state.latest=0;state.lastMarked=0;state.readPending=false;state.loading=false;state.requestId=null;state.requestBody=null;
 box.replaceChildren();$('body').value='';$('counter').textContent='0 / 4,000 · Ctrl+Enter to send';$('sendStatus').textContent='';$('older').hidden=true;$('body').disabled=false;$('send').disabled=false;
 $('title').textContent=topic==='group'?'Subscriber lounge':state.owner?name:'Message the owner';$('description').textContent=topic==='group'?'Community conversation':'Private two-way conversation';
 document.querySelectorAll('.active').forEach(b=>b.classList.remove('active'));if(topic==='group')$('group').classList.add('active');else if(!state.owner)$('private').classList.add('active');else document.querySelectorAll('[data-subscriber]').forEach(b=>{if(b.dataset.subscriber===subscriber)b.classList.add('active');});await refresh();
}
async function subscribers(reset=false){if(!state.owner)return;const generation=++state.searchGeneration;if(reset)state.offset=0;const offset=state.offset;
 try{const data=await api('/subscribers?q='+encodeURIComponent($('search').value)+'&offset='+offset);if(generation!==state.searchGeneration)return;if(reset)$('subscribers').replaceChildren();
 for(const u of data.subscribers){const b=document.createElement('button');b.type='button';b.className='subscriber';b.textContent=u.username+(u.active?'':' · inactive');b.dataset.subscriber=u.id;b.onclick=()=>choose('private',u.id,u.username);badge(b,state.unread['private:'+u.id]);$('subscribers').append(b);}
 if(reset&&!data.subscribers.length){const p=document.createElement('p');p.className='muted';p.textContent='No subscribers found.';$('subscribers').append(p);}state.offset=offset+data.subscribers.length;$('moreSubscribers').hidden=!data.has_more;
 }catch(e){$('notice').textContent=e.message;}}
$('group').onclick=()=>choose('group');$('private').onclick=()=>choose('private');$('older').onclick=()=>refresh(true);$('moreSubscribers').onclick=()=>subscribers();let searchTimer;$('search').oninput=()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>subscribers(true),250);};
$('body').oninput=()=>{$('counter').textContent=$('body').value.length+' / 4,000 · Ctrl+Enter to send';};
$('body').onkeydown=e=>{if((e.ctrlKey||e.metaKey)&&e.key==='Enter'){e.preventDefault();$('composer').requestSubmit();}};
$('composer').onsubmit=async e=>{e.preventDefault();const body=$('body').value.trim();if(!body||state.sending||!state.topic)return;
 // Reuse the id after an uncertain response so Retry cannot duplicate a send.
 if(state.requestBody!==body){state.requestId=crypto.randomUUID();state.requestBody=body;}state.sending=true;$('send').disabled=true;$('body').disabled=true;$('sendStatus').textContent='Sending…';
 try{await api(url(),{method:'POST',body:JSON.stringify({body,request_id:state.requestId})});$('body').value='';state.requestId=null;state.requestBody=null;$('sendStatus').textContent='Message sent.';$('counter').textContent='0 / 4,000 · Ctrl+Enter to send';box.scrollTop=box.scrollHeight;await refresh();}
 catch(e){$('sendStatus').textContent=e.message+' Your draft is saved here; retry to check or send it.';}
 finally{state.sending=false;$('send').disabled=false;$('body').disabled=false;$('body').focus();}};
box.addEventListener('scroll',()=>{if(nearBottom())read();});
setInterval(async()=>{if(document.hidden||state.sending)return;try{await inbox();await refresh();}catch{$('connection').textContent='Reconnecting';}},10000);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
(async()=>{try{await inbox();await subscribers(true);await choose(state.owner?'group':'private');}catch(e){$('notice').textContent=e.message;$('notice').classList.add('error');}})();
})();
