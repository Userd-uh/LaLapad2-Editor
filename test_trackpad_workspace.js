const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync(__dirname+'/templates/index.html','utf8');
const script = html.slice(html.indexOf('<script>')+8,html.lastIndexOf('</script>'));
const ui = fs.readFileSync(__dirname+'/static/trackpad-ui.js','utf8');
new vm.Script(script);new vm.Script(ui);
const part=(from,to)=>script.slice(script.indexOf(from),script.indexOf(to,script.indexOf(from)));
let palette;
const writes=[];
const ctx={assert,console,markUnsaved(){},renderKeyboard(){},renderTpGestureKeys(){},setStatus(){},
  bindingLabel:raw=>raw,clearPaletteContext(){},activatePaletteContext:value=>{palette=value;},
  needsFollowUpPicker:raw=>raw.includes('XXXXXXXX'),openTemplateFollowUpPicker:value=>{palette=value;},
  DEFAULT_BINDING_CAT_IDS:['basic','macro'],setBinding:(idx,raw)=>writes.push({idx,raw}),
  state:{tpSide:'left',currentLayer:0,tpSelected:'tap1',currentTab:'trackpad',tpView:'actions',macroDefs:[]}};
vm.createContext(ctx);
vm.runInContext(part('const TP_CLUSTER=','const TP_GESTURES=')+
  part('const TP_SCHEMA=','const TP_SECTION_JA=')+
  part('function getGestureMode(','function getTpNavBinding(')+
  part('function gestureActionOffsets(','function editGestureAction(')+
  ui,ctx);
vm.runInContext(`
  // Both halves and all 2F/3F directions retain the original 24 virtual positions.
  const modes={};for(const f of [2,3])for(const a of ['horizontal','vertical']) modes[tpModeKey(f,a)]='2';
  const before=JSON.stringify(modes);
  const allPositions=[];
  for(const side of ['left','right']){
    const rows=tpActionRows(side,modes);
    const positions=[...new Set(rows.filter(r=>r.idx!==undefined).map(r=>r.idx))];
    assert.equal(positions.length,12);allPositions.push(...positions);
    for(const f of [1,2,3]) assert.equal(rows.find(r=>r.id==='tap'+f).idx,rows.find(r=>r.id==='hold'+f).idx);
  }
  assert.deepEqual(allPositions.sort((a,b)=>a-b),Array.from({length:24},(_,i)=>i+52));
  assert.equal(JSON.stringify(modes),before);
  // Scroll / disabled hide inactive directional bindings without mutating them.
  const bindings=Array.from({length:76},()=>({raw:'&trans'}));bindings[58]={raw:'&kp LA(LEFT)'};
  const bindingsBefore=JSON.stringify(bindings);
  for(const mode of ['0','1','2']){
    modes[tpModeKey(2,'horizontal')]=mode;
    const rows=tpActionRows('left',modes),axis=rows.find(r=>r.id==='2-horizontal');
    assert.equal(rows.some(r=>r.id==='2-right'),mode==='2');
    assert.equal(tpActionOutput(axis,modes,bindings),mode==='0'?'無効':mode==='1'?'横スクロール':'方向ごとにキー操作');
  }
  assert.equal(JSON.stringify(bindings),bindingsBefore);
  assert.equal(tpBindingName('&mkp LCLK'),'左クリック');
  assert.equal(tpBindingName('&trans'),'下位レイヤーから継承');
  assert.equal(tpBindingName('&none'),'割り当てなし');
  // Every old settings row has a destination exactly once (no silent losses).
  const settings=tpSettingsSchema('feel').concat(tpSettingsSchema('advanced')).flatMap(s=>s.rows);
  const actionKeys=new Set(tpActionRows('left',modes).flatMap(r=>[r.enableKey,r.modeKey]).filter(Boolean));
  const oldRows=TP_SCHEMA.flatMap(s=>s.rows).filter(r=>r.type!=='navBindings');
  for(const row of oldRows){
    const count=settings.filter(r=>r===row).length+(actionKeys.has(row.key)?1:0);
    assert.equal(count,1,'Missing or duplicated '+row.key);
  }
  assert.equal(tpSettingsSchema('feel').some(s=>s.title==='Sensor'),false);
  assert.equal(tpSettingsSchema('advanced').some(s=>s.title==='Sensor'),true);
  // All physical controls remain in the photo bounds and keep unique positions.
  const physical=Array.from({length:52},(_,i)=>keymapVisualPosition(i));
  assert.equal(new Set(physical.map(p=>p.x+':'+p.y)).size,52);
  for(const p of physical)assert.ok(p.x>=0&&p.y>=0&&p.x+p.w<=1971&&p.y+p.h<=715);
  // The right half is the exact horizontal mirror of the cleanly aligned left half.
  const pairs=[];
  for(let row=0;row<3;row++)for(let col=0;col<5;col++)pairs.push([row*10+col,row*10+9-col]);
  for(let i=0;i<6;i++)pairs.push([30+i,41-i]);
  pairs.push([42,51],[43,48],[44,49],[45,50],[46,47]);
  for(const [left,right] of pairs){
    const a=physical[left],b=physical[right];
    assert.equal(b.x,1971-a.x-a.w,'x mirror '+left+'/'+right);
    assert.equal(b.y,a.y,'y mirror '+left+'/'+right);
    assert.equal(b.w,a.w);assert.equal(b.h,a.h);
    assert.equal((b.angle||0)+(a.angle||0),0,'angle mirror '+left+'/'+right);
  }
`,ctx);
// A stale palette callback cannot edit a different side, layer, or operation.
vm.runInContext("pickTpCustomBinding({idx:52,label:'1本指でタップ'},'basic')",ctx);
const originalPicker=palette;
ctx.state.tpSide='right';originalPicker.onPick('&kp A');assert.equal(writes.length,0);
ctx.state.tpSide='left';ctx.state.currentLayer=1;originalPicker.onPick('&kp B');assert.equal(writes.length,0);
ctx.state.currentLayer=0;ctx.state.tpSelected='tap2';originalPicker.onPick('&kp C');assert.equal(writes.length,0);
ctx.state.tpSelected='tap1';originalPicker.onPick('&kp D');assert.deepEqual(writes,[{idx:52,raw:'&kp D'}]);
// Templates never write incomplete placeholders; only the completed binding is applied.
writes.length=0;originalPicker.onPick('&kp LC(XXXXXXXX)');assert.equal(writes.length,0);
palette.onComplete('&kp LC(A)');assert.deepEqual(writes,[{idx:52,raw:'&kp LC(A)'}]);
// Per-side copy touches only the opposite side on the selected layer.
vm.runInContext(part('function copyTpGestureBindings(','function getRotation('),ctx);
ctx.renderTpGestureKeys=()=>{};
ctx.state.layers=Array.from({length:2},()=>({bindings:Array.from({length:76},(_,i)=>({raw:'&kp KEY'+i}))}));
ctx.state.currentLayer=1;
vm.runInContext(`
  const unchanged=JSON.stringify(state.layers[0]);
  const original=JSON.stringify(state.layers[1].bindings.slice(0,52));
  copyTpGestureBindings('left','right');
  assert.equal(JSON.stringify(state.layers[0]),unchanged);
  assert.equal(JSON.stringify(state.layers[1].bindings.slice(0,52)),original);
  TP_CLUSTER.right.forEach((idx,i)=>assert.equal(state.layers[1].bindings[idx].raw,'&kp KEY'+TP_CLUSTER.left[i]));
`,ctx);
console.log('Trackpad workspace: positions, mode visibility, complete settings partition, stale-target guards and copy isolation OK');
