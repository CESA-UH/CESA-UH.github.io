const app = document.querySelector('#app');
const modal = document.querySelector('#modal');
const state = { token: sessionStorage.getItem('hamdars-token'), user: null, courses: [], course: null, topics: [], view: 'dashboard', authMode: 'login', status: null, generation: 0, busy: false, threads: [], threadId: null, chatCourse: null };
const fa = value => value == null ? '—' : Number(value).toLocaleString('fa-IR');
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const date = value => value ? new Date(value).toLocaleDateString('fa-IR', { month:'short', day:'numeric', timeZone:'Asia/Tehran' }) : 'بدون گزارش';
const fullName = u => `${u.first_name} ${u.last_name}`;
const icons = {dashboard:'<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',report:'<path d="M8 4H5v17h14V4h-3M8 3h8v4H8zM8 12h8M8 16h5"/>',chat:'<path d="M21 11a8 8 0 0 1-8 8H8l-5 3v-5a8 8 0 1 1 18-6Z"/><path d="M8 10h8M8 14h5"/>',resources:'<path d="M12 5c-4-3-8-2-9-1v15c3-2 6-1 9 1 3-2 6-3 9-1V4c-2-1-5-2-9 1Zm0 0v15"/>',students:'<circle cx="9" cy="8" r="3"/><path d="M3 20v-3a6 6 0 0 1 12 0v3M16 4a3 3 0 0 1 0 6M17 14a5 5 0 0 1 4 5"/>',clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',trend:'<path d="m3 17 6-6 4 4 8-11M15 4h6v6"/>',leaf:'<path d="M20 3C8 3 3 7 5 14s15 3 15-11ZM5 20l9-10"/>',logout:'<path d="M9 4H4v16h5M13 8l4 4-4 4M8 12h13"/>',file:'<path d="M14 3H5v18h14V8l-5-5Zm0 0v5h5M8 12h8M8 16h6"/>',check:'<path d="m5 12 4 4L19 6"/>',arrow:'<path d="M19 12H5m6-6-6 6 6 6"/>'};
const icon = name => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || icons.leaf}</svg>`;
const brand = () => `<div class="brand"><span class="brand-icon">${icon('resources')}</span><span>هم‌درس</span></div>`;
const art = () => `<svg class="hero-art" viewBox="0 0 220 150" fill="none" aria-hidden="true"><circle cx="112" cy="75" r="63" stroke="#548ae0" stroke-dasharray="4 7"/><circle cx="112" cy="75" r="45" fill="#1c4180"/><path d="m61 63 47-16 51 16-49 19-49-19Z" fill="#dceaff"/><path d="M74 74v30c24 12 45 12 69 0V74l-33 13-36-13Z" fill="#8bb6ff"/><path d="M158 65v39" stroke="#dceaff" stroke-width="3"/><circle cx="158" cy="107" r="4" fill="#dceaff"/><path d="m48 32 4-10 4 10 10 4-10 4-4 10-4-10-10-4 10-4Z" fill="#8bb6ff"/><circle cx="178" cy="44" r="6" fill="#a78bfa"/><circle cx="55" cy="122" r="4" fill="#a78bfa"/></svg>`;

async function api(path, options = {}) {
  const headers = {...options.headers};
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  if (options.body && !(options.body instanceof FormData)) { headers['Content-Type'] = 'application/json'; options.body = JSON.stringify(options.body); }
  const response = await fetch(`/api${path}`, {...options, headers});
  const data = response.status === 204 ? null : await response.json();
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith('/auth/')) logout();
    const detail = Array.isArray(data.detail) ? data.detail.map(x => `${x.loc.at(-1)}: ${x.msg}`).join('\n') : data.detail;
    throw new Error(detail || 'درخواست انجام نشد. دوباره تلاش کنید.');
  }
  return data;
}
function toast(text) { const el = document.querySelector('#toast'); el.textContent = text; el.classList.add('visible'); clearTimeout(state.toastTimer); state.toastTimer = setTimeout(() => el.classList.remove('visible'), 4500); }
function logout() { clearReportPolling(); state.streamAbort?.abort(); state.threadId=null; state.chatCourse=null; state.generation++; state.token = null; state.user = null; state.course = null; state.siteCourseOpened=false; state.view='dashboard'; sessionStorage.removeItem('hamdars-token'); modal.close(); renderAuth(); }
function showModal(title, content) { modal.innerHTML = `<div class="modal-head"><h2>${esc(title)}</h2><button class="ghost" data-action="close-modal" aria-label="بستن">✕</button></div>${content}`; modal.showModal(); }
function topicOptions(optional = false) { return `${optional ? '<option value="">همهٔ مباحث</option>' : '<option value="" disabled selected>انتخاب مبحث</option>'}${state.topics.map(t => `<option value="${t.id}">${esc(t.name)}</option>`).join('')}`; }
function empty(title, text, action, label) { return `<div class="empty"><div class="empty-icon">${icon('leaf')}</div><h2>${esc(title)}</h2><p>${esc(text)}</p>${action ? `<button data-action="${action}">${esc(label)}</button>` : ''}</div>`; }
function stats(items) { return `<div class="grid stats">${items.map(([label,value,foot,ic]) => `<div class="stat"><div class="stat-label">${label}<span class="stat-icon">${icon(ic)}</span></div><strong>${value}</strong></div>`).join('')}</div>`; }
function sources(items) { return items.map((s,i) => `<button class="source-btn" data-action="source" data-resource="${s.resource_id}" data-page="${s.page}">[${fa(i+1)}] ${esc(s.title)} · صفحهٔ ${fa(s.page)} ↗</button>`).join(''); }
function skills(data) { return data.skills.length ? data.skills.map(s => `<div class="skill-row"><div class="skill-top"><span>${esc(s.name)}</span><span>${s.confidence_percent == null ? 'ثبت نشده' : fa(s.confidence_percent)+'٪'}</span></div><div class="bar ${s.needs_attention ? 'weak' : ''}"><span style="width:${s.confidence_percent ?? 0}%"></span></div><div class="skill-bottom"><span>${esc(s.difficulty)}</span><span>${s.updated_at ? date(s.updated_at) : ''}</span></div></div>`).join('') : '<p class="empty">استاد هنوز مبحثی تعریف نکرده است.</p>'; }
function strengthsView(data){return (data.strengths||[]).length ? '<h2>نقاط قوت</h2>'+data.strengths.map(s=>`<div class="skill-row"><strong>${esc(s.topic)}</strong><p>${esc(s.reason)}</p><span class="tag">${s.basis==='graded_quiz'?'بر اساس کوییز تصحیح‌شده':'بر اساس خوداظهاری'}</span></div>`).join('') : ''; }
function recommendations(data) { return data.recommendations.length ? data.recommendations.map((r,i) => `<div class="recommendation"><h3><span class="number">${fa(i+1)}</span>${esc(r.topic)}</h3><p>${esc(r.reason)}</p><p class="action">${esc(r.action)}</p>${r.reading_hint?`<p>${esc(r.reading_hint)}</p>`:''}${r.sources.map(source=>`<div class="reading-location">${sources([source])}<p class="reading-focus">${source.match==='topic_link'?'شروع مرور منبع مرتبط:':'بخش پیشنهادی از متن منبع:'} ${esc(source.focus || '')}</p>${source.original_url?`<a class="source-btn" href="${esc(source.original_url)}" target="_blank" rel="noopener noreferrer">باز کردن فایل اصلی در صفحهٔ ${fa(source.page)}</a>`:''}</div>`).join('')}${r.check?`<p class="muted">${esc(r.check)}</p>`:''}${!r.sources.length ? '<p>منبع مرتبط ثبت نشده</p>' : ''}</div>`).join('') : '<div class="empty">پیشنهادی ثبت نشده</div>'; }
function chart(data) { const max = Math.max(...data.trend.map(d => d.study_minutes), 30); return `<div class="chart">${data.trend.map(d => `<div class="chart-day"><span class="chart-value">${fa(d.study_minutes)}</span><div class="chart-bar" style="height:${Math.max(2,d.study_minutes/max*100)}%" title="${d.date}: ${d.study_minutes} دقیقه"></div></div>`).join('')}</div><div class="chart-labels">${data.trend.map(d => `<span>${new Date(d.date+'T12:00:00Z').toLocaleDateString('fa-IR',{weekday:'short',timeZone:'UTC'})}</span>`).join('')}</div>`; }
function reportsTable(data) { return data.reports.length ? `<div class="table-wrap"><table><thead><tr><th>مبحث</th><th>اطمینان</th><th>چالش</th><th>مطالعه</th><th>تاریخ</th><th>یادداشت</th></tr></thead><tbody>${data.reports.map(r => `<tr><td>${esc(r.topic)}</td><td>${fa(r.confidence)} از ۵</td><td><span class="tag ${r.difficulty === 'none' ? '' : 'amber'}">${esc(r.difficulty_label)}</span></td><td>${fa(r.study_minutes)} دقیقه</td><td>${date(r.created_at)}</td><td>${esc(r.note) || '—'}</td></tr>`).join('')}</tbody></table></div>` : '<p class="empty">هنوز خوداظهاری ثبت نشده است.</p>'; }

function renderAuth() {
  const register = state.authMode === 'register';
  app.innerHTML = `<div class="auth"><section class="auth-story">${brand()}<h1>دستیار استاد و دانشجو</h1>${art()}</section><section class="auth-content"><div class="auth-box">${themeControl()}<a href="/">← برنامهٔ عمومی دروس</a><h2>${register ? 'ساخت حساب' : 'ورود'}</h2><div class="tabs"><button data-action="auth-login" class="${!register?'active':''}">ورود</button><button data-action="auth-register" class="${register?'active':''}">ساخت حساب</button></div><form id="auth-form">${register ? '<div class="form-row"><div class="field"><label for="first_name">نام</label><input id="first_name" name="first_name" required maxlength="100" autocomplete="given-name"></div><div class="field"><label for="last_name">نام خانوادگی</label><input id="last_name" name="last_name" required maxlength="100" autocomplete="family-name"></div></div><div class="field"><label for="role">نقش شما</label><select id="role" name="role"><option value="student">دانشجو</option><option value="teacher">استاد</option></select></div>' : ''}<div class="field"><label for="email">ایمیل</label><input id="email" name="email" type="email" dir="ltr" placeholder="you@university.ac.ir" required autocomplete="email"></div><div class="field"><label for="password">رمز عبور</label><input id="password" name="password" type="password" dir="ltr" required minlength="8" maxlength="128" autocomplete="${register?'new-password':'current-password'}" placeholder="حداقل ۸ کاراکتر"></div><div class="error" role="alert"></div><button class="submit" type="submit">${register?'ساخت حساب':'ورود به هم‌درس'} ←</button></form><p class="auth-foot">خوداظهاری‌های درس برای استاد و حل‌تمرین‌های همان درس قابل مشاهده‌اند.<br>از خوداظهاری، پاسخ کوییز و گفت‌وگو، گزارش تحلیلی برای عوامل آموزشی همان درس تهیه می‌شود.</p></div></section></div>`;
}
async function initialize() {
  if (!state.token) return renderAuth();
  try { state.user = await api('/auth/me'); await loadCourses(); state.status = await api('/status'); await renderShell(); }
  catch (error) { logout(); toast(error.message); }
}
async function loadCourses(preferred) {
  const requested = await openRequestedSiteCourse();
  preferred = requested || preferred;
  state.courses = await api('/courses');
  state.course = state.courses.find(c => c.id === (preferred || state.course?.id)) || state.courses[0] || null;
  state.topics = state.course ? await api(`/courses/${state.course.id}/topics`) : [];
}
async function renderShell() {
  if (!state.user) return;
  const teacher = canEditCourse();
  const nav = teacher ? [['dashboard','نمای کلی کلاس'],['students','دانشجویان'],['learning-reports','گزارش‌های جامع'],['topics','مباحث ترم'],['forms','فرم‌های خوداظهاری'],['quizzes','کوییزها'],['resources','منابع'],['staff','دسترسی‌های درس']] : [['dashboard','داشبورد'],['topics','مباحث ترم'],['report','خوداظهاری'],['quizzes','کوییزها'],['chat','دستیار درس'],['resources','منابع']];
  if(state.user.role==='admin')nav.push(['admin-users','مدیریت کاربران']);
  app.innerHTML = `<div class="shell"><aside class="sidebar">${brand()}<div class="nav-label">فضای ${teacher?'آموزش':'یادگیری'}</div><nav class="nav">${nav.map(([v,l])=>`<button data-action="view" data-view="${v}" class="${state.view===v?'active':''}">${icon(v)}${l}</button>`).join('')}</nav><div class="sidebar-bottom"><div class="profile"><div class="avatar">${esc(state.user.first_name[0])}</div><div><strong>${esc(fullName(state.user))}</strong><div class="muted">${esc(courseRoleLabel())}</div></div><button class="ghost" data-action="logout" title="خروج" aria-label="خروج از حساب">${icon('logout')}</button></div></div></aside><main class="main"><header class="topbar"><div class="course-select"><span class="muted">درس فعال</span><select id="course-selector" aria-label="درس فعال">${state.courses.length ? state.courses.map(c=>`<option value="${c.id}" ${c.id===state.course?.id?'selected':''}>${esc(c.name)}</option>`).join('') : '<option>هنوز درسی ندارید</option>'}</select><button class="secondary small" data-action="${['teacher','admin'].includes(state.user.role)?'create-course':'join-course'}">${['teacher','admin'].includes(state.user.role)?'+ درس جدید':'+ عضویت'}</button></div><a href="/" class="secondary small">برنامهٔ عمومی دروس</a>${state.course?.site_key?`<a href="/docs-site/courses/${encodeURIComponent(state.course.site_key.split('-')[0])}/" class="secondary small">جلسات و ویرایش صفحهٔ درس</a>`:''}${themeControl()}<span class="date">${new Date().toLocaleDateString('fa-IR',{weekday:'long',day:'numeric',month:'long',year:'numeric',timeZone:'Asia/Tehran'})}</span></header><div id="view"><div class="loading">در حال دریافت اطلاعات…</div></div></main></div>`;
  await renderView();
}
async function renderView() {
  const el = document.querySelector('#view');
  clearReportPolling(); state.openLearningReport=null; state.streamAbort?.abort(); clearInterval(state.quizTimer); state.activeAttempt=null; const generation = ++state.generation;
  const isTeacher = canEditCourse();
  if(state.view==='admin-users' && state.user.role==='admin'){try{el.innerHTML=adminUsersView(await fetchAdminUsers());}catch(error){el.innerHTML=empty(error.message,'','retry','تلاش دوباره');}return;}
  if (!state.course) { const creator=['teacher','admin'].includes(state.user.role);el.innerHTML = empty('درسی ثبت نشده','',creator?'create-course':'join-course',creator?'ساخت درس':'وارد کردن کد درس'); return; }
  const cid = state.course.id;
  try {
    let html;
    if (state.view === 'dashboard') {
      const data = await api(`/courses/${cid}/${isTeacher?'students':'dashboard'}`);
      html = isTeacher ? teacherOverview(data) : studentOverview(data);
    } else if (state.view === 'report') {state.reportForms=await api(`/courses/${cid}/report-forms`);html=buildReportView();}
    else if(state.view==='learning-reports'){state.learningReportData=await api(`/courses/${cid}/learning-reports`);html=classLearningReportsView(state.learningReportData);}
    else if(state.view==='staff')html=staffView(await api(`/courses/${cid}/assistants`));
    else if(state.view==='forms')html=formsView(await api(`/courses/${cid}/report-forms`));
    else if(state.view==='quizzes')html=quizzesView(await api(`/courses/${cid}/quizzes`));
    else if(state.view==='topics'){const r=await api(`/courses/${cid}/resources`);html=semesterView(r,isTeacher?null:await api(`/courses/${cid}/dashboard`));}
    else if (state.view === 'students') { state.studentData = await api(`/courses/${cid}/students`); html = studentsView(state.studentData); }
    else if (state.view === 'resources') { const data = await api(`/courses/${cid}/resources`); html = resourcesView(data); }
    else if (state.view === 'chat') {
      state.threads = await api(`/courses/${cid}/chat/threads`);
      if(state.chatCourse!==cid || !state.threads.some(t=>t.id===state.threadId))state.threadId=state.threads[0]?.id||null;
      state.chatCourse=cid;
      const data=state.threadId?await api(`/courses/${cid}/chat/threads/${state.threadId}`):[]; html=chatView(data);
    }
    if (generation !== state.generation) return;
    el.innerHTML = html;
    if (state.view === 'learning-reports') pollClassReports(state.learningReportData);
    if (state.view === 'chat') scrollChat();
  } catch (error) { if (generation === state.generation) el.innerHTML = `<div class="panel"><p class="error">${esc(error.message)}</p><button data-action="retry">تلاش مجدد</button></div>`; }
}
function pageTitle(title, sub, action='') { return `<div class="page-title"><div><h1>${title}</h1></div>${action}</div>`; }
function studentOverview(d) {
  return pageTitle('داشبورد', '')+stats([['امتیاز خوداظهاری',d.average_confidence==null?'—':fa(d.average_confidence)+'٪','','trend'],['مباحث گزارش‌شده',fa(d.reported_topics)+' از '+fa(d.total_topics),'','resources'],['مباحث دارای چالش',fa(d.weak_topics),'','report'],['مطالعهٔ هفته',fa(d.study_minutes_week)+' دقیقه','','clock']])+`<div class="grid two-col"><section class="panel"><div class="panel-head"><h2>وضعیت مباحث</h2><button class="secondary small" data-action="view" data-view="topics">مباحث ترم</button></div>${skills(d)}${strengthsView(d)}</section><section class="panel"><div class="panel-head"><h2>پیشنهاد مطالعه</h2></div>${recommendations(d)}</section>${topicTrendsView(d.learning_trends)}<section class="panel wide"><div class="panel-head"><h2>خوداظهاری‌های اخیر</h2><button class="secondary small" data-action="view" data-view="report">+ خوداظهاری</button></div>${reportsTable(d)}</section></div>`;
}
function teacherOverview(d) {
  return pageTitle('نمای کلی کلاس','',`<span class="tag">کد عضویت: <b dir="ltr">${esc(state.course.join_code)}</b></span>`)+stats([['دانشجویان',fa(d.students.length),'','students'],['نیازمند پیگیری',fa(d.attention_count),'','report'],['گزارش‌دهندگان',fa(d.students.filter(s=>s.last_report_at).length),'','check'],['مباحث ترم',fa(state.topics.length),'','resources']])+`<div class="grid two-col"><section class="panel"><div class="panel-head"><h2>مباحث دارای چالش</h2></div>${d.topic_difficulties.map(t=>`<div class="skill-row"><div class="skill-top"><span>${esc(t.name)}</span><span>${fa(t.count)} دانشجو</span></div></div>`).join('')||'<p class="muted">گزارشی ثبت نشده</p>'}</section><section class="panel"><div class="panel-head"><h2>چالش‌ها</h2></div>${Object.entries(d.difficulty_counts).map(([name,count])=>`<div class="skill-top"><span>${esc(name)}</span><span>${fa(count)}</span></div>`).join('')||'<p class="muted">گزارشی ثبت نشده</p>'}</section><section class="panel wide"><div class="panel-head"><h2>دانشجویان نیازمند پیگیری</h2><button class="secondary small" data-action="view" data-view="students">همهٔ دانشجویان</button></div>${studentTable(d.students.filter(s=>s.needs_attention))}</section></div>`;
}
function studentTable(rows) {
  return rows.length ? `<div class="table-wrap"><table><thead><tr><th>دانشجو</th><th>اطمینان خوداظهاری</th><th>نیازمند توجه</th><th>استفاده از چت</th><th>آخرین گزارش</th><th>وضعیت</th><th></th></tr></thead><tbody>${rows.map(s=>`<tr><td><div class="student-name"><span class="avatar">${esc(s.student.first_name[0])}</span><span>${esc(fullName(s.student))}<small>${esc(s.student.email)}</small></span></div></td><td>${s.average_confidence == null?'—':fa(s.average_confidence)+'٪'}</td><td>${fa(s.weak_topics)} مبحث</td><td>${fa(s.chat_analysis?.question_count||0)} پرسش<small class="usage-sub">${esc(s.chat_analysis?.learning_status||'')}</small></td><td>${date(s.last_report_at)}</td><td><span class="tag ${s.needs_attention?'amber':''}">${esc(s.reason)}</span></td><td><button class="secondary small" data-action="student-detail" data-student="${s.student.id}">جزئیات ←</button></td></tr>`).join('')}</tbody></table></div>` : '<p class="empty">دانشجویی برای نمایش وجود ندارد.</p>';
}
function studentsView(d) { return pageTitle('پیگیری دانشجویان','مشاهدهٔ روند، چالش‌ها و یادداشت‌های هر دانشجو') + `<section class="panel"><div class="toolbar"><input id="student-search" class="search" placeholder="جست‌وجوی نام یا ایمیل…" aria-label="جست‌وجوی دانشجو"><label class="check-label"><input type="checkbox" id="attention-only">فقط نیازمند پیگیری</label><span class="tag">${fa(d.students.length)} دانشجو</span></div><div id="student-table">${studentTable(d.students)}</div></section>`; }
function resourcesView(rows) {
  const teacher = canEditCourse();
  return pageTitle('کتابخانهٔ درس','منابع مشترک کلاس، پایهٔ پاسخ‌های دستیار و پیشنهادهای مطالعه',teacher?'<button class="secondary" data-action="export-knowledge">دریافت کتابخانهٔ OKF</button> <button data-action="upload-resource">+ بارگذاری منبع</button>':'') +
    `<section class="panel" style="margin-bottom:22px"><div class="panel-head"><h2>مباحث درس</h2>${teacher?'<button class="secondary small" data-action="create-topic">+ مبحث جدید</button>':''}</div><button class="secondary small" data-action="view" data-view="topics">مشاهدهٔ مباحث ترم</button></section>`+
    (rows.length?`<div class="grid resource-grid">${rows.map(r=>`<article class="resource-card"><span class="file-icon">${icon('file')}</span><span class="tag" style="float:left">${fa(r.page_count)} صفحه</span><h3>${esc(r.title)}</h3><p>${esc(state.topics.find(t=>t.id===r.topic_id)?.name || 'منبع عمومی درس')}</p><p class="filename">${esc(r.filename)}</p><p>${fa(r.chunk_count)} بخش قابل جست‌وجو · ${date(r.created_at)}</p><button class="secondary small" data-action="source" data-resource="${r.id}" data-page="${r.first_page}">خواندن متن منبع ←</button></article>`).join('')}</div>`:empty('کتابخانه هنوز خالی است',teacher?'کتاب یا جزوه را بارگذاری کن و در صورت امکان آن را به یک مبحث مرتبط کن.':'پس از بارگذاری کتاب و جزوه توسط استاد، منابع اینجا نمایش داده می‌شوند.',teacher?'upload-resource':null,'بارگذاری اولین منبع'))+
    `<div class="notice">PDF متنی، TXT و Markdown تا ${fa((state.status?.max_upload_bytes || 104857600)/1048576)} مگابایت و PDF تا ${fa(state.status?.max_resource_pages || 3000)} صفحه پشتیبانی می‌شوند. PDF تصویری به OCR نیاز دارد.</div>`;
}
function messageHTML(m) { return `<div class="message ${m.role==='user'?'user':'assistant'}"><span class="message-label">${m.role==='user'?'شما':m.mode==='general_llm'?'راهنمایی عمومی · بدون ارجاع به جزوه':m.mode==='llm'?'دستیار درس':m.mode==='retrieval'?'جست‌وجوی منابع':m.mode==='unverified'?'پاسخ نیازمند بررسی':'دستیار درس'}</span><div class="message-content ${m.role==='user'?'':'markdown'}">${m.role==='user'?esc(m.content):renderMarkdown(m.content)}</div>${m.citations?.length?`<div>${sources(m.citations)}</div>`:''}</div>`; }
function chatView(messages) {
  return pageTitle('با منابع درس گفت‌وگو کن','با یک راهنمایی کوچک شروع کن، پاسخ را خودت بساز و با هم بررسی کنیم.')+`<div class="chat-layout"><aside class="panel thread-library"><button data-action="new-chat">+ گفت‌وگوی جدید</button><h3>گفت‌وگوهای ذخیره‌شده</h3><div id="thread-list">${threadList()}</div></aside><section class="panel chat-panel"><div class="chat-head"><div class="intro-line"><span class="stat-icon">${icon('chat')}</span><span>${esc(state.course.name)}</span></div><button class="secondary small" data-action="export-chat" ${!state.threadId?'disabled':''}>دریافت چت</button></div><div class="chat-messages" id="messages">${messages.length?messages.map(messageHTML).join(''):'<div class="empty"><h2>گفت‌وگوی جدید</h2><p>پرسش خود را بنویسید.</p></div>'}</div><form id="chat-form" class="chat-form"><textarea name="message" rows="2" required minlength="2" maxlength="2000" aria-label="پیام شما" placeholder="مثلاً: در انتخاب گره بعدی A* گیر کرده‌ام…"></textarea><button type="submit">ارسال ←</button></form><p class="stream-status" id="stream-status" role="status">پاسخ زنده · گفت‌وگوها پس از تکمیل پاسخ خودکار ذخیره می‌شوند.</p></section></div><div class="field" style="margin-top:16px;max-width:350px"><label for="chat-topic">محدودهٔ جست‌وجو در منابع</label><select id="chat-topic">${topicOptions(true)}</select></div>`;
}
function threadList(){return state.threads.map(t=>`<button class="thread-item ${t.id===state.threadId?'selected':''}" data-action="open-chat" data-thread="${t.id}"><strong>${esc(t.title)}</strong><small>${fa(t.message_count||0)} پیام · ${date(t.created_at)}</small></button>`).join('')||'<p class="muted">اولین پرسش را بنویس.</p>';}
async function sendStream(text,topic,form){
  const generation=state.generation;
  const messages=document.querySelector('#messages');messages.querySelector('.empty')?.remove();
  const user=document.createElement('div');user.innerHTML=messageHTML({role:'user',content:text});messages.append(user);
  const pending=document.createElement('div');pending.className='message assistant streaming';pending.innerHTML='<span class="message-label">دستیار درس · در حال فکر کردن</span><div class="message-content markdown"></div>';messages.append(pending);
  const status=document.querySelector('#stream-status');let content='',done=false,general=false;scrollChat();
  state.streamAbort=new AbortController();
  try{
    const response=await fetch(`/api/courses/${state.course.id}/chat/stream`,{method:'POST',headers:{'Authorization':`Bearer ${state.token}`,'Content-Type':'application/json'},body:JSON.stringify({message:text,topic_id:topic?Number(topic):null,thread_id:state.threadId}),signal:state.streamAbort.signal});
    if(!response.ok){const d=await response.json();throw new Error(d.detail||'اتصال انجام نشد.');}
    const reader=response.body.getReader(),decoder=new TextDecoder();let buffer='';
    while(true){const chunk=await reader.read();buffer+=decoder.decode(chunk.value||new Uint8Array(),{stream:!chunk.done});let boundary;
      while((boundary=buffer.indexOf('\n\n'))>=0){const frame=buffer.slice(0,boundary);buffer=buffer.slice(boundary+2);const raw=frame.split('\n').filter(l=>l.startsWith('data:')).map(l=>l.slice(5).trim()).join('\n');if(!raw)continue;const e=JSON.parse(raw);
        if(generation!==state.generation){await reader.cancel();return;}
        if(e.event==='start'){state.threadId=e.thread_id;general=e.mode==='general_llm';}
        if(e.event==='reset'){if(e.mode==='general_llm')general=true;content='';pending.querySelector('.markdown').innerHTML='';status.textContent=general?'راهنمایی عمومی زنده؛ متن مرتبطی از جزوه بررسی نشده است.':'در حال تولید پاسخ زنده؛ ارجاع‌ها پس از پایان بررسی می‌شوند.';}
        if(e.event==='delta'){content+=e.text;pending.querySelector('.markdown').innerHTML=renderMarkdown(content);pending.querySelector('.message-label').textContent=general?'راهنمایی عمومی · در حال نوشتن':'دستیار درس · در حال نوشتن';scrollChat();}
        if(e.event==='error')throw new Error(e.message);
        if(e.event==='done'){done=true;pending.outerHTML=messageHTML(e.reply);status.textContent='پاسخ تکمیل شد و گفت‌وگو ذخیره شد.';form.reset();scrollChat();}
      }
      if(chunk.done)break;
    }
    if(!done)throw new Error('ارتباط قطع شد؛ این پرسش و پاسخ ذخیره نشده‌اند. دوباره ارسال کن.');
    state.threads=await api(`/courses/${state.course.id}/chat/threads`);
    if(generation===state.generation){document.querySelector('#thread-list').innerHTML=threadList();document.querySelector('[data-action="export-chat"]').disabled=false;}
  }catch(error){if(!done){user.remove();pending.remove();}if(generation===state.generation){status.textContent=error.message;throw error;}}
  finally{state.streamAbort=null;}
}
function chatAnalytics(d){if(!d)return '';return `<section class="panel wide chat-analysis"><div class="panel-head"><div><h2>وضعیت یادگیری از روی گفت‌وگو</h2><p>${esc(d.learning_status)}</p></div><span class="tag ${d.needs_attention?'amber':''}">نشانه‌های چت</span></div>${stats([['پرسش‌های ثبت‌شده',fa(d.question_count),'کل پرسش‌های همین درس','chat'],['پرسش‌های هفته',fa(d.questions_week),'۷ روز اخیر','trend'],['روزهای فعالیت',fa(d.active_days),'آخرین فعالیت: '+date(d.last_active_at),'clock'],['نشست‌های یادگیری',fa(d.sessions),'فاصلهٔ بیش از ۳۰ دقیقه','resources']])}<div class="topic-list">${Object.entries(d.difficulty_counts).map(([k,v])=>`<span class="tag">${esc(k)}: ${fa(v)}</span>`).join('')}</div>${d.topics.map(t=>`<div class="skill-row"><div class="skill-top"><strong>${esc(t.name)}</strong><span>${fa(t.question_count)} پرسش</span></div><p>${esc(t.difficulty)} · ${esc(t.reason)}</p></div>`).join('')||'<p class="muted">هنوز پرسشی به مبحث مشخصی مرتبط نشده است.</p>'}<p class="muted">${fa(d.no_evidence_count)} پاسخ بدون منبع کافی</p><span class="tag">نشانه‌های چت؛ بدون نمرهٔ تسلط</span></section>`;}
function scrollChat() { const messages=document.querySelector('#messages'); if(messages) messages.scrollTop=messages.scrollHeight; }

app.addEventListener('click', handleAction);
modal.addEventListener('click', handleAction);
async function handleAction(event) {
  const button=event.target.closest('[data-action]'); if (!button || button.disabled) return;
  const action=button.dataset.action;
  try{if(await handleStaffAction(action,button))return;if(await handleLearningReportAction(action,button))return;if(await handleTeachingAction(action,button))return;}catch(error){toast(error.message);return;}
  if(action==='auth-login'||action==='auth-register'){state.authMode=action==='auth-login'?'login':'register';renderAuth();return;}
  if(action==='logout')return logout();
  if(action==='close-modal')return modal.close();
  if(action==='retry')return renderView();
  if(action==='new-chat'||action==='open-chat'){
    if(state.streamAbort)return toast('تا پایان پاسخ صبر کن.');
    if(action==='new-chat'){const t=await api(`/courses/${state.course.id}/chat/threads`,{method:'POST',body:{}});state.threadId=t.id;}else state.threadId=Number(button.dataset.thread);
    state.chatCourse=state.course.id;return renderView();
  }
  if(action==='export-knowledge'){
    button.disabled=true;
    try{const r=await fetch(`/api/courses/${state.course.id}/knowledge/export`,{headers:{Authorization:`Bearer ${state.token}`}});if(!r.ok)throw new Error('دریافت کتابخانه انجام نشد.');const url=URL.createObjectURL(await r.blob());const a=document.createElement('a');a.href=url;a.download=`course-${state.course.id}-okf.zip`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);toast('بستهٔ OKF آماده شد.');}catch(error){toast(error.message);}finally{button.disabled=false;}return;
  }
  if(action==='export-chat'){
    const r=await fetch(`/api/courses/${state.course.id}/chat/threads/${state.threadId}/export`,{headers:{Authorization:`Bearer ${state.token}`}});
    if(!r.ok)return toast('دریافت گفت‌وگو انجام نشد.');const url=URL.createObjectURL(await r.blob());const a=document.createElement('a');a.href=url;a.download='conversation.md';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);return;
  }
  if(action==='view'){state.view=button.dataset.view;await renderShell();return;}
  if(action==='create-course')return showModal('ساخت درس جدید',`<form id="course-form"><div class="field"><label for="course-name">نام درس</label><input id="course-name" name="name" required minlength="2" maxlength="255" placeholder="مثلاً: مبانی هوش مصنوعی"></div><div class="field"><label for="course-description">توضیح کوتاه</label><textarea id="course-description" name="description" maxlength="2000"></textarea></div><div class="error" role="alert"></div><button type="submit">ساخت درس</button></form>`);
  if(action==='join-course')return showModal('عضویت در درس',`<form id="join-form"><p class="muted" style="margin-bottom:15px">کد عضویت را از استاد درس دریافت کن.</p><div class="field"><label for="join-code">کد درس</label><input id="join-code" name="code" required minlength="6" maxlength="32" dir="ltr" placeholder="A1B2C3D4E5"></div><div class="error" role="alert"></div><button type="submit">عضویت در درس</button></form>`);
  if(action==='create-topic')return showModal('افزودن مبحث',`<form id="topic-form"><div class="field"><label for="topic-name">نام مبحث</label><input id="topic-name" name="name" required minlength="2" maxlength="255"></div><div class="field"><label for="topic-description">توضیح و پیش‌نیازها</label><textarea id="topic-description" name="description" maxlength="2000"></textarea></div><div class="error" role="alert"></div><button type="submit">افزودن مبحث</button></form>`);
  if(action==='upload-resource')return showModal('بارگذاری منبع درس',`<form id="resource-form"><div class="field"><label for="resource-title">عنوان کتاب یا جزوه</label><input id="resource-title" name="title" required maxlength="255"></div><div class="field"><label for="resource-topic">مبحث مرتبط (اختیاری)</label><select id="resource-topic" name="topic_id">${topicOptions(true)}</select></div><div class="field"><label for="resource-file">فایل منبع</label><input id="resource-file" type="file" name="file" accept=".pdf,.txt,.md"></div><div class="field"><label for="resource-text">یا متن منبع را اینجا وارد کن</label><textarea id="resource-text" name="text" rows="6" maxlength="200000" placeholder="متن جزوه یا محتوای آموزشی…"></textarea></div><p class="muted">یک فایل یا متن وارد کن. حداکثر ${fa((state.status?.max_upload_bytes || 104857600)/1048576)} مگابایت و ${fa(state.status?.max_resource_pages || 3000)} صفحه. پردازش کتاب بزرگ ممکن است چند دقیقه طول بکشد. PDF تصویری پشتیبانی نمی‌شود.</p><div class="error" role="alert"></div><button type="submit">بارگذاری و پردازش</button></form>`);
  if(action==='source'){
    button.disabled=true;
    try{const d=await api(`/resources/${button.dataset.resource}/pages/${button.dataset.page}`);showModal(d.title,`<span class="tag">صفحهٔ ${fa(d.page)}</span><p class="muted" style="margin-top:10px">متن استخراج‌شده؛ ممکن است چیدمان با فایل اصلی متفاوت باشد. بخش‌ها کمی هم‌پوشانی دارند.</p>${d.original_url?`<p><a class="source-btn" href="${esc(d.original_url)}" target="_blank" rel="noopener noreferrer">فایل اصلی · صفحهٔ ${fa(d.page)}</a></p>`:""}${d.chunks.map(c=>`<div class="source-text">${esc(c.text)}</div>`).join('')}<div style="margin-top:18px;display:flex;gap:10px">${d.previous_page?`<button class="secondary small" data-action="source" data-resource="${button.dataset.resource}" data-page="${d.previous_page}">صفحهٔ قبل</button>`:''}${d.next_page?`<button class="secondary small" data-action="source" data-resource="${button.dataset.resource}" data-page="${d.next_page}">صفحهٔ بعد</button>`:''}</div>`);}
    catch(error){toast(error.message);}finally{button.disabled=false;}return;
  }
  if(action==='student-detail'){
    clearReportPolling(); const detailGeneration=++state.generation; button.disabled=true;
    try{const d=await api(`/courses/${state.course.id}/students/${button.dataset.student}`);if(state.generation!==detailGeneration)return;document.querySelector('#view').innerHTML=pageTitle(esc(fullName(d.student)),'وضعیت یادگیری و استفاده در '+esc(state.course.name),'<button class="secondary small" data-action="view" data-view="students">بازگشت به فهرست</button>')+stats([['اطمینان خوداظهاری',d.average_confidence==null?'—':fa(d.average_confidence)+'٪','آخرین گزارش هر مبحث','trend'],['نیازمند توجه',fa(d.weak_topics),'مباحث دارای چالش','report'],['مطالعهٔ ۷ روز اخیر',fa(d.study_minutes_week),'دقیقهٔ ثبت‌شده','clock'],['مباحث گزارش‌شده',fa(d.reported_topics),'از '+fa(d.total_topics)+' مبحث','resources']])+`<div id="student-learning-report" data-student="${d.student.id}"></div><div class="grid two-col"><section class="panel"><div class="panel-head"><h2>وضعیت مباحث</h2></div>${skills(d)}${strengthsView(d)}</section>${chatAnalytics(d.chat_analysis)}${topicTrendsView(d.learning_trends)}<section class="panel"><div class="panel-head"><h2>پیشنهادهای مطالعه برای دانشجو</h2></div>${recommendations(d)}</section><section class="panel wide"><div class="panel-head"><h2>گزارش‌ها و یادداشت‌های دانشجو</h2></div>${reportsTable(d)}</section></div>`;await loadStudentReportPanel(d.student.id);}
    catch(error){toast(error.message);}finally{button.disabled=false;}
  }
}
app.addEventListener('change',async event=>{
  if(event.target.id==='course-selector'){state.course=state.courses.find(c=>c.id===Number(event.target.value));state.view='dashboard';state.topics=await api(`/courses/${state.course.id}/topics`);await renderShell();}
  if(event.target.id==='attention-only')filterStudents();
});
app.addEventListener('input',event=>{if(event.target.id==='student-search')filterStudents();});
function filterStudents(){const query=document.querySelector('#student-search').value.toLowerCase();const only=document.querySelector('#attention-only').checked;document.querySelector('#student-table').innerHTML=studentTable(state.studentData.students.filter(s=>(!only||s.needs_attention)&&(fullName(s.student)+' '+s.student.email).toLowerCase().includes(query)));}
app.addEventListener('submit',handleSubmit);modal.addEventListener('submit',handleSubmit);
async function handleSubmit(event){
  event.preventDefault();const form=event.target;const button=form.querySelector('button[type="submit"]');if(!button||button.disabled)return;
  button.disabled=true;const fd=new FormData(form);const values=Object.fromEntries(fd);const errorEl=form.querySelector('.error');if(errorEl)errorEl.textContent='';
  const courseId=state.course?.id;
  try{
    if(await handleStaffSubmit(form))return;
    if(await handleTeachingSubmit(form))return;
    if(form.id==='auth-form'){
      const d=await api(`/auth/${state.authMode}`,{method:'POST',body:values});state.token=d.access_token;state.user=d.user;sessionStorage.setItem('hamdars-token',state.token);await loadCourses();state.status=await api('/status');state.view='dashboard';await renderShell();
    }else if(form.id==='course-form'){
      const d=await api('/courses',{method:'POST',body:values});modal.close();await loadCourses(d.id);state.view='resources';await renderShell();toast('درس ساخته شد. حالا مباحث و منابع را اضافه کن.');
    }else if(form.id==='join-form'){
      const d=await api('/courses/join',{method:'POST',body:values});modal.close();await loadCourses(d.id);await renderShell();toast('به درس پیوستی.');
    }else if(form.id==='topic-form'){
      await api(`/courses/${courseId}/topics`,{method:'POST',body:values});modal.close();await loadCourses();await renderShell();toast('مبحث اضافه شد.');
    }else if(form.id==='resource-form'){
      if(values.text.trim()){if(values.file.size)throw new Error('فقط فایل یا متن را انتخاب کن.');fd.set('file',new Blob([values.text.trim()],{type:'text/plain'}),'source.txt');}else if(!values.file.size)throw new Error('یک فایل انتخاب کن یا متن منبع را وارد کن.');fd.delete('text');if(fd.get('file').size>(state.status?.max_upload_bytes || 104857600))throw new Error('اندازهٔ فایل بیشتر از حد مجاز است.');button.textContent='در حال استخراج متن و آماده‌سازی جست‌وجو…';if(!values.topic_id)fd.delete('topic_id');await api(`/courses/${courseId}/resources`,{method:'POST',body:fd});modal.close();await renderView();toast('منبع پردازش شد و آمادهٔ جست‌وجو است.');
    }else if(form.id==='report-form'){
      for(const field of ['topic_id','confidence','study_minutes'])values[field]=Number(values[field]);await api(`/courses/${courseId}/reports`,{method:'POST',body:values});state.view='dashboard';await renderShell();toast('گزارش ثبت شد. پیشنهادهای مطالعه به‌روز شدند.');
    }else if(form.id==='chat-form'){
      const text=values.message.trim();if(text.length<2)throw new Error('پرسش را با حداقل دو کاراکتر بنویس.');button.textContent='در حال پاسخ…';await sendStream(text,document.querySelector('#chat-topic').value,form);
    }
  }catch(error){if(errorEl)errorEl.textContent=error.message;else toast(error.message);}
  finally{button.disabled=false;if(form.id==='chat-form')button.textContent='ارسال ←';if(form.id==='resource-form')button.textContent='بارگذاری و پردازش';}
}
initialize();
