// Шкала GAD-7 (Spitzer R.L. и др., Arch Intern Med, 2006; 166:1092–1097).
// Свободна для использования, разрешение не требуется (Pfizer, phqscreeners.com).
// ВНИМАНИЕ: русские формулировки ниже — черновой перевод с английского оригинала.
// Перед запуском замените их официальным русским переводом с phqscreeners.com.
(function (root) {
  const GAD7 = {
    stem: 'Как часто за последние 2 недели вас беспокоили следующие проблемы?',
    questions: [
      'Нервозность, тревога или ощущение, что вы на взводе',
      'Невозможность остановить беспокойство или управлять им',
      'Чрезмерное беспокойство по разным поводам',
      'Трудно расслабиться',
      'Такое сильное беспокойство, что трудно усидеть на месте',
      'Легко раздражаетесь или злитесь',
      'Страх, будто может случиться что-то ужасное'
    ],
    options: ['Ни разу', 'Несколько дней', 'Больше половины дней', 'Почти каждый день'],
    // Пороги из оригинальной статьи: 5, 10, 15 баллов.
    levels: [
      { min: 0, max: 4, label: 'минимальная тревога' },
      { min: 5, max: 9, label: 'лёгкая тревога' },
      { min: 10, max: 14, label: 'умеренная тревога' },
      { min: 15, max: 21, label: 'выраженная тревога' }
    ],
    score(answers) {
      if (!Array.isArray(answers) || answers.length !== 7) throw new Error('Нужно 7 ответов');
      if (!answers.every(a => Number.isInteger(a) && a >= 0 && a <= 3)) throw new Error('Ответ от 0 до 3');
      const total = answers.reduce((a, b) => a + b, 0);
      const level = GAD7.levels.find(l => total >= l.min && total <= l.max);
      return { total, label: level.label, seeSpecialist: total >= 10 };
    }
  };
  if (typeof module !== 'undefined') module.exports = GAD7;
  else root.GAD7 = GAD7;
})(this);
