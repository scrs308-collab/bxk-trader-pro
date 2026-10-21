import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const source = readFileSync('static/system-settings.js', 'utf8').replace('export function', 'function');
const elements = new Map();
for (const [id, value] of Object.entries({bxkMaxOrderRisk:'25000', bxkMinOrderCredit:'1', bxkMinBuyingPower:'5000', bxkSaveRiskButton:'', bxkSaveSettingsButton:'', bxkRiskSaveStatus:'', bxkSettingsStatus:''})) {
  elements.set(id, {value, checkValidity:()=>true});
}
let saved = {risk:{max_order_risk:7500,min_order_credit:1,min_remaining_buying_power:5000}};
let fail = false;
const ctx = vm.createContext({document:{getElementById:id=>elements.get(id)},console,
 fetch:async (url, options)=>{
   if(options.method === 'POST') {
     const body=JSON.parse(options.body);
     assert.deepEqual(Object.keys(body), ['max_order_risk']);
     assert.equal(body.max_order_risk,25000);
     if(!fail) saved={risk:{...saved.risk,...body}};
   }
   return {ok:true,json:async()=>saved};
 }});
vm.runInContext(source,ctx);
vm.runInContext('currentSettings = '+JSON.stringify(saved),ctx);
await vm.runInContext('saveSystemSettings(true)',ctx);
assert.equal(saved.risk.max_order_risk,25000);
assert.match(elements.get('bxkRiskSaveStatus').textContent,/saved and verified/);
assert.equal(elements.get('bxkSaveRiskButton').disabled,false);
// A server that acknowledges a save but returns the old value must show an error.
saved.risk.max_order_risk=7500; fail=true;
vm.runInContext('currentSettings = '+JSON.stringify(saved),ctx);
await vm.runInContext('saveSystemSettings(true)',ctx);
assert.match(elements.get('bxkRiskSaveStatus').textContent,/did not retain/);
assert.equal(elements.get('bxkSaveRiskButton').disabled,false);
console.log('Risk settings save and read-back checks passed');
