import {Store,readSnapshot} from './model.mjs';
const config=await (await fetch('config.json')).json();
const store=new Store(await (await fetch('sample.json')).json());
const status=document.querySelector('#status'), jobStatus=document.querySelector('#job-status');
let selected=null,table,plot,editMode=false,chain=Promise.resolve();
const worker=new Worker('./worker.mjs',{type:'module'});
function download(url,name) {const a=document.createElement('a');a.href=url;a.download=name;a.click();}
function select(id) { selected=id; table?.select(id); render(store.snapshot(),'',false); }
function edit(id,field,value) {
  try {store.edit(id,field,value);}
  catch(error) {status.textContent=error.message;render(store.snapshot(),error.message);}
}
if(config.views.includes('table')) table=await (await import('./table.mjs')).createTable(document.querySelector('#table'),{edit,select});
else document.querySelector('#table-section').remove();
if(config.views.includes('plot')) plot=await (await import('./plot.mjs')).createPlot(document.querySelector('#plot'),{select,move:(id,x,y,revision)=>{try{store.move(id,x,y,revision);}catch(error){render(store.snapshot(),error.message);}}});
else {document.querySelector('#plot-section').remove();document.querySelector('#svg').remove();document.querySelector('#point-mode').hidden=true;}
function render(snapshot,error='',updateTable=true) {
  const chosen=selected;
  chain=chain.then(async()=>{
    if(updateTable) await table?.render(snapshot,chosen);await plot?.render(snapshot,chosen,editMode);
    document.querySelector('#title').textContent=snapshot.data.title;
    status.textContent=error || `Revision ${snapshot.revision} - ${snapshot.data.rows.length} rows${chosen?' - selected '+chosen:''}`;
    document.body.dataset.revision=String(snapshot.revision);
  }).catch(error=>{status.textContent=error.message;});
  return chain;
}
function calculate() {
  const ticket=store.beginJob(); jobStatus.textContent='Calculating mean…';
  worker.postMessage({ticket,rows:store.snapshot().data.rows});
}
worker.onmessage=({data:{ticket,mean}})=>{
  if(store.accepts(ticket)) jobStatus.textContent=`Mean y: ${mean?.toFixed(3) ?? 'empty'} (revision ${ticket.revision})`;
};
worker.onerror=()=>{jobStatus.textContent='Calculation failed; data remains editable';};
store.subscribe(snapshot=>{if(!snapshot.data.rows.some(r=>r.id===selected)) selected=null;render(snapshot);calculate();});
document.querySelector('#edit-points').onchange=event=>{editMode=event.target.checked;if(editMode && !selected) selected=store.data.rows[0]?.id;render(store.snapshot());};
document.querySelector('#add-point').onclick=()=>{
  const inputs=['new-x','new-y','new-error'].map(id=>document.getElementById(id).value);
  try {if(inputs.some(x=>!x.trim())) throw Error('Enter x, y and uncertainty');store.insert({id:crypto.randomUUID(),x:Number(inputs[0]),y:Number(inputs[1]),yerr:Number(inputs[2])});}
  catch(error){status.textContent=error.message;}
};
document.querySelector('#remove-point').onclick=()=>{try{if(!selected) throw Error('Select a row or point first');store.remove(selected);}catch(error){status.textContent=error.message;}};

document.querySelector('#undo').onclick=()=>store.undo();
document.querySelector('#redo').onclick=()=>store.redo();
document.querySelector('#snapshot').onclick=()=>{
  const url=URL.createObjectURL(new Blob([JSON.stringify(store.snapshot(),null,2)+'\n'],{type:'application/json'}));
  download(url,'figure-snapshot.json');setTimeout(()=>URL.revokeObjectURL(url),1000);
};
document.querySelector('#open').onchange=async event=>{
  try {
    const snapshot=readSnapshot(await event.target.files[0].text());
    // A reload is a new local document session, with saved source revision preserved.
    store.data=snapshot.data;store.revision=snapshot.revision;store.past=[];store.future=[];store.job++;
    selected=null;store.notify();
  } catch(error) {status.textContent=error.message;}
};
if(plot) document.querySelector('#svg').onclick=async()=>{
  await chain;
  download(await plot.exportSvg(),'interactive-figure.svg');
};
await render(store.snapshot());calculate();
