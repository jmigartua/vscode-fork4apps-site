// Editor-independent experiment. Renderers consume snapshots; only Store changes data.
export function validate(data) {
  if (!data || data.schema_version !== 1 || typeof data.title !== 'string' ||
      !Array.isArray(data.rows) || !data.axes || !data.axes.x || !data.axes.y) throw Error('Invalid dataset');
  for (const axis of ['x','y']) if (typeof data.axes[axis].label !== 'string' || typeof data.axes[axis].unit !== 'string') throw Error('Invalid axis');
  const ids = new Set();
  for (const row of data.rows) {
    if (typeof row.id !== 'string' || !row.id || ids.has(row.id)) throw Error('Rows need unique stable identifiers');
    ids.add(row.id);
    if (!Number.isFinite(row.x) || !Number.isFinite(row.y) || !Number.isFinite(row.yerr) || row.yerr < 0) throw Error('Expected finite x/y and nonnegative uncertainty');
  }
  return structuredClone(data);
}
export class Store {
  constructor(data) { this.data=validate(data); this.revision=0; this.past=[]; this.future=[]; this.listeners=new Set(); this.job=0; }
  snapshot() { return {schema_version:1,revision:this.revision,data:structuredClone(this.data)}; }
  subscribe(listener) { this.listeners.add(listener); return () => this.listeners.delete(listener); }
  notify() { for (const listener of this.listeners) listener(this.snapshot()); }
  edit(id,field,value,baseRevision=this.revision) {
    if (baseRevision !== this.revision) throw Error('Stale edit; refresh and try again');
    if (!['x','y','yerr'].includes(field) || typeof value !== 'number' || !Number.isFinite(value)) throw Error('Expected a finite number');
    const next=structuredClone(this.data), row=next.rows.find(r => r.id === id);
    if (!row) throw Error('Unknown row');
    row[field]=value; validate(next);
    this.past.push(this.data); this.future=[]; this.data=next; this.revision++; this.notify();
  }
  transact(change,baseRevision=this.revision) {
    if (baseRevision!==this.revision) throw Error('Stale edit; refresh and try again');
    const next=structuredClone(this.data);change(next);validate(next);
    this.past.push(this.data);this.future=[];this.data=next;this.revision++;this.notify();
  }
  move(id,x,y,baseRevision=this.revision) {
    this.transact(next=>{const row=next.rows.find(r=>r.id===id);if(!row) throw Error('Unknown row');row.x=x;row.y=y;},baseRevision);
  }
  insert(row) { this.transact(next=>next.rows.push(structuredClone(row))); }
  remove(id) { this.transact(next=>{const index=next.rows.findIndex(r=>r.id===id);if(index<0) throw Error('Unknown row');next.rows.splice(index,1);}); }
  undo() { if (!this.past.length) return; this.future.push(this.data); this.data=this.past.pop(); this.revision++; this.notify(); }
  redo() { if (!this.future.length) return; this.past.push(this.data); this.data=this.future.pop(); this.revision++; this.notify(); }
  beginJob() { return {revision:this.revision,job:++this.job}; }
  accepts(ticket) { return ticket.revision === this.revision && ticket.job === this.job; }
}
export function readSnapshot(text) {
  const value=JSON.parse(text);
  if (value.schema_version!==1 || !Number.isSafeInteger(value.revision) || value.revision<0) throw Error('Invalid snapshot');
  return {...value,data:validate(value.data)};
}
