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
console.log('Gesture modes, payloads and 16 independent action positions OK');
