export async function createPlot(element,{select,move}) {
  let bound=false,updating=false,last,selected,editing=false;
  return {
    async render(snapshot,chosen,editMode=false) {
      updating=true;last=snapshot;selected=chosen;editing=editMode;
      const {data}=snapshot,point=data.rows.find(r=>r.id===selected),shapes=[];
      if(editing && point) {
        const radius=axis=>Math.max(1,Math.max(...data.rows.map(r=>r[axis]))-Math.min(...data.rows.map(r=>r[axis])))*.025;
        shapes.push({type:'circle',xref:'x',yref:'y',x0:point.x-radius('x'),x1:point.x+radius('x'),
          y0:point.y-radius('y'),y1:point.y+radius('y'),line:{color:'#b16626',width:2},fillcolor:'rgba(177,102,38,0.3)',editable:true});
      }
      try {
        await Plotly.react(element,[{type:'scatter',mode:'markers',x:data.rows.map(r=>r.x),y:data.rows.map(r=>r.y),
          customdata:data.rows.map(r=>r.id),error_y:{type:'data',array:data.rows.map(r=>r.yerr),visible:true},
          marker:{size:10,color:data.rows.map(r=>r.id===selected?'#b16626':'#286c70')}}],
          {margin:{l:65,r:25,t:25,b:55},xaxis:{title:{text:data.axes.x.label+' ('+data.axes.x.unit+')'}},
           yaxis:{title:{text:data.axes.y.label+' ('+data.axes.y.unit+')'}},shapes,
           editrevision:snapshot.revision,uirevision:'preserve-navigation',paper_bgcolor:'#ffffff'},
          {responsive:true,displaylogo:false,edits:{shapePosition:editMode},modeBarButtonsToRemove:['toImage']});
        if(!bound) {
          element.on('plotly_click',event=>select(event.points[0].customdata));
          element.on('plotly_relayout',event=>{
            if(updating || !editing || !selected || !Object.keys(event).some(key=>key.startsWith('shapes[0]'))) return;
            const shape=element.layout.shapes[0];
            move(selected,(shape.x0+shape.x1)/2,(shape.y0+shape.y1)/2,last.revision);
          });
          bound=true;
        }
      } finally {updating=false;}
    },
    async exportSvg() {
      const shapes=structuredClone(element.layout.shapes || []);updating=true;
      try {await Plotly.relayout(element,{shapes:[]});return await Plotly.toImage(element,{format:'svg',width:900,height:550});}
      finally {await Plotly.relayout(element,{shapes});updating=false;}
    }
  };
}
