import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
const moduleSource = readFileSync('static/order-status.js', 'utf8');
const { brokerOrderLifecycle } = await import(`data:text/javascript;base64,${Buffer.from(moduleSource).toString('base64')}`);
for (const status of ['Received', 'Live', 'Working', 'Cancel Requested', 'Partially Filled']) {
  assert.equal(brokerOrderLifecycle(status).state, 'pending');
  assert.equal(brokerOrderLifecycle(status).terminal, false);
}
assert.equal(brokerOrderLifecycle('Filled').state, 'filled');
for (const status of ['Rejected', 'Cancelled', 'Canceled', 'Expired']) {
  assert.equal(brokerOrderLifecycle(status).state, 'failed');
  assert.equal(brokerOrderLifecycle(status).terminal, true);
}
assert.equal(brokerOrderLifecycle('unrecognized').state, 'submitted');
// Exercise the actual polling code: a verified working order must still be polled,
// partial fills must stay pending, and no submission request may be made.
const source = readFileSync('static/best-trade.js', 'utf8');
const pollingCode = source.slice(source.indexOf('  let submittedOrderId = null;'), source.indexOf('  confirmButton?.addEventListener(', source.indexOf('  let submittedOrderId = null;')));
const elements = new Map();
const element = id => {
  if (!elements.has(id)) elements.set(id, {hidden:true, dataset:{}, textContent:'', addEventListener(){}});
  return elements.get(id);
};
const queue = ['Partially Filled', 'Filled'];
const calls = [];
const sandbox = {
  overlay: {isConnected:true, querySelector:element},
  confirmButton: {disabled:true, textContent:''}, submissionReadiness:{},
  brokerOrderLifecycle, formatMoney:x=>String(x), updateReadinessCard(){}, setBrokerMessage(){},
  window:{setTimeout:resolve=>resolve()}, AbortSignal, console,
  fetch: async url => {calls.push(url); return {ok:true,json:async()=>({status:'RECONCILED',broker_status:queue.shift(),filled_quantity:1})};},
};
vm.createContext(sandbox);
await vm.runInContext(pollingCode + '\nreconcileSubmittedOrder("123", {status:"RECONCILED",broker_status:"Live"});', sandbox);
assert.equal(element('#orderLifecycle').dataset.state,'filled');
assert.equal(sandbox.confirmButton.textContent,'ORDER FILLED');
assert.equal(calls.length,2);
assert.ok(calls.every(url=>url.startsWith('/api/order-status?')));
assert.equal(sandbox.confirmButton.disabled,true);
console.log('Order lifecycle and working → partial → filled polling checks passed.');
