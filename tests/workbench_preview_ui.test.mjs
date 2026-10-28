import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const source=fs.readFileSync(new URL('../static/workbench-preview.js',import.meta.url),'utf8');
class Element {
  constructor(tag){this.tag=tag;this.children=[];this.textContent='';}
  appendChild(node){this.children.push(node);}
  replaceChildren(){this.children=[];}
}
const context=vm.createContext({document:{createElement:tag=>new Element(tag)},Intl,Date});
vm.runInContext(source.slice(source.indexOf('  function automaticMove('),source.indexOf('  function populateMove('))+source.slice(source.indexOf('  function renderDryRun('),source.indexOf('  const analyze=')),context);
const now=Date.now();
const quote=(type,strike,bid,ask)=>({type,strike,bid,ask,fresh:true,timestamp:new Date(now).toISOString()});
const snapshot={expiration:'2026-10-28',quotes:[quote('call',7740,10,12),quote('put',7740,8,10),quote('call',7735,14,16),quote('put',7735,5,7)]};
assert.ok(Math.abs(context.automaticMove(snapshot,7739,'2026-10-28',now).value-25.066)<1e-9);
assert.equal(context.automaticMove(snapshot,7739,'2026-10-29',now),null);
assert.equal(context.automaticMove(snapshot,7800,'2026-10-28',now),null);
snapshot.quotes[0].timestamp=new Date(now-121000).toISOString();
assert.equal(context.automaticMove(snapshot,7739,'2026-10-28',now),null);
snapshot.quotes=snapshot.quotes.slice(1);
assert.equal(context.automaticMove(snapshot,7739,'2026-10-28',now),null);
const root=new Element('div');
context.renderDryRun(root,{passed:false,checks:[{passed:true,message:'Legs match'},{passed:false,message:'Reserve blocked'}],buying_power:{impact:1856.88,remaining:12949.2},fees:6.88,minimum_reserve:15000});
assert.equal(root.children[0].textContent,'Dry-run blocked · No order submitted');
assert.equal(root.children[1].children[0].textContent,'Reserve blocked');
assert.equal(root.children[2].children[5].textContent,'$12,949.20');
assert.equal(root.children[3].tag,'details');
assert.equal(root.children[3].open,undefined);
context.renderDryRun(root,{passed:true,checks:[{passed:true,message:'Verified'}]});
assert.equal(root.children[0].textContent,'Dry-run passed · No order submitted');
console.log('Workbench UI: automatic ATM move, stale/missing inputs, blocker priority, money formatting and collapsed checks passed.');
