import React, {useState} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';

type Recommendation={type:'doctor'|'hospital',id:number,name:string,specialty?:string|null,hospital?:string|null,city?:string|null,source:'database'};
type Msg={role:'user'|'assistant',content:string,action?:string,recommendations?:Recommendation[]};
type Result={message:string,action:string,recommendations:Recommendation[],tool_calls:string[]};
const API=import.meta.env.VITE_API_BASE_URL||'http://localhost:8000';
const welcome={en:'Hi. I can help you think through the next healthcare step. I do not diagnose conditions.',ar:'مرحبًا. أستطيع مساعدتك في التفكير في الخطوة الصحية التالية، لكنني لا أُشخّص الحالات.'};

function App(){
 const [lang,setLang]=useState<'en'|'ar'>('en');
 const [input,setInput]=useState('');
 const [loading,setLoading]=useState(false);
 const [messages,setMessages]=useState<Msg[]>([{role:'assistant',content:welcome[lang]}]);
 const labels=lang==='en'?{title:'HealTrip AI',sub:'Patient Decision Assistant',send:'Send',placeholder:'Describe what you are experiencing...',clear:'New conversation',ai:'AI explanation',db:'Database-backed recommendations',safety:'Emergency / safety guidance',empty:'No matching options were found in the prototype database.'}:{title:'HealTrip AI',sub:'مساعد قرار المريض',send:'إرسال',placeholder:'اكتب ما تشعر به...',clear:'محادثة جديدة',ai:'توضيح من الذكاء الاصطناعي',db:'توصيات مستندة إلى قاعدة البيانات',safety:'إرشادات الطوارئ والسلامة',empty:'لم يتم العثور على خيارات مطابقة في قاعدة بيانات النموذج الأولي.'};
 async function send(){
  if(!input.trim()||loading)return;
  const text=input.trim();
  setMessages(m=>[...m,{role:'user',content:text}]);setInput('');setLoading(true);
  try{
   const history=messages.map(({role,content})=>({role,content}));
   const r=await fetch(API+'/api/v1/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text,history})});
   if(!r.ok)throw new Error('request failed');
   const data:Result=await r.json();
   setMessages(m=>[...m,{role:'assistant',content:data.message,action:data.action,recommendations:data.recommendations||[]}]);
  }catch{setMessages(m=>[...m,{role:'assistant',content:'The service is temporarily unavailable. Please try again.'}]);}
  finally{setLoading(false)}
 }
 return <main dir={lang==='ar'?'rtl':'ltr'}><header><div><h1>{labels.title}</h1><span>{labels.sub}</span></div><button onClick={()=>{const next=lang==='en'?'ar':'en';setLang(next);setMessages(current=>current.map((m,i)=>i===0&&m.role==='assistant'&&(m.content===welcome.en||m.content===welcome.ar)?{...m,content:welcome[next]}:m));}}>{lang==='en'?'العربية':'English'}</button></header>
  <section className="notice">Prototype only · Not a diagnosis or emergency medical service.</section>
  <section className="chat">{messages.map((m,i)=><div className={'bubble '+m.role} key={i}>{m.role==='assistant'&&<strong className="section-label">{m.action==='ER'||m.action==='URGENT_CARE'?labels.safety:labels.ai}</strong>}<div>{m.content}</div>
   {m.role==='assistant'&&m.recommendations&&m.recommendations.length>0&&<section className="recommendations"><strong className="section-label">{labels.db}</strong>{m.recommendations.map(r=><article className="recommendation" key={`${r.type}-${r.id}`}><strong>{r.name}</strong>{r.specialty&&<div>{r.specialty}</div>}{r.type==='doctor'&&r.hospital&&<div>{r.hospital}</div>}{r.city&&<div>{r.city}</div>}</article>)}</section>}
  </div>)}{loading&&<div className="bubble assistant">…</div>}</section>
  <div className="composer"><textarea value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}}} placeholder={labels.placeholder}/><button onClick={send}>{labels.send}</button></div><button className="clear" onClick={()=>setMessages([])}>{labels.clear}</button>
 </main>
}
createRoot(document.getElementById('root')!).render(<App/>);
