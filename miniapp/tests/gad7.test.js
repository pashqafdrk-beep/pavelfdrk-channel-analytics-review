// Запуск: node --test miniapp/tests/
const test = require('node:test');
const assert = require('node:assert');
const GAD7 = require('../web/gad7.js');

test('7 вопросов и 4 варианта ответа', () => {
  assert.strictEqual(GAD7.questions.length, 7);
  assert.strictEqual(GAD7.options.length, 4);
});

test('пороги 5 / 10 / 15', () => {
  const at = total => {
    const a = [0, 0, 0, 0, 0, 0, 0];
    for (let i = 0; i < total; i++) a[i % 7]++;
    return GAD7.score(a);
  };
  assert.strictEqual(at(0).label, 'минимальная тревога');
  assert.strictEqual(at(4).label, 'минимальная тревога');
  assert.strictEqual(at(5).label, 'лёгкая тревога');
  assert.strictEqual(at(9).label, 'лёгкая тревога');
  assert.strictEqual(at(10).label, 'умеренная тревога');
  assert.strictEqual(at(14).label, 'умеренная тревога');
  assert.strictEqual(at(15).label, 'выраженная тревога');
  assert.strictEqual(at(21).total, 21);
  assert.strictEqual(at(9).seeSpecialist, false);
  assert.strictEqual(at(10).seeSpecialist, true);
});

test('неверные ответы отклоняются', () => {
  assert.throws(() => GAD7.score([0, 0, 0]));
  assert.throws(() => GAD7.score([0, 0, 0, 0, 0, 0, 4]));
  assert.throws(() => GAD7.score([0, 0, 0, 0, 0, 0, '1']));
});
