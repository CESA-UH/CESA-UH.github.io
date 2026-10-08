function canEditCourse(){return !!state.course?.can_edit;}
function courseRoleLabel(){return ({admin:'ادمین سیستم',teacher:'استاد درس',assistant:'حل‌تمرین درس',student:'دانشجو'})[state.course?.course_role] || (state.user?.role==='admin'?'ادمین سیستم':'دانشجو');}
async function openRequestedSiteCourse(){
  if(state.siteCourseOpened)return null;
  const key=new URLSearchParams(location.search).get('site_course');
  if(!key)return null;
  try {const course=await api(`/site-courses/${encodeURIComponent(key)}/open`,{method:'POST'});state.siteCourseOpened=true;return course.id;}
  catch(error){toast(error.message);return null;}
}
function staffView(grants){
  const admin=state.user.role==='admin';
  return pageTitle('دسترسی‌های درس','')+`<section class="panel"><h2>استاد درس</h2><p>${esc(state.course.teacher)}</p><h2>حل‌تمرین‌های درس</h2>${grants.map(g=>`<div class="staff-row"><span>${esc(fullName(g.student))}<small dir="ltr">${esc(g.student.email)}</small></span>${admin?`<button class="secondary small" data-action="revoke-assistant" data-student="${g.student.id}">لغو دسترسی ویرایش</button>`:'<span class="tag">ویرایش مباحث، منابع، فرم‌ها و کوییزها</span>'}</div>`).join('')||'<p>حل‌تمرینی تعیین نشده است.</p>'}</section>${admin?`<section class="panel staff-search"><h2>افزودن عضو و تعیین نقش</h2><form id="staff-search-form"><div class="field"><label for="staff-search">نام یا ایمیل حساب</label><input id="staff-search" name="q" maxlength="255" required></div><div class="error" role="alert"></div><button type="submit">جست‌وجو</button></form><div id="staff-users"></div></section>`:'<p class="muted">تعیین و لغو نقش حل‌تمرین توسط ادمین سیستم انجام می‌شود.</p>'}`;
}
function staffUsersView(users){return users.map(u=>`<div class="staff-row"><span>${esc(fullName(u))}<small dir="ltr">${esc(u.email)}</small><span class="tag">${esc(({student:'دانشجو',teacher:'استاد',admin:'ادمین'})[u.role])}</span></span><div class="button-row">${u.role==='student'?`<button class="secondary small" data-action="enroll-member" data-student="${u.id}">عضویت در درس</button><button class="small" data-action="grant-assistant" data-student="${u.id}">تعیین حل‌تمرین</button>`:u.role==='teacher'?`<button class="secondary small" data-action="assign-teacher" data-teacher="${u.id}">تعیین استاد درس</button>`:''}</div></div>`).join('')||'<p>حسابی پیدا نشد.</p>';}
async function handleStaffAction(action,button){
  if(action==='topic-readings'){
    const cid=state.course.id, tid=Number(button.dataset.topic), generation=state.generation;
    const rows=await api(`/courses/${cid}/resources`);
    if(generation!==state.generation)return true;
    showModal('منابع '+topicLabel(tid), `<form id="topic-readings-form" data-topic="${tid}" data-course="${cid}"><fieldset class="topic-checkboxes"><legend>منابع این مبحث</legend>${rows.map(r=>`<label class="check-label"><input type="checkbox" name="resource_ids" value="${r.id}" ${r.topic_id===tid||r.topic_ids?.includes(tid)?'checked':''}>${esc(r.title)}</label>`).join('')||'<p>ابتدا منبعی به کتابخانهٔ درس اضافه کنید.</p>'}</fieldset><div class="error" role="alert"></div><button type="submit">ذخیرهٔ منابع</button></form>`);
    return true;
  }
  if(!['grant-assistant','revoke-assistant','enroll-member','assign-teacher'].includes(action))return false;
  const cid=state.course.id;
  button.disabled=true;
  try{
    if(action==='revoke-assistant')await api(`/courses/${cid}/assistants/${button.dataset.student}`,{method:'DELETE'});
    else if(action==='assign-teacher')await api(`/courses/${cid}/teacher`,{method:'PUT',body:{teacher_id:Number(button.dataset.teacher)}});
    else await api(`/courses/${cid}/${action==='grant-assistant'?'assistants':'members'}`,{method:action==='grant-assistant'?'PUT':'POST',body:{student_id:Number(button.dataset.student)}});
    await loadCourses(cid);await renderShell();toast('دسترسی‌های درس به‌روز شد.');
  }finally{button.disabled=false;}
  return true;
}
async function handleStaffSubmit(form){
  if(form.id==='topic-readings-form'){
    await api(`/courses/${form.dataset.course}/topics/${form.dataset.topic}/readings`,{method:'PUT',body:{resource_ids:new FormData(form).getAll('resource_ids').map(Number)}});
    modal.close();await renderView();toast('منابع مبحث ذخیره شد.');return true;
  }
  if(form.id!=='staff-search-form')return false;
  const generation=state.generation;
  const rows=await api('/admin/users?q='+encodeURIComponent(new FormData(form).get('q')));
  if(generation===state.generation)document.querySelector('#staff-users').innerHTML=staffUsersView(rows)+(rows.length===100?'<p class="muted">۱۰۰ نتیجه نمایش داده شد؛ برای یافتن حساب، ایمیل یا نام دقیق‌تری وارد کنید.</p>':'');
  return true;
}

const globalRoleLabels={student:'دانشجو',teacher:'استاد',admin:'ادمین'};
async function fetchAdminUsers(){return api('/admin/users?offset='+(state.adminOffset||0)+'&q='+encodeURIComponent(state.adminQuery||'')+'&role='+encodeURIComponent(state.adminFilter||'all'));}
function adminUsersView(users){state.adminUsers=users;return pageTitle('مدیریت کاربران','', '<button data-action="admin-create-user">+ حساب جدید</button>')+`<section class="panel"><form id="admin-users-search"><div class="form-row"><div class="field"><label for="admin-query">نام یا ایمیل</label><input id="admin-query" name="q" maxlength="255" value="${esc(state.adminQuery||'')}"></div><button type="submit">جست‌وجو</button></div><div class="error" role="alert"></div></form><div class="button-row">${['all','student','teacher','assistant','admin'].map(r=>`<button class="secondary small" data-action="admin-filter" data-role="${r}">${r==='all'?'همه':r==='assistant'?'حل‌تمرین':globalRoleLabels[r]}</button>`).join('')}</div><div id="admin-user-list">${adminUserRows(users)}</div><div class="button-row"><button class="secondary small" data-action="admin-previous" ${!state.adminOffset?'disabled':''}>صفحهٔ قبل</button><button class="secondary small" data-action="admin-next" ${users.length<100?'disabled':''}>صفحهٔ بعد</button></div></section>`;}
function adminUserRows(users){return users.map(u=>`<div class="staff-row"><span><strong>${esc(fullName(u))}</strong><small dir="ltr">${esc(u.email)}</small><span class="tag">${globalRoleLabels[u.role]}</span></span><div class="button-row"><button class="secondary small" data-action="admin-edit-user" data-user="${u.id}">ویرایش حساب</button><button class="small" data-action="admin-user-courses" data-user="${u.id}">درس‌ها و نقش‌ها</button></div></div>`).join('')||'<p>حسابی پیدا نشد.</p>';}
function adminAccountModal(u){const create=!u;showModal(create?'ساخت حساب':'ویرایش حساب',`<form id="admin-account-form" ${u?`data-user="${u.id}"`:''}><div class="form-row"><div class="field"><label>نام<input name="first_name" required maxlength="100" value="${esc(u?.first_name||'')}"></label></div><div class="field"><label>نام خانوادگی<input name="last_name" required maxlength="100" value="${esc(u?.last_name||'')}"></label></div></div>${create?'<div class="field"><label>ایمیل<input type="email" name="email" required maxlength="255" dir="ltr"></label></div><div class="field"><label>رمز اولیه<input type="password" name="password" required minlength="8" maxlength="128" dir="ltr" autocomplete="new-password"></label></div>':''}<div class="field"><label>نقش حساب<select name="role">${Object.entries(globalRoleLabels).map(([v,l])=>`<option value="${v}" ${u?.role===v?'selected':''}>${l}</option>`).join('')}</select></label></div><div class="error" role="alert"></div><button type="submit">ذخیره</button></form>`);}
const originalStaffAction=handleStaffAction;
handleStaffAction=async function(action,button){
  if(!action.startsWith('admin-'))return originalStaffAction(action,button);
  if(action==='admin-create-user')adminAccountModal(null);
  if(action==='admin-edit-user')adminAccountModal(state.adminUsers.find(u=>u.id===Number(button.dataset.user)));
  if(action==='admin-filter'){state.adminFilter=button.dataset.role;state.adminOffset=0;document.querySelector('#view').innerHTML=adminUsersView(await fetchAdminUsers());}
  if(action==='admin-next'||action==='admin-previous'){state.adminOffset=Math.max(0,(state.adminOffset||0)+(action==='admin-next'?100:-100));document.querySelector('#view').innerHTML=adminUsersView(await fetchAdminUsers());}
  if(action==='admin-user-courses'){
    const u=state.adminUsers.find(u=>u.id===Number(button.dataset.user)), roles=await api(`/admin/users/${u.id}/courses`);
    showModal(fullName(u),Object.entries(roles).map(([r,cs])=>`<h3>${({teacher:'استاد',assistant:'حل‌تمرین',student:'دانشجو'})[r]}</h3>${cs.map(c=>`<p><button class="secondary" data-action="admin-open-course" data-course="${c.id}">${esc(c.name)} ← مدیریت دسترسی‌ها</button></p>`).join('')||'<p>—</p>'}`).join('')+`<h3>تعیین نقش در درس</h3><div class="button-row">${state.courses.map(c=>`<button class="secondary small" data-action="admin-open-course" data-course="${c.id}">${esc(c.name)}</button>`).join('')}</div>`);
  }
  if(action==='admin-open-course'){modal.close();await loadCourses(Number(button.dataset.course));state.view='staff';await renderShell();}
  return true;
};
const originalStaffSubmit=handleStaffSubmit;
handleStaffSubmit=async function(form){
  if(form.id==='admin-users-search'){state.adminQuery=new FormData(form).get('q');state.adminOffset=0;document.querySelector('#view').innerHTML=adminUsersView(await fetchAdminUsers());return true;}
  if(form.id==='admin-account-form'){const values=Object.fromEntries(new FormData(form));await api('/admin/users'+(form.dataset.user?'/'+form.dataset.user:''),{method:form.dataset.user?'PUT':'POST',body:values});modal.close();state.adminOffset=0;await renderView();toast('حساب ذخیره شد.');return true;}
  return originalStaffSubmit(form);
};
