import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
const source=readFileSync('static/best-trade.js','utf8');
const helpers=source.slice(source.indexOf('function normalizedStrategy'),source.indexOf('export async function loadBestTrade'));
const context=vm.createContext({});
vm.runInContext(helpers,context);
const leg={symbol:'SPXW_P7640',strike:7640,action:'BUY',option_type:'PUT'};
const trade={strategy:'Reverse Iron Condor',legs:[leg]};
test('rejects a regular credit condor returned for reverse condor',()=>{
  assert.throws(()=>context.assertReviewIdentity(trade,{order:{strategy:'SPX Iron Condor',legs:[leg]}}),/strategy differs/);
});
test('accepts identical strategy and contracts',()=>{
  context.assertReviewIdentity(trade,{order:{strategy:'reverse_iron_condor',legs:[{...leg}]}});
});
test('rejects changed contracts even with matching strategy',()=>{
  assert.throws(()=>context.assertReviewIdentity(trade,{order:{strategy:'Reverse Iron Condor',legs:[{...leg,strike:7645}]}}),/contracts differ/);
});
test('normalizes SPX credit strategy names',()=>{
  assert.equal(context.normalizedStrategy('SPX Iron Condor'),'iron_condor');
});
