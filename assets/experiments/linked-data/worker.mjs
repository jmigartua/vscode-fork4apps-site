// Demonstrates asynchronous lifecycle only; not a scientific analysis engine.
self.onmessage=({data:{ticket,rows,delay=0}}) => {
  const mean=rows.length ? rows.reduce((total,row)=>total+row.y,0)/rows.length : null;
  setTimeout(()=>self.postMessage({ticket,mean}),delay);
};
