/* Presentation only: bindings retain their original firmware positions. */
function keymapVisualPosition(index){
  const topLeft=[[49,113],[170,90],[292,65],[409,80],[525,106]];
  const topRight=[[1307,121],[1424,99],[1544,84],[1663,104],[1785,133]];
  if(index<30){
    const col=index%10, row=Math.floor(index/10), [x,y]=(col<5?topLeft:topRight)[col%5];
    return {x:x-row*8,y:y+row*119,w:104,h:103};
  }
  const thumbs=[[20,474],[143,445],[263,428],[476,474],[614,462,18],[750,519,27],
    [1050,511,-25],[1190,477,-17],[1340,493],[1580,476],[1715,485],[1842,505]];
  if(index<42){const [x,y,angle]=thumbs[index-30];return {x,y,w:100,h:100,angle};}
  // Matrix order is center/right/down/left/up on left, up/left/down/right/center on right.
  const cross=[[0,0],[32,0],[0,32],[-32,0],[0,-32],[0,-32],[-32,0],[0,32],[32,0],[0,0]];
  const [dx,dy]=cross[index-42];
  return {x:(index<47?400:1489)+dx,y:490+dy,w:30,h:30};
}
function tpNode(tag,className,text){
  const node=document.createElement(tag);
  if(className) node.className=className;
  if(text!==undefined) node.textContent=text;
  return node;
}
function tpButton(text,handler,className='btn'){
  const node=tpNode('button',className,text);node.type='button';node.onclick=handler;return node;
}
function tpSideName(side=state.tpSide){return side==='left'?'左':'右';}
function appendTrackpadEntrances(keyboard){
  for(const side of ['left','right']){
    const pos=side==='left'?{x:636,y:85,w:263,h:329}:{x:1028,y:117,w:263,h:329};
    const button=tpButton('',()=>openTrackpad(side),'trackpad-entrance');
    button.dataset.trackpadSide=side;
    button.setAttribute('aria-label',`${tpSideName(side)}トラックパッドの設定を開く`);
    button.classList.toggle('last-selected',state.tpSide===side);
    Object.assign(button.style,{left:`${pos.x/1971*100}%`,top:`${pos.y/715*100}%`,width:`${pos.w/1971*100}%`,height:`${pos.h/715*100}%`});
    button.append(tpNode('strong','',`${tpSideName(side)}トラックパッド`),tpNode('small','','クリックして設定'));
    keyboard.appendChild(button);
  }
  if(!document.getElementById('keyboard-help')){
    const hint=tpNode('div','keyboard-help');hint.id='keyboard-help';
    hint.append(tpNode('strong','','キーを選択して割り当てを変更'),tpNode('span','','トラックパッドをクリックすると、その側の操作と感度を設定できます。'));
    document.querySelector('#tab-keymap .kb-area').after(hint);
  }
}
function clearTpEditingContext(){
  closeBindingPicker();closeKeyPicker();
  if(state.paletteContext?.tab==='trackpad') clearPaletteContext();
}
function openTrackpad(side){
  clearTpEditingContext();state.tpSide=side;
  state.tpView='actions';state.tpSelected='tap1';
  switchTab('trackpad');
}
function switchTpView(view){
  if(!['actions','feel','advanced'].includes(view)) return;
  clearTpEditingContext();state.tpView=view;renderTpWorkspace();
  document.querySelector('.tp-scroll').scrollTop=0;
}
function tpModeKey(fingers,axis){return `CONFIG_INPUT_IQS9151_${fingers}F_${axis.toUpperCase()}_MODE`;}
function tpActionRows(side,cfg){
  const rows=[];
  for(const fingers of [1,2,3]) rows.push({id:`tap${fingers}`,group:'タップ',label:`${fingers}本指でタップ`,idx:TP_CLUSTER[side][fingers-1],enableKey:`CONFIG_INPUT_IQS9151_${fingers}F_TAP_ENABLE`});
  for(const fingers of [2,3]) for(const axis of ['horizontal','vertical']){
    const modeKey=tpModeKey(fingers,axis), id=`${fingers}-${axis}`, vertical=axis==='vertical';
    rows.push({id,group:'スワイプ',label:`${fingers}本指・${vertical?'縦':'横'}方向`,modeKey,axis,fingers});
    if(getGestureMode(cfg,modeKey)==='2'){
      for(const [direction,name] of vertical?[['up','上'],['down','下']]:[['left','左'],['right','右']]){
        rows.push({id:`${fingers}-${direction}`,group:'スワイプ',label:`${fingers}本指で${name}にスワイプ`,idx:gestureActionPosition(side,fingers,direction),modeKey,axis,fingers});
      }
    }
  }
  rows.push({id:'pinch',group:'ピンチ',label:'2本指でピンチ',idx:TP_CLUSTER[side][7],enableKey:'CONFIG_INPUT_IQS9151_2F_PINCH_ENABLE',pinch:true});
  // Hold uses the same BTN0/1/2 positions as tap. Do not invent separate bindings.
  for(const fingers of [1,2,3]) rows.push({id:`hold${fingers}`,group:'長押し・ドラッグ',label:`${fingers}本指で長押し`,idx:TP_CLUSTER[side][fingers-1],enableKey:`CONFIG_INPUT_IQS9151_${fingers}F_PRESSHOLD_ENABLE`,hold:true,fingers});
  return rows;
}
function tpBindingName(raw){
  const names={'&mkp LCLK':'左クリック','&mkp MB1':'左クリック','&mkp RCLK':'右クリック','&mkp MB2':'右クリック','&mkp MCLK':'中央クリック','&mkp MB3':'中央クリック','&mkp MB4':'マウスの戻るボタン','&mkp MB5':'マウスの進むボタン','&trans':'下位レイヤーから継承','&none':'割り当てなし','&kp LG(TAB)':'Win + Tab','&kp LG(D)':'Win + D','&kp LA(LEFT)':'Alt + ←','&kp LA(RIGHT)':'Alt + →'};
  if(names[raw]) return names[raw];
  const modifiers={LCTRL:'Ctrl',LEFT_CONTROL:'Ctrl',RCTRL:'右Ctrl',RIGHT_CONTROL:'右Ctrl',LALT:'Alt',LEFT_ALT:'Alt',RALT:'右Alt',RIGHT_ALT:'右Alt',LWIN:'Win',LGUI:'Win',LEFT_GUI:'Win',LSHIFT:'Shift',LEFT_SHIFT:'Shift'};
  if(raw.startsWith('&kp ') && modifiers[raw.slice(4)]) return modifiers[raw.slice(4)];
  const macro=raw.match(/^&mc(\d+)$/);
  if(macro) return state.macroDefs?.[+macro[1]]?.display_name||`マクロ ${macro[1]}`;
  const td=raw.match(/^&td(\d+)$/);
  if(td) return `タップダンス ${td[1]}`;
  return bindingLabel(raw).replace(/\n/g,' ')||raw;
}
function tpActionOutput(row,cfg,bindings){
  if(row.idx===undefined){
    const mode=getGestureMode(cfg,row.modeKey);
    return mode==='0'?'無効':mode==='2'?'方向ごとにキー操作':row.axis==='vertical'?'縦スクロール':'横スクロール';
  }
  const raw=bindings[row.idx]?.raw||'&trans',name=tpBindingName(raw);
  if(row.enableKey && cfg[row.enableKey]==='n') return `無効（保存済み：${name}）`;
  if(row.pinch) return raw==='&none'?'ホイール入力':`${name} ＋ ホイール`;
  if(row.hold) return `${name}を押したまま`;
  return name;
}
function tpSettingsSchema(view){
  // Partition the original schema: no config keys are renamed or discarded.
  return TP_SCHEMA.map(section=>({...section,rows:section.rows.filter(row=>{
    if(row.type==='gestureMode'||row.type==='navBindings'||/_TAP_ENABLE$|_PRESSHOLD_ENABLE$|_PINCH_ENABLE$/.test(row.key||'')) return false;
    const advanced=['Sensor','Dynamic Filter'].includes(section.title)||(/Inertia/.test(section.title)&&!/_ENABLE$|_DECAY$/.test(row.key||''));
    return view==='advanced'?advanced:!advanced;
  })})).filter(section=>section.rows.length);
}
function renderTpWorkspace(){
  const sideName=tpSideName();
  document.getElementById('tp-heading').textContent=`${sideName}トラックパッドを編集中`;
  document.getElementById('tp-side-caption').textContent=`${sideName}側を選択中`;
  document.querySelectorAll('.tp-btn[data-side]').forEach(button=>{
    const selected=button.dataset.side===state.tpSide;
    button.classList.toggle('active',selected);button.setAttribute('aria-pressed',String(selected));
  });
  document.querySelectorAll('[data-tp-view]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.tpView===state.tpView)));
  const actions=state.tpView==='actions';
  document.getElementById('tp-actions').classList.toggle('d-none',!actions);
  document.getElementById('tp-settings').classList.toggle('d-none',actions);
  document.getElementById('tp-settings-scope').classList.toggle('d-none',actions);
  if(actions) renderTpActions();
  else if(state.configLoaded[state.tpSide]) renderSettingsGrid(tpSettingsSchema(state.tpView),state.tpConfigs[state.tpSide],'tp-settings');
  else document.getElementById('tp-settings').replaceChildren(tpNode('p','tp-empty','設定を読み込めません。フォルダー設定を確認して、左右を選び直してください。'));
}
function renderTpActions(){
  const container=document.getElementById('tp-gesture-keys');if(!container) return;
  const panel=document.getElementById('tp-action-editor');
  container.replaceChildren();
  const copy=document.getElementById('tp-gesture-copy-btn');
  copy.textContent=`このレイヤーの割り当てを${state.tpSide==='left'?'右':'左'}へコピー`;
  copy.disabled=!state.layers.length;
  if(!state.layers.length || !state.configLoaded[state.tpSide]){
    container.appendChild(tpNode('p','tp-empty',!state.layers.length?'キーマップを読み込むと操作の割り当てが表示されます。':'この側の設定を読み込めません。フォルダー設定を確認して、左右を選び直してください。'));
    panel.replaceChildren();return;
  }
  const cfg=state.tpConfigs[state.tpSide],bindings=state.layers[state.currentLayer]?.bindings||[],rows=tpActionRows(state.tpSide,cfg);
  if(!rows.some(row=>row.id===state.tpSelected)) state.tpSelected='tap1';
  const head=tpNode('div','tp-table-head');head.append(tpNode('span','','操作'),tpNode('span','','割り当て・動作'));container.appendChild(head);
  let group='';
  for(const row of rows){
    if(row.group!==group){container.appendChild(tpNode('h3','tp-action-group',row.group));group=row.group;}
    const button=tpButton('',()=>{
      clearTpEditingContext();state.tpSelected=row.id;renderTpActions();
      if(window.matchMedia('(max-width:720px)').matches) panel.scrollIntoView({block:'start',behavior:'smooth'});
    },'tp-action-row');
    button.dataset.tpAction=row.id;button.setAttribute('aria-pressed',String(row.id===state.tpSelected));
    const label=tpNode('span','',row.label),output=tpNode('span','tp-output',tpActionOutput(row,cfg,bindings));
    if(row.hold) label.appendChild(tpNode('small','','タップと同じ割り当てを使用'));
    if(row.idx===undefined) label.appendChild(tpNode('small','','モード：全レイヤー共通'));
    button.classList.toggle('is-disabled',row.enableKey?cfg[row.enableKey]==='n':row.idx===undefined&&getGestureMode(cfg,row.modeKey)==='0');
    if(row.idx!==undefined&&isLayerBindingChanged(state.currentLayer,row.idx)) button.classList.add('changed-outline-inset','rpc');
    if([row.enableKey,row.modeKey].filter(Boolean).some(key=>isConfigKeyChanged(state.tpSide,key))) button.classList.add('changed-outline-inset');
    button.append(label,output);container.appendChild(button);
  }
  renderTpActionEditor(rows.find(row=>row.id===state.tpSelected),cfg,bindings);
}
function tpEditScope(){return {side:state.tpSide,layer:state.currentLayer,id:state.tpSelected};}
function tpScopeMatches(scope){return scope.side===state.tpSide&&scope.layer===state.currentLayer&&scope.id===state.tpSelected&&state.currentTab==='trackpad'&&state.tpView==='actions';}
function pickTpCustomBinding(row,category){
  const scope=tpEditScope();
  const apply=raw=>{if(!tpScopeMatches(scope)) return;setBinding(row.idx,raw);clearPaletteContext();};
  activatePaletteContext({tab:'trackpad',title:`${tpSideName()} / レイヤー ${scope.layer} / ${row.label}`,note:'キーを選ぶと、この操作に割り当てます。',initialCat:category,catIds:DEFAULT_BINDING_CAT_IDS,target:{type:'gesture',idx:row.idx},onPick:raw=>{
    if(!tpScopeMatches(scope)) return;
    if(needsFollowUpPicker(raw)) openTemplateFollowUpPicker({tab:'trackpad',title:row.label,target:{type:'gesture',idx:row.idx},template:raw,onComplete:apply});
    else apply(raw);
  }});
}
function renderTpActionEditor(row,cfg,bindings){
  const panel=document.getElementById('tp-action-editor');panel.replaceChildren();
  const scope=tpEditScope();
  panel.append(tpNode('h3','',row.idx===undefined?'動作を選択':'割り当てを選択'),tpNode('p','tp-editor-context',`${tpSideName()} / レイヤー ${state.currentLayer} / ${row.label}`));
  if(row.idx===undefined){
    const select=tpNode('select','sselect tp-mode-select');select.setAttribute('aria-label',`${row.label}のモード`);
    for(const [value,label] of [['1',row.axis==='vertical'?'縦スクロール':'横スクロール'],['2','キー操作'],['0','無効']]){
      const option=tpNode('option','',label);option.value=value;select.appendChild(option);
    }
    select.value=getGestureMode(cfg,row.modeKey);
    select.onchange=()=>{if(!tpScopeMatches(scope)) return;clearTpEditingContext();setGestureMode(cfg,row.modeKey,select.value);renderTpActions();};
    panel.append(select,tpNode('p','','この側の全レイヤー共通です。変更の反映には Save All とファームウェアの再ビルド・書き込みが必要です。'));
    if(select.value!=='2'){
      const details=tpNode('details','tp-inactive-bindings');details.appendChild(tpNode('summary','','保存済みのキー割り当て（現在は未使用）'));
      for(const [direction,label] of row.axis==='vertical'?[['up','上'],['down','下']]:[['left','左'],['right','右']]){
        details.appendChild(tpNode('div','',`${label}：${tpBindingName(bindings[gestureActionPosition(state.tpSide,row.fingers,direction)]?.raw||'&trans')}`));
      }
      panel.appendChild(details);
    } else panel.appendChild(tpNode('p','','一覧の各方向を選択して、キー操作を割り当ててください。'));
    return;
  }
  const raw=bindings[row.idx]?.raw||'&trans';
  panel.appendChild(tpNode('p','tp-editor-current',`現在：${tpActionOutput(row,cfg,bindings)}`));
  if(row.enableKey){
    const label=tpNode('label','tp-choice tp-editor-enable'),input=tpNode('input');input.type='checkbox';input.checked=cfg[row.enableKey]==='y';
    input.setAttribute('aria-label',`${row.label}を有効にする`);
    input.onchange=()=>{if(!tpScopeMatches(scope)) return;cfg[row.enableKey]=input.checked?'y':'n';markUnsaved();renderTpActions();};
    label.append(input,tpNode('span','','この操作を有効にする'));panel.append(label,tpNode('p','','有効・無効は全レイヤー共通。変更にはファームウェア更新が必要です。'));
  }
  if(row.hold) panel.appendChild(tpNode('p','','長押しはタップと同じ入力を押したままにします。割り当てを変えると、同じ指のタップにも適用されます。'));
  if(row.pinch) panel.appendChild(tpNode('p','','ピンチ中に押す修飾キーを選びます。Ctrl + ホイールは対応アプリで拡大・縮小になります。'));
  const choices=row.pinch?[['&kp LCTRL','Ctrl'],['&kp LEFT_SHIFT','Shift'],['&kp LALT','Alt'],['&none','修飾キーなし'],['&trans','下位レイヤーから継承']]:[['&mkp LCLK','左クリック'],['&mkp RCLK','右クリック'],['&mkp MCLK','中央クリック'],['&none','割り当てなし'],['&trans','下位レイヤーから継承']];
  const canonical={'&mkp MB1':'&mkp LCLK','&mkp MB2':'&mkp RCLK','&mkp MB3':'&mkp MCLK'}[raw]||raw;
  if(!choices.some(([value])=>value===canonical)) choices.unshift([raw,tpBindingName(raw)]);
  let selected=raw;
  for(const [value,name] of choices){
    const label=tpNode('label','tp-choice'),radio=tpNode('input');radio.type='radio';radio.name='tp-output-choice';radio.value=value;radio.checked=value===canonical;
    radio.onchange=()=>{selected=value;};label.append(radio,tpNode('span','',name));panel.appendChild(label);
  }
  panel.appendChild(tpButton('この操作に割り当て',()=>{if(tpScopeMatches(scope)){clearTpEditingContext();setBinding(row.idx,selected);setStatus(`${tpSideName()} / レイヤー ${state.currentLayer} / ${row.label} の割り当てを変更しました。`,'s-ok');}},'btn primary tp-apply'));
  panel.appendChild(tpButton('キー・ショートカットを選ぶ',()=>pickTpCustomBinding(row,'basic'),'btn tp-editor-secondary'));
  if(!row.pinch) panel.appendChild(tpButton('マクロを選ぶ',()=>pickTpCustomBinding(row,'macro_pal'),'btn tp-editor-secondary'));
  panel.appendChild(tpNode('p','tp-inactive-bindings','対応するキー割り当てはRPCで反映できます。マクロの定義変更などはファームウェア更新が必要です。'));
  const details=tpNode('details','tp-inactive-bindings');details.append(tpNode('summary','','割り当てコード'),tpNode('code','',raw));panel.appendChild(details);
}
