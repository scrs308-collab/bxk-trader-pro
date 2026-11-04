import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';

const source = readFileSync('static/best-trade.js', 'utf8');
const safeNumber = (v, fallback = 0) => v == null || !Number.isFinite(Number(v)) ? fallback : Number(v);
const returnExpression = source.match(/formatNumber\((safeNumber\(trade\.max_profit,[\s\S]*?)\, 1\)/)[1];
const ratioExpression = source.match(/const riskReward =\s*([\s\S]*?);/)[1];
test('debit and credit return on risk use profit, not entry premium', () => {
  for (const [trade, credit, maxRisk, expected] of [
    [{max_profit:1400,debit:11},11,1100,127.2727272727],
    [{max_profit:1430,debit:10.7},10.7,1070,133.6448598131],
    [{},2,2300,8.6956521739],
  ]) {
    assert.ok(Math.abs(vm.runInNewContext(returnExpression,{trade,credit,maxRisk,safeNumber})-expected)<1e-8);
  }
});
test('risk 1 reward ratio points in the correct direction', () => {
  assert.equal(vm.runInNewContext(ratioExpression,{maxProfit:1400,maxRisk:1100}),1400/1100);
  assert.equal(vm.runInNewContext(ratioExpression,{maxProfit:1400,maxRisk:0}),0);
});
test('structure assessment takes priority over legacy scores', () => {
  const expression = source.match(/const missionScore = ([\s\S]*?);/)[1];
  const trade = {structure_analysis:{score:95},trade_quality_score:0};
  assert.equal(vm.runInNewContext(expression,{trade,data:{score:0},safeNumber}),95);
});
