import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const fixtureUrl = new URL('../datasets/eval/shopflow-v1.json', import.meta.url);
const fixture = JSON.parse(await readFile(fixtureUrl, 'utf8'));
const source = await readFile(new URL(fixture.source_path, fixtureUrl), 'utf8');
const labels = new Set([
  'IN_SCOPE', 'POTENTIAL_SCOPE_ADDITION', 'CONFLICT', 'AMBIGUOUS', 'INSUFFICIENT_EVIDENCE',
]);
assert.equal(fixture.synthetic, true);
assert.equal(fixture.split, 'development', 'ShopFlow is not a held-out benchmark');
assert.equal(fixture.review_status, 'pending_human_review');
assert.equal(fixture.family_id, 'shopflow-checkout');
assert.equal(fixture.baseline_fixture_id, 'shopflow-b1');
assert.equal(fixture.requirements.length, 5);
assert.equal(fixture.cases.length, 15);
const requirements = new Map();
const spans = new Map();
for (const requirement of fixture.requirements) {
  assert.match(requirement.code, /^REQ-\d{3}$/);
  assert.ok(!requirements.has(requirement.code), 'Duplicate requirement');
  assert.ok(!spans.has(requirement.span_id), 'Duplicate evidence span');
  assert.ok(requirement.quote.length > 0);
  const line = `${requirement.code}: ${requirement.quote}`;
  assert.equal(source.split(line).length - 1, 1, `Unresolved source: ${requirement.code}`);
  requirements.set(requirement.code, requirement);
  spans.set(requirement.span_id, requirement);
}
const ids = new Set();
const inputs = new Set();
const counts = Object.fromEntries([...labels].map(label => [label, 0]));
for (const item of fixture.cases) {
  assert.match(item.id, /^SF-\d{3}$/);
  assert.ok(!ids.has(item.id), `Duplicate case: ${item.id}`);
  ids.add(item.id);
  assert.ok(item.input_text.trim().length > 0);
  assert.ok(!inputs.has(item.input_text.trim()), `Duplicate input: ${item.id}`);
  inputs.add(item.input_text.trim());
  assert.ok(labels.has(item.expected_class), `Invalid label: ${item.id}`);
  counts[item.expected_class]++;
  assert.ok(item.notes.trim().length > 0, `Missing rationale: ${item.id}`);
  assert.ok(Array.isArray(item.relevant_requirement_codes));
  assert.ok(Array.isArray(item.gold_evidence_span_ids));
  for (const field of ['relevant_requirement_codes', 'gold_evidence_span_ids']) {
    assert.equal(new Set(item[field]).size, item[field].length, `Duplicate reference: ${item.id}`);
  }
  for (const code of item.relevant_requirement_codes) {
    assert.ok(requirements.has(code), `Unknown requirement: ${item.id}`);
  }
  for (const spanId of item.gold_evidence_span_ids) {
    assert.ok(spans.has(spanId), `Unknown evidence: ${item.id}`);
    assert.ok(item.relevant_requirement_codes.includes(spans.get(spanId).code),
      `Evidence outside relevant requirements: ${item.id}`);
  }
  if (['IN_SCOPE', 'CONFLICT', 'POTENTIAL_SCOPE_ADDITION'].includes(item.expected_class)) {
    assert.ok(item.gold_evidence_span_ids.length > 0, `Unsupported proposal: ${item.id}`);
  }
}
assert.ok(Object.values(counts).every(count => count > 0), 'All five labels must be represented');
console.log(`Validated ${ids.size} synthetic development cases and ${spans.size} source anchors.`);
console.log(JSON.stringify(counts));
console.log('Structural validation only; labels await human review. No model evaluation was run.');
