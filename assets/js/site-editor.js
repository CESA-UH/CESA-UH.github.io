(function(){
'use strict';
const key=window.ECESiteCourseKey;
if(!key || !window.ECEAssistant)return;
const article=document.querySelector('.md-content__inner');if(!article)return;
const endpoint=new URL(window.ECEAssistant.urlFor(key));
const marker='/courses/';const relative=location.pathname.split(marker)[1];if(!relative)return;
let route=relative.substring(relative.indexOf('/')+1);
const path=!route || route==='index.html'?'index.md':route.replace(/\/index\.html$/,'').replace(/\/$/,'')+'.md';
let doc,dialog,table,sourceParts,mode='table',activeLink;
const bar=document.createElement('div');bar.className='ece-edit-bar';article.before(bar);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function request(url,options={}){
 const token=sessionStorage.getItem('hamdars-token');const headers={...options.headers};
 if(token)headers.Authorization='Bearer '+token;
 if(options.body && !(options.body instanceof FormData)){headers['Content-Type']='application/json';options.body=JSON.stringify(options.body);}
 const r=await fetch(new URL('/api'+url,endpoint),{...options,headers});const data=await r.json();
 if(!r.ok)throw Object.assign(new Error(typeof data.detail==='string'?data.detail:'اطلاعات واردشده معتبر نیست.'),{status:r.status});return data;
}
const base='/site-courses/'+encodeURIComponent(key);
async function load(){
 try{
  doc=await request(base+'/document?path='+encodeURIComponent(path));
  if(doc.html!=null){article.innerHTML=doc.html;if(window.MathJax?.typesetPromise)window.MathJax.typesetPromise([article]).catch(()=>{});}
  bar.innerHTML='<a href="/">همهٔ دروس</a>'+ (doc.can_edit?'<span>ویرایش این صفحه برای شما فعال است</span><button data-edit="open">ویرایش صفحه</button><button data-edit="history">تاریخچه</button><button data-edit="logout">خروج</button>':'<button data-edit="login">ورود برای ویرایش</button>');
 }catch(error){if(error.status===401){sessionStorage.removeItem('hamdars-token');return load();}bar.innerHTML='<span>اتصال به ویرایشگر برقرار نشد.</span><button data-edit="reload">تلاش مجدد</button>';}
}
function popup(title,html){
 if(dialog)dialog.remove();dialog=document.createElement('dialog');dialog.className='ece-editor';
 dialog.innerHTML='<header><h2>'+esc(title)+'</h2><button type="button" data-edit="close" aria-label="بستن">×</button></header>'+html;
 document.body.append(dialog);dialog.showModal();
}
function parseTable(text){
 const lines=text.split('\n');let start=-1,end=-1;
 for(let i=0;i<lines.length-1;i++)if(/^\s*\|/.test(lines[i]) && /^\s*\|?[\s:|-]+\|\s*$/.test(lines[i+1])){start=i;end=i+2;while(end<lines.length && /^\s*\|/.test(lines[end]))end++;break;}
 if(start<0)return null;
 const cells=line=>line.trim().replace(/^\||\|$/g,'').split(/(?<!\\)\|/).map(c=>c.trim());
 return {before:lines.slice(0,start).join('\n'),after:lines.slice(end).join('\n'),headers:cells(lines[start]),separator:lines[start+1],rows:lines.slice(start+2,end).map(cells)};
}
function field(value,row,col){
 const match=value.match(/^\[([^\]]*)\]\((.*)\)(?:\{[^}]*\})?$/);
 const links=/فایل|اسلاید|ویدئو|ویدیو|جزوه|تمرین|کد/.test(table.headers[col]) && col>1;
 return `<td><input aria-label="${esc(table.headers[col])} ردیف ${row+1}" data-cell="${row}:${col}" value="${esc(match?match[1]:value==='—'||value==='-'?'':value)}">${links?`<input class="ece-link-field" aria-label="آدرس ${esc(table.headers[col])} ردیف ${row+1}" data-link="${row}:${col}" value="${esc(match?match[2]:'')}" placeholder="آدرس فایل (اختیاری)" dir="ltr">`:''}</td>`;
}
function tableUI(){return `<div class="ece-table-wrap"><table><thead><tr>${table.headers.map(h=>'<th>'+esc(h)+'</th>').join('')}<th></th></tr></thead><tbody>${table.rows.map((row,i)=>'<tr>'+table.headers.map((_,j)=>field(row[j]||'',i,j)).join('')+`<td><button type="button" data-edit="remove-row" data-row="${i}" aria-label="حذف ردیف ${i+1}">×</button></td></tr>`).join('')}</tbody></table></div><button type="button" data-edit="add-row">+ ردیف جدید</button>`;}
function captureTable(){
 dialog.querySelectorAll('[data-cell]').forEach(input=>{const [r,c]=input.dataset.cell.split(':').map(Number);const url=dialog.querySelector(`[data-link="${r}:${c}"]`)?.value.trim();let text=input.value.trim();table.rows[r][c]=url?'['+(text||'مشاهده')+']('+url+')':text||'—';});
 return [table.before,'| '+table.headers.join(' | ')+' |',table.separator,...table.rows.map(row=>'| '+table.headers.map((_,i)=>(row[i]||'—').replace(/\|/g,'&#124;').replace(/\n/g,' ')).join(' | ')+' |'),table.after].join('\n');
}
function edit(markdown=doc.markdown){
 table=parseTable(markdown);sourceParts=markdown;mode=table?'table':'text';
 popup('ویرایش صفحه',`<form id="ece-content-form">${table?'<div class="ece-edit-tabs"><button type="button" data-edit="table-mode">جدول جلسات</button><button type="button" data-edit="text-mode">متن کامل صفحه</button></div>':''}<div id="ece-edit-fields">${table?tableUI():`<label for="ece-body">متن صفحه</label><textarea id="ece-body" spellcheck="false">${esc(markdown)}</textarea>`}</div><section class="ece-file-upload"><label for="ece-file">افزودن فایل منبع</label><input id="ece-file" type="file" accept=".pdf,.txt,.md,.png,.jpg,.jpeg"><button type="button" data-edit="upload">بارگذاری فایل</button><p id="ece-file-status" role="status"></p><label for="ece-upload-url">آدرس فایل بارگذاری‌شده</label><input id="ece-upload-url" readonly dir="ltr" placeholder="پس از بارگذاری نمایش داده می‌شود"></section><p class="ece-error" role="alert"></p><footer><span>نسخهٔ ${doc.revision.toLocaleString('fa-IR')}</span><button type="submit">ذخیره و نمایش</button></footer></form>`);
}
async function act(event){
 const button=event.target.closest('[data-edit]');if(!button)return;
 try{
  const action=button.dataset.edit;
  if(action==='close'){dialog.close();return;}
  if(action==='reload')return load();
  if(action==='logout'){sessionStorage.removeItem('hamdars-token');return load();}
  if(action==='login'){popup('ورود به حساب',`<form id="ece-login-form"><label for="ece-email">ایمیل</label><input id="ece-email" name="email" type="email" autocomplete="email" required dir="ltr"><label for="ece-password">رمز عبور</label><input id="ece-password" name="password" type="password" autocomplete="current-password" required dir="ltr"><p class="ece-error" role="alert"></p><button type="submit">ورود</button></form>`);return;}
  if(action==='open'){await load();if(doc.can_edit)edit();return;}
  if(action==='upload'){
   const file=dialog.querySelector('#ece-file').files[0];if(!file)throw new Error('فایل را انتخاب کنید.');
   const payload=new FormData();payload.set('file',file);button.disabled=true;
   try{const result=await request(base+'/files',{method:'POST',body:payload});dialog.querySelector('#ece-upload-url').value=result.url;dialog.querySelector('#ece-file-status').textContent=result.index_warning?'فایل ذخیره شد؛ متن آن برای دستیار قابل استخراج نیست: '+result.index_warning:result.resource_id?'فایل ذخیره شد و برای دستیار درس هم آماده است.':'فایل ذخیره شد.';if(activeLink?.isConnected)activeLink.value=result.url;}finally{button.disabled=false;}return;
  }
  if(action==='add-row'){sourceParts=captureTable();const newRow=table.headers.map(()=> '');newRow[0]=String(table.rows.length+1).replace(/\d/g,d=>'۰۱۲۳۴۵۶۷۸۹'[d]);table.rows.push(newRow);dialog.querySelector('#ece-edit-fields').innerHTML=tableUI();return;}
  if(action==='remove-row'){captureTable();table.rows.splice(Number(button.dataset.row),1);dialog.querySelector('#ece-edit-fields').innerHTML=tableUI();return;}
  if(action==='text-mode' && mode==='table'){sourceParts=captureTable();mode='text';dialog.querySelector('#ece-edit-fields').innerHTML=`<label for="ece-body">متن صفحه</label><textarea id="ece-body" spellcheck="false">${esc(sourceParts)}</textarea>`;return;}
  if(action==='table-mode' && mode==='text'){sourceParts=dialog.querySelector('#ece-body').value;table=parseTable(sourceParts);if(!table)throw new Error('در متن صفحه جدولی وجود ندارد.');mode='table';dialog.querySelector('#ece-edit-fields').innerHTML=tableUI();return;}
  if(action==='history'){
   const rows=await request(base+'/document/history?path='+encodeURIComponent(path));
   popup('تاریخچهٔ صفحه',rows.length?rows.map(r=>`<div class="ece-history"><span>نسخهٔ ${r.revision.toLocaleString('fa-IR')} · ${esc(r.editor)} · ${new Date(r.at).toLocaleString('fa-IR')}</span><button data-edit="restore" data-revision="${r.revision}">بازگردانی در ویرایشگر</button></div>`).join(''):'<p>هنوز ویرایشی ذخیره نشده است.</p>');return;
  }
  if(action==='restore'){const old=await request(base+'/document/versions/'+button.dataset.revision+'?path='+encodeURIComponent(path));await load();edit(old.markdown);}
 }catch(error){const el=dialog?.open?dialog.querySelector('.ece-error'):null;if(el)el.textContent=error.message;else{const message=document.createElement('span');message.className='ece-error';message.textContent=error.message;bar.append(message);}}
}
document.addEventListener('focusin',event=>{if(event.target.matches('[data-link]'))activeLink=event.target;});
document.addEventListener('click',act);
document.addEventListener('submit',async event=>{
 if(!['ece-login-form','ece-content-form'].includes(event.target.id))return;
 event.preventDefault();const form=event.target,button=form.querySelector('[type="submit"]');button.disabled=true;form.querySelector('.ece-error').textContent='';
 try{
  if(form.id==='ece-login-form'){const result=await request('/auth/login',{method:'POST',body:Object.fromEntries(new FormData(form))});sessionStorage.setItem('hamdars-token',result.access_token);dialog.close();await load();if(!doc.can_edit)bar.insertAdjacentHTML('beforeend','<span>حساب شما اجازهٔ ویرایش این درس را ندارد.</span>');}
  else {const markdown=mode==='table'?captureTable():form.querySelector('#ece-body').value;
   await request(base+'/document',{method:'PUT',body:{path,markdown,expected_revision:doc.revision,source_digest:doc.source_digest}});dialog.close();await load();}
 }catch(error){form.querySelector('.ece-error').textContent=error.message;}finally{button.disabled=false;}
});
load();
})();
