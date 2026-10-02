(() => {
  const tg = window.Telegram && window.Telegram.WebApp;
  const inTelegram = Boolean(tg && tg.initData);
  const screen = document.getElementById('screen');
  const state = { tab: 'videos', content: null, topic: 'Все', format: 'all', query: '', answers: [], admin: false, adminView: 'videos' };

  // Элементы строим через textContent: названия видео приходят извне.
  function h(tag, attrs = {}, ...children) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v === undefined || v === null || v === false) continue;
      if (k === 'class') el.className = v;
      else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? '' : v);
    }
    for (const c of children.flat()) if (c !== null && c !== undefined && c !== false) el.append(c.nodeType ? c : String(c));
    return el;
  }

  function toast(text) {
    const t = document.getElementById('toast');
    t.textContent = text; t.classList.add('show');
    clearTimeout(toast.timer); toast.timer = setTimeout(() => t.classList.remove('show'), 2200);
  }

  async function api(path, body) {
    const headers = { 'Content-Type': 'application/json' };
    if (inTelegram) headers['X-Telegram-Init-Data'] = tg.initData;
    const res = await fetch('api/' + path, body === undefined ? { headers } : { method: 'POST', headers, body: JSON.stringify(body) });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || 'Ошибка сервера');
    return data;
  }
  const track = (event, item) => api('event', { event, item }).catch(() => {});

  function openLink(url) {
    if (!url) return;
    if (inTelegram && /^https:\/\/t\.me\//.test(url)) tg.openTelegramLink(url);
    else if (inTelegram) tg.openLink(url);
    else window.open(url, '_blank', 'noopener');
  }

  const fmtDuration = s => {
    const hh = Math.floor(s / 3600), mm = Math.floor(s % 3600 / 60), ss = String(s % 60).padStart(2, '0');
    return hh ? `${hh}:${String(mm).padStart(2, '0')}:${ss}` : `${mm}:${ss}`;
  };
  const fmtAgo = iso => {
    const days = Math.floor((Date.now() - new Date(iso + 'T00:00:00')) / 864e5);
    if (days < 1) return 'сегодня';
    if (days < 30) return `${days} дн. назад`;
    if (days < 365) return `${Math.floor(days / 30)} мес. назад`;
    return `${Math.floor(days / 365)} г. назад`;
  };

  function videoCard(v) {
    const url = v.format === 'shorts' ? `https://www.youtube.com/shorts/${v.id}` : `https://www.youtube.com/watch?v=${v.id}`;
    return h('a', { class: 'card', href: url, onclick: e => { e.preventDefault(); track('video_click', v.id); openLink(url); } },
      h('div', { class: 'thumb' },
        v.thumbnail && h('img', { src: v.thumbnail, alt: '', loading: 'lazy' }),
        v.pinned ? h('span', { class: 'badge left' }, 'Важное') : null,
        h('span', { class: 'badge' }, v.format === 'shorts' ? 'Shorts' : fmtDuration(v.duration))),
      h('div', { class: 'card-body' },
        h('div', { class: 'card-title' }, v.title),
        h('div', { class: 'muted' }, `${v.topic} · ${fmtAgo(v.published)}`)));
  }

  // Вкладка «Материалы»
  function renderVideos() {
    const { topics, videos } = state.content;
    const q = state.query.trim().toLowerCase();
    const list = videos.filter(v =>
      (state.topic === 'Все' || v.topic === state.topic) &&
      (state.format === 'all' || v.format === state.format) &&
      (!q || v.title.toLowerCase().includes(q)));
    const listEl = h('div', { class: 'list' }, list.length ? list.map(videoCard)
      : h('div', { class: 'empty' }, videos.length ? 'Ничего не нашлось. Попробуйте другую тему.' : 'Видео скоро появятся.'));
    const search = h('input', { class: 'search', type: 'search', placeholder: 'Поиск по названию', value: state.query,
      oninput: e => { state.query = e.target.value; const pos = e.target.selectionStart; render(); const s = screen.querySelector('.search'); s.focus(); s.setSelectionRange(pos, pos); } });
    const chip = (label, on, click) => h('button', { class: 'chip' + (on ? ' on' : ''), onclick: click }, label);
    return [
      h('h1', {}, 'Материалы'),
      search,
      h('div', { class: 'chips' }, ['Все', ...topics].map(t => chip(t, state.topic === t, () => { state.topic = t; render(); }))),
      h('div', { class: 'chips' }, [['all', 'Все форматы'], ['video', 'Видео'], ['shorts', 'Shorts']]
        .map(([k, label]) => chip(label, state.format === k, () => { state.format = k; render(); }))),
      listEl
    ];
  }

  // Вкладка «Тест»
  function renderTest() {
    const a = state.answers;
    if (a.length === 0 && !state.testStarted) {
      return [
        h('h1', {}, 'Тест на тревогу'),
        h('p', {}, 'Шкала GAD-7. Семь вопросов о последних двух неделях. Займёт около минуты.'),
        h('p', { class: 'muted' }, 'Ответы остаются на вашем телефоне. Мы их не сохраняем и не передаём.'),
        h('button', { class: 'btn wide', onclick: () => { state.testStarted = true; render(); } }, 'Начать')
      ];
    }
    if (a.length < GAD7.questions.length) {
      const i = a.length;
      return [
        h('p', { class: 'muted' }, GAD7.stem),
        h('div', { class: 'muted' }, `Вопрос ${i + 1} из ${GAD7.questions.length}`),
        h('div', { class: 'progress' }, h('i', { style: `width:${i / GAD7.questions.length * 100}%` })),
        h('p', { class: 'question' }, GAD7.questions[i]),
        GAD7.options.map((label, value) => h('button', { class: 'option', onclick: () => {
          a.push(value);
          if (tg && tg.HapticFeedback) tg.HapticFeedback.selectionChanged();
          if (a.length === GAD7.questions.length) track('test_done');
          render();
        } }, label)),
        i > 0 && h('button', { class: 'btn ghost', onclick: () => { a.pop(); render(); } }, 'Назад')
      ];
    }
    const r = GAD7.score(a);
    const anxiety = state.content.videos.filter(v => v.topic === 'Тревога').slice(0, 5);
    return [
      h('h1', {}, 'Ваш результат'),
      h('div', { class: 'result' },
        h('div', { class: 'score' }, `${r.total} из 21`),
        h('div', {}, r.label[0].toUpperCase() + r.label.slice(1)),
        h('div', { class: 'note' }, 'Это не диагноз. Тест показывает, насколько сильно тревога мешала вам последние две недели.'),
        r.seeSpecialist && h('div', { class: 'note' }, 'При таком результате имеет смысл показаться специалисту: психотерапевту или психиатру. Это обычный шаг, а не признак того, что с вами «что-то не так».')),
      anxiety.length ? [h('h2', {}, 'Видео для вас'), h('div', { class: 'list' }, anxiety.map(videoCard))] : null,
      h('p', {}, h('button', { class: 'btn ghost wide', onclick: () => { state.answers = []; state.testStarted = false; render(); } }, 'Пройти заново'))
    ];
  }

  // Вкладка «Книги»
  function renderBooks() {
    return [
      h('h1', {}, 'Книги'),
      h('div', { class: 'list' }, state.content.books.map(b => h('div', { class: 'card book' },
        b.cover ? h('img', { class: 'cover', src: b.cover, alt: '' }) : h('div', { class: 'cover' }, b.title),
        h('div', {},
          h('div', { class: 'card-title' }, b.title),
          h('p', { class: 'muted' }, b.description),
          b.link ? h('button', { class: 'btn', onclick: () => { track('book_click', String(b.id)); openLink(b.link); } }, 'Купить')
                 : h('span', { class: 'muted' }, 'Ссылка скоро появится')))))
    ];
  }

  // Вкладка «Об авторе»
  function renderAbout() {
    const t = state.content.texts;
    return [
      h('div', { class: 'about-head' },
        t.about_photo ? h('img', { class: 'avatar', src: t.about_photo, alt: '' }) : h('div', { class: 'avatar' }, 'ПФ'),
        h('div', {}, h('h1', {}, t.about_name), h('div', { class: 'muted' }, t.about_role))),
      h('p', { style: 'white-space:pre-line' }, t.about_text),
      h('div', { class: 'row' },
        t.youtube_url && h('button', { class: 'btn', onclick: () => openLink(t.youtube_url) }, 'YouTube'),
        t.telegram_url && h('button', { class: 'btn ghost', onclick: () => openLink(t.telegram_url) }, 'Телеграм-канал')),
      h('p', {}, h('a', { href: 'privacy.html', class: 'muted' }, 'Конфиденциальность'))
    ];
  }

  // Админка: показывается только после подтверждения сервером
  function renderAdmin() {
    const views = [['videos', 'Видео'], ['books', 'Книги и тексты'], ['stats', 'Статистика']];
    const body = h('div', {}, h('div', { class: 'empty' }, 'Загрузка…'));
    const loaders = { videos: adminVideos, books: adminBooks, stats: adminStats };
    loaders[state.adminView]().then(nodes => body.replaceChildren(...nodes)).catch(e => body.replaceChildren(h('div', { class: 'empty' }, e.message)));
    return [
      h('h1', {}, 'Админка'),
      h('div', { class: 'chips' }, views.map(([k, label]) => h('button', { class: 'chip' + (state.adminView === k ? ' on' : ''), onclick: () => { state.adminView = k; render(); } }, label))),
      body
    ];
  }

  async function adminVideos() {
    const { topics, videos } = await api('admin/videos');
    const save = async (id, patch) => { try { await api('admin/video', { id, ...patch }); toast('Сохранено'); await loadContent(); } catch (e) { toast(e.message); } };
    return [
      h('div', { class: 'row' }, h('button', { class: 'btn', onclick: async e => {
        e.target.disabled = true; e.target.textContent = 'Обновляю…';
        try { const r = await api('admin/refresh', {}); toast(r.ok ? `Загружено видео: ${r.count}` : r.error); await loadContent(); render(); }
        catch (err) { toast(err.message); e.target.disabled = false; }
      } }, 'Обновить с YouTube')),
      h('p', { class: 'muted' }, `Всего видео: ${videos.length}`),
      h('div', { class: 'list' }, videos.map(v => {
        const hiddenBtn = h('button', { class: 'toggle' + (v.hidden ? ' on' : ''), onclick: () => { v.hidden = !v.hidden; hiddenBtn.classList.toggle('on'); save(v.id, { hidden: v.hidden }); } }, 'Скрыто');
        const pinBtn = h('button', { class: 'toggle' + (v.pinned ? ' on' : ''), onclick: () => { v.pinned = !v.pinned; pinBtn.classList.toggle('on'); save(v.id, { pinned: v.pinned }); } }, 'Закреплено');
        const select = h('select', { onchange: e => save(v.id, { topic: e.target.value }) }, topics.map(t => h('option', { value: t, selected: t === v.topic }, t)));
        return h('div', { class: 'card admin-item' },
          h('div', { class: 'card-title' }, v.title),
          h('div', { class: 'muted' }, `${v.format === 'shorts' ? 'Shorts' : 'Видео'} · ${v.published}${v.topic_manual ? ' · тема вручную' : ''}`),
          select, h('div', { class: 'row' }, hiddenBtn, pinBtn));
      }))
    ];
  }

  async function adminBooks() {
    const { books, texts } = await api('admin/books');
    const field = (label, value, onsave, multiline) => {
      const input = h(multiline ? 'textarea' : 'input', { rows: multiline ? 4 : null });
      input.value = value;
      input.addEventListener('change', async () => { try { await onsave(input.value); toast('Сохранено'); await loadContent(); } catch (e) { toast(e.message); } });
      return h('div', {}, h('label', {}, label), input);
    };
    const textLabels = { about_name: 'Имя', about_role: 'Кто вы', about_text: 'Текст об авторе', about_photo: 'Фото (ссылка https://)', youtube_url: 'Ссылка на YouTube', telegram_url: 'Ссылка на Телеграм-канал (https://t.me/...)' };
    return [
      h('h2', {}, 'Книги'),
      books.map(b => h('div', { class: 'card admin-item' },
        field('Название', b.title, v => api('admin/book', { id: b.id, title: v })),
        field('Описание', b.description, v => api('admin/book', { id: b.id, description: v }), true),
        field('Обложка (ссылка https://)', b.cover, v => api('admin/book', { id: b.id, cover: v })),
        field('Где купить (ссылка https://)', b.link, v => api('admin/book', { id: b.id, link: v })),
        field('Порядок', String(b.position), v => api('admin/book', { id: b.id, position: parseInt(v, 10) || 0 })))),
      h('h2', {}, 'Об авторе'),
      h('div', { class: 'card admin-item' }, Object.entries(textLabels).map(([k, label]) =>
        field(label, texts[k] || '', v => api('admin/text', { key: k, value: v }), k === 'about_text')))
    ];
  }

  async function adminStats() {
    const s = await api('admin/stats');
    const sum = ev => s.by_day.filter(r => r.event === ev).reduce((a, r) => a + r.count, 0);
    const names = { open: 'Открытия', video_click: 'Клики по видео', test_done: 'Тест пройден', book_click: 'Клики по книгам' };
    const days = [...new Set(s.by_day.map(r => r.day))].reverse();
    return [
      h('p', { class: 'muted' }, `За ${s.days} дней. Последнее обновление видео: ${s.last_refresh}`),
      h('div', { class: 'stat-grid' }, Object.entries(names).map(([k, label]) => h('div', { class: 'stat' }, h('b', {}, sum(k)), h('span', { class: 'muted' }, label)))),
      h('h2', {}, 'Самые открываемые видео'),
      s.top_videos.length ? h('div', { class: 'list' }, s.top_videos.map(v => h('div', { class: 'card admin-item' }, h('div', {}, v.title || v.id), h('div', { class: 'muted' }, `${v.count} кликов`))))
        : h('p', { class: 'muted' }, 'Пока нет данных'),
      h('h2', {}, 'По дням'),
      days.length ? h('div', { class: 'list' }, days.map(d => h('div', { class: 'card admin-item' }, h('b', {}, d),
        h('div', { class: 'muted' }, Object.entries(names).map(([k, label]) => `${label}: ${(s.by_day.find(r => r.day === d && r.event === k) || { count: 0 }).count}`).join(' · ')))))
        : h('p', { class: 'muted' }, 'Пока нет данных')
    ];
  }

  const renderers = { videos: renderVideos, test: renderTest, books: renderBooks, about: renderAbout, admin: renderAdmin };

  function render() {
    document.querySelectorAll('.tabbar button').forEach(b => b.classList.toggle('active', b.dataset.tab === state.tab));
    if (!state.content) { screen.replaceChildren(h('div', { class: 'empty' }, state.error || 'Загрузка…')); return; }
    screen.replaceChildren(...[renderers[state.tab]()].flat(3).filter(Boolean));
  }

  function setTab(tab) {
    if (tab === state.tab) return;
    state.tab = tab;
    screen.style.animation = 'none'; void screen.offsetWidth; screen.style.animation = '';
    window.scrollTo(0, 0);
    if (tg && tg.HapticFeedback) tg.HapticFeedback.selectionChanged();
    render();
  }

  async function loadContent() {
    state.content = await api('content');
  }

  document.querySelectorAll('.tabbar button').forEach(b => b.addEventListener('click', () => setTab(b.dataset.tab)));

  if (inTelegram) {
    document.documentElement.classList.add('tg');
    tg.ready();
    tg.expand();
    const mobile = ['android', 'ios'].includes(tg.platform);
    if (mobile && tg.isVersionAtLeast('8.0')) { try { tg.requestFullscreen(); } catch (e) {} }
    if (tg.isVersionAtLeast('7.7')) { try { tg.disableVerticalSwipes(); } catch (e) {} }
    try { tg.setHeaderColor('secondary_bg_color'); } catch (e) {}
  }

  render();
  loadContent()
    .then(() => { render(); track('open'); })
    .catch(() => { state.error = 'Не удалось загрузить материалы. Проверьте интернет и откройте снова.'; render(); });

  if (inTelegram) {
    api('admin/me').then(() => {
      state.admin = true;
      document.querySelector('[data-tab="admin"]').hidden = false;
    }).catch(() => {});
  }
})();
