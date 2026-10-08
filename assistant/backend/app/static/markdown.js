// Math is protected before Markdown processing, then inserted using KaTeX's safe renderer.
function renderMarkdown(text) {
  const math=[];const prefix='HAMDARSMATH'+Math.random().toString(36).slice(2)+'TOKEN';
  const input=String(text||'').replace(/\\\[([\s\S]*?)\\\]|\\\(([\s\S]*?)\\\)|\$\$([\s\S]*?)\$\$|(?<!\$)\$([^\n$]+)\$(?!\$)/g,(_,display,inline,dollars,single)=>{
    const i=math.length;math.push({text:display??inline??dollars??single,display:display!=null||dollars!=null});return prefix+i+'END';
  });
  let html=DOMPurify.sanitize(marked.parse(input,{breaks:true,gfm:true}),{ALLOWED_TAGS:['p','br','strong','em','del','h1','h2','h3','h4','ul','ol','li','blockquote','pre','code','table','thead','tbody','tr','th','td','hr'],ALLOWED_ATTR:['start']});
  math.forEach((m,i)=>{html=html.replace(prefix+i+'END',katex.renderToString(m.text,{displayMode:m.display,throwOnError:false,trust:false,strict:'ignore',maxExpand:1000,maxSize:20}));});
  return html;
}
