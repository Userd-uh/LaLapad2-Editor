const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync(__dirname + '/templates/index.html', 'utf8');
const script = html.slice(html.indexOf('<script>') + 8, html.lastIndexOf('</script>'));
new vm.Script(script);
const part = (a,b) => script.slice(script.indexOf(a), script.indexOf(b, script.indexOf(a)));
const context = {assert, console, markUnsaved(){}, state:{}};
vm.createContext(context);
vm.runInContext(part('const TP_CLUSTER=', 'const TP_GESTURES=') +
  part('function getGestureMode(', 'function getTpNavBinding(') +
  part('function gestureActionOffsets(', 'function editGestureAction(') + `
  const left={}, right={};
  const keys=[2,3].flatMap(f=>['HORIZONTAL','VERTICAL'].map(a=>'CONFIG_INPUT_IQS9151_'+f+'F_'+a+'_MODE'));
  for(const key of keys){
    for(const mode of ['0','1','2']){
      setGestureMode(left,key,mode);
      assert.equal(getGestureMode(left,key),mode);
      assert.equal(JSON.parse(JSON.stringify({config:left})).config[key],mode);
      assert.equal(right[key],undefined);
    }
  }
  assert.equal(getGestureMode({CONFIG_INPUT_IQS9151_SCROLL_Y_ENABLE:'n'},keys[1]),'0');
  assert.throws(()=>setGestureMode(left,keys[0],'invalid'));
  setGestureMode(left,keys[0],2);
  assert.equal(left.CONFIG_INPUT_IQS9151_2F_HORIZONTAL_NAV,'y');
  const positions=[];
  for(const side of ['left','right'])for(const fingers of [2,3])for(const direction of ['right','left','up','down']){
    positions.push(gestureActionPosition(side,fingers,direction));
  }
  assert.equal(new Set(positions).size,16);
  assert.equal(gestureActionPosition('left',2,'right'),58);
  assert.equal(gestureActionPosition('left',3,'right'),68);
  assert.equal(gestureActionPosition('right',3,'down'),75);
  const bindings=Array.from({length:76},()=>({raw:'&trans'}));
  bindings[gestureActionPosition('left',2,'left')]={raw:'&mkp MB4'};
  bindings[gestureActionPosition('left',3,'left')]={raw:'&kp LC(TAB)'};
  assert.equal(bindings[59].raw,'&mkp MB4');
  assert.equal(bindings[69].raw,'&kp LC(TAB)');
  assert.equal(bindings[73].raw,'&trans');
  `, context);
vm.runInContext(part('function gestureDisplayRows(', 'function renderSettingsGrid(') + `
  const hm={type:'gestureMode',key:'h'}, vm={type:'gestureMode',key:'v'};
  const ha={type:'navBindings',modeKey:'h'}, va={type:'navBindings',modeKey:'v'};
  const tap={type:'bool',key:'tap'};
  const rows=[va,tap,hm,vm,ha];
  const before=JSON.stringify(rows);
  for(const h of ['0','1','2'])for(const v of ['0','1','2']){
    const cfg={h,v};
    const display=gestureDisplayRows(rows,cfg);
    assert.equal(display.includes(ha),h==='2');
    assert.equal(display.includes(va),v==='2');
    if(h==='2') assert.equal(display.indexOf(ha),display.indexOf(hm)+1);
    if(v==='2') assert.equal(display.indexOf(va),display.indexOf(vm)+1);
    assert.ok(display.includes(tap));
    assert.equal(JSON.stringify(cfg),JSON.stringify({h,v}));
  }
  assert.equal(JSON.stringify(rows),before);
  assert.equal(gestureDisplayRows([tap],{} )[0],tap);
`, context);
console.log('Gesture modes, payloads and 16 independent action positions OK');

// Exercise the production RPC preflight: no mutations may reach an old MCU.
vm.runInContext(part('async function applyKeymapToDevice(', 'async function saveFirmwareSettings('), context);
context.state={device:{conn:{}},layers:[{bindings:Array(76).fill({raw:'&trans'})}]};
const requests=[];
context.callDeviceRpc=async request=>{
  requests.push(request);
  return {keymap:{getKeymap:{layers:[{bindings:Array(68).fill({})}]}}};
};
vm.runInContext('applyKeymapToDevice()',context).then(result=>{
  assert.match(result.error,/76-position firmware/);
  assert.equal(requests.length,1);
  assert.equal(requests[0].keymap.getKeymap,true);
  console.log('Old-firmware RPC preflight rejects before any writes OK');
}).catch(error=>{console.error(error);process.exitCode=1;});
