import assert from 'node:assert/strict';
import test from 'node:test';
import { totalCents } from './calculator.js';
test('multiplies unit prices by quantity', () => {
  assert.equal(totalCents([{priceCents:125,quantity:3},{priceCents:50,quantity:1}]),425);
});
test('empty basket costs zero', () => { assert.equal(totalCents([]),0); });
test('zero quantity contributes zero', () => {
  assert.equal(totalCents([{priceCents:299,quantity:0}]),0);
});
