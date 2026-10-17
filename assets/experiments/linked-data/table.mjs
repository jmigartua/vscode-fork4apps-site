export async function createTable(element,{edit,select}) {
  let readyResolve, updating=false;
  const ready=new Promise(resolve => {readyResolve=resolve;});
  const table=new Tabulator(element,{index:'id',height:320,layout:'fitColumns',selectableRows:1,history:false,
    columns:[{title:'Row',field:'id'},...['x','y','yerr'].map(field => ({title:field,field,editor:'number',sorter:'number',hozAlign:'right'}))]});
  table.on('tableBuilt',readyResolve);
  table.on('cellEdited',cell => {if (!updating) edit(cell.getRow().getIndex(),cell.getField(),cell.getValue());});
  table.on('rowClick',(_event,row) => {if (!updating) select(row.getIndex());});
  await ready;
  return {
    async render(snapshot,selected) {
      updating=true;
      try { await table.replaceData(snapshot.data.rows); table.deselectRow(); if(selected) table.selectRow(selected); }
      finally {updating=false;}
    },
    select(id) { updating=true; table.deselectRow(); if(id) table.selectRow(id); updating=false; }
  };
}
