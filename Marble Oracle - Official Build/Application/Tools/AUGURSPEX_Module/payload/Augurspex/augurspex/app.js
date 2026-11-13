'use strict';
// AUGURSPEX 1.2 — source-aware market data, no login or Yahoo scraping.
const $ = id => document.getElementById(id);
const CHART_SRC = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
const LAYOUTS = [1, 2, 4, 6, 9];
const DEFAULT = ['BTC-USD', '4568.T', 'NVDA', 'COH.AX', '005930.KS', 'ETH-USD', 'RMD.AX', 'CSL.AX', '4519.T'];
const KRYPTO = {'BTC-USD':'BTC/USD', 'ETH-USD':'ETH/USD','SOL-USD':'SOL/USD','XRP-USD':'XRP/USD'};
const CRYPTO_REVERSE = Object.fromEntries(Object.entries(KRYPTO).map(([a,b]) => [b,a]));
const TV_KNOWN = {'AAPL':'NASDAQ:AAPL','NVDA':'NASDAQ:NVDA','MSFT':'NASDAQ:MSFT','SPY':'AMEX:SPY', 'EWY':'AMEX:EWY','QQQ':'NASDAQ:QQQ','^GSPC':'SP:SPX','^IXIC':'NASDAQ:IXIC','^DJI':'DJ:DJI','BTC-USD':'KRAKEN:BTCUSD','ETH-USD':'KRAKEN:ETHUSD','SOL-USD':'KRAKEN:SOLUSD','XRP-USD':'KRAKEN:XRPUSD'};
const SUFFIXES = [['.AX','ASX'],['.T','TSE'],['.KS','KRX'],['.KQ','KOSDAQ'],['.L','LSE']];
// Only markets confirmed in TradingView's public widget market directory.
const EMBED_MARKETS = new Set(['KRAKEN','COINBASE','BINANCE','BITSTAMP','ASX','CHIXAU', 'NASDAQ','NYSE','AMEX','NYSEARCA','CBOE','SP','DJ','BSE','MSEI','SSE','SZSE','IDX','TPEX','TOCOM']);
const PRESET_SLOTS = {
  Healthcare:['RMD.AX','COH.AX','CSL.AX','SHL.AX','4568.T','4519.T','4543.T','RHC.AX','NVDA'],
  Crypto:['BTC-USD','ETH-USD','SOL-USD','XRP-USD','NVDA','COH.AX','RMD.AX','AAPL','MSFT']
};
const state = {token:'',settings:null,watchlist:[],source:null,active:0, cards:new Map(),focus:null,quotes:new Map(),ws:null,wsRetry:0,wsTimer:0,cbws:null,cbRetry:0,cbTimer:0,venueQuotes:new Map(),quoteClock:0,nowTimer:0};
let saveQueue = Promise.resolve();let toastTimer = 0;let cryptoPaintTimer = 0;

function mapSymbol(raw){
  if(typeof raw !== 'string')return '';
  const s=raw.trim().toUpperCase();
  if(!/^[A-Z0-9^.=+:-]{1,48}$/.test(s))return '';
  if(TV_KNOWN[s])return TV_KNOWN[s];
  if(s.includes(':'))return /^[A-Z0-9_]+:[A-Z0-9.\-]+$/.test(s)?s:'';
  for(const [suffix, exchange] of SUFFIXES)if(s.endsWith(suffix)&&s.length>suffix.length)return exchange+':'+s.slice(0,-suffix.length);
  return '';
}
function exchangeFor(symbol){return (mapSymbol(symbol).split(':')[0]||'');}
function availability(symbol){
  const ex=exchangeFor(symbol);
  if(!ex)return {status:'invalid',label:'Unknown listing',detail:'Choose an explicit exchange and ticker.'};
  if(['TSE','KRX','KOSDAQ'].includes(ex))return {status:'unavailable',label:'Embed unavailable',detail:'This exchange is not listed in TradingView’s public widget data directory. No different company will be substituted.'};
  if(!EMBED_MARKETS.has(ex))return {status:'unavailable',label:'Unverified exchange',detail:'This exchange is not confirmed in the public widget directory. The app will not risk displaying another company’s chart.'};
  if(['KRAKEN','COINBASE','BINANCE','BITSTAMP'].includes(ex))return {status:'live',label:'Crypto · live feed',detail:'TradingView crypto widget; live Kraken spot quote shown separately when connected.'};
  if(ex==='ASX')return {status:'delayed',label:'ASX · ~20m delayed',detail:'ASX widget quotes can be delayed by approximately 20 minutes under exchange rules.'};
  if(ex==='CHIXAU')return {status:'live',label:'Cboe AU · provider live',detail:'Cboe Australia feed may be real-time; verify this exact listing in the widget.'};
  if(['NASDAQ','NYSE','AMEX','NYSEARCA','CBOE'].includes(ex))return {status:'delayed',label:'US · delay possible',detail:'US stock widget feed can differ from primary-exchange live prices.'};
  return {status:'delayed',label:'Provider data',detail:'Public chart feed is controlled by TradingView; check chart source and timestamp.'};
}
function groupFor(item){
  const ex=exchangeFor(item.symbol);
  if(['KRAKEN','COINBASE','BINANCE','BITSTAMP'].includes(ex))return 'CRYPTO';
  if(['ASX','CHIXAU'].includes(ex))return 'AUSTRALIA';
  if(ex==='TSE')return 'JAPAN';
  if(['KRX','KOSDAQ'].includes(ex))return 'SOUTH KOREA';
  if(['SP','DJ'].includes(ex)||item.symbol.startsWith('^'))return 'INDICES';
  if(['NASDAQ','NYSE','NYSEARCA','AMEX','CBOE'].includes(ex))return 'UNITED STATES';
  return 'OTHER MARKETS';
}
const GROUPS = ['CRYPTO','AUSTRALIA','JAPAN','SOUTH KOREA','UNITED STATES','INDICES','OTHER MARKETS'];
function stockItem(symbol){return state.watchlist.find(x=>x.symbol===symbol)||{symbol,name:symbol,tv:mapSymbol(symbol)};}
function safeName(item){return (item.name||item.symbol||'').trim();}
function toast(msg,error=false){const x=$('toast');x.textContent=msg;x.classList.toggle('error',error);x.classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>x.classList.remove('show'),5200);}
function setStatus(s){$('statusText').textContent=s;}
function copySnapshot(s){return {layout:s.layout,interval:s.interval,style:s.style,symbols:[...s.symbols]};}
function recordWorkspace(){state.settings.workspaces[state.settings.workspace]=copySnapshot(state.settings);}
function save(){
  if(!state.settings||!state.token)return;
  recordWorkspace();
  const payload=structuredClone(state.settings);
  saveQueue=saveQueue.catch(()=>{}).then(async()=>{
    const response=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json','X-Augurspex-Token':state.token},body:JSON.stringify(payload)});
    if(!response.ok)throw new Error('Could not save layout on this computer');
  }).catch(e=>toast(e.message,true));
}
function ensureSelections(){
  const s=state.settings;
  if(!Array.isArray(s.symbols))s.symbols=[];
  // Preserve imported choices, never silently replace a TSE ticker with a US stock.
  s.symbols=s.symbols.slice(0,9).map(x=>mapSymbol(x)?x:'');
  while(s.symbols.length<9)s.symbols.push('');
  if(!s.symbols.some(Boolean))s.symbols=state.watchlist.length?[state.watchlist[0].symbol,...Array(8).fill('')]:Array(9).fill('');
}
function getQuote(symbol){
  const venues=state.venueQuotes.get(symbol)||new Map();
  const selected=state.settings?.quote_provider||'auto';
  const now=Date.now();
  const fresh=[...venues.values()].filter(q=>Number.isFinite(q.price)&&q.price>0&&now-q.received<45000&&now-(q.timestamp||q.received)<45000&&q.timestamp<=now+10000);
  const matches=selected==='auto'?fresh:fresh.filter(q=>q.venue===selected);
  // Prefer actual exchange trade timestamps. Kraken snapshots without an event
  // timestamp have only an arrival timestamp and are labelled as such.
  matches.sort((a,b)=>Number(b.hasTradeTime)-Number(a.hasTradeTime)||(b.timestamp||b.received)-(a.timestamp||a.received));
  return matches[0]||null;
}
function storeQuote(symbol,venue,price,pct,timestamp,hasTradeTime){
  const now=Date.now();if(!Number.isFinite(price)||price<=0)return false;
  if(!state.venueQuotes.has(symbol))state.venueQuotes.set(symbol,new Map());
  const time=Number.isFinite(timestamp)&&timestamp<=now+10000?timestamp:now;
  const q={venue,price,pct,received:now,timestamp:time,hasTradeTime:!!hasTradeTime};
  state.venueQuotes.get(symbol).set(venue,q);
  const chosen=getQuote(symbol);if(chosen)state.quotes.set(symbol,chosen);
  return true;
}
function fmtMoney(value){
  if(!Number.isFinite(value))return '—';
  return new Intl.NumberFormat('en-AU',{maximumFractionDigits:value<1?5:2,minimumFractionDigits:value<1?4:2}).format(value);
}
function renderQuotes(){
  const root=$('liveQuotes');root.replaceChildren();
  for(const [sym] of Object.entries(KRYPTO)){
    const q=getQuote(sym);
    const btn=document.createElement('button');btn.type='button';btn.className='quote-chip';btn.title='Show '+sym+' in selected chart';
    const short=document.createElement('strong');short.textContent=sym.split('-')[0];
    const price=document.createElement('span');price.className='price';price.textContent=q?'$'+fmtMoney(q.price):'—';
    const change=document.createElement('span');change.className='change';
    if(q && Number.isFinite(q.pct)){change.textContent=(q.pct>=0?'+':'')+q.pct.toFixed(2)+'%';change.classList.add(q.pct<0?'down':'up');}
    else change.textContent='';
    const venue=document.createElement('span');venue.className='venue';venue.textContent=q?q.venue+' spot':'No fresh feed';
    const age=document.createElement('span');age.className='age';age.textContent=q?Math.round((Date.now()-q.received)/1000)+'s':'';
    btn.title=q?'Latest '+(q.hasTradeTime?'trade at ':'update received ')+new Date(q.timestamp).toLocaleTimeString()+' · '+q.venue:'No fresh trade available';
    btn.append(short,price,change,venue,age);btn.addEventListener('click',()=>assign(state.active,sym));root.append(btn);
  }
}
function renderWatchlist(){
  const root=$('watchlist');root.replaceChildren();
  const term=$('watchSearch').value.toLowerCase().trim();const filter=state.settings.watch_filter;
  const favorites=new Set(state.settings.favorites);
  document.querySelectorAll('[data-filter]').forEach(b=>{const yes=b.dataset.filter===filter;b.classList.toggle('active',yes);b.setAttribute('aria-pressed',String(yes));});
  const rows=state.watchlist.filter(item=>{
    if(filter==='favorites'&&!favorites.has(item.symbol))return false;
    if(filter==='crypto'&&groupFor(item)!=='CRYPTO')return false;
    if(filter==='stocks'&&groupFor(item)==='CRYPTO')return false;
    return [item.symbol,item.name,item.tv].some(v=>String(v||'').toLowerCase().includes(term));
  });
  $('watchCount').textContent=String(state.watchlist.length);
  if(!rows.length){const empty=document.createElement('p');empty.className='no-results';empty.textContent='No markets match this filter';root.append(empty);return;}
  const grouped=new Map();
  rows.forEach(x=>{const g=groupFor(x);if(!grouped.has(g))grouped.set(g,[]);grouped.get(g).push(x)});
  for(const group of [...grouped.keys()].sort((a,b)=>GROUPS.indexOf(a)-GROUPS.indexOf(b))){
    const title=document.createElement('div');title.className='group-title';title.textContent=group;root.append(title);
    grouped.get(group).sort((a,b)=>Number(favorites.has(b.symbol))-Number(favorites.has(a.symbol))).forEach(item=>{
      const row=document.createElement('div');row.className='watch-row';
      if(state.settings.symbols[state.active]===item.symbol)row.classList.add('selected');
      const pick=document.createElement('button');pick.type='button';pick.className='watch-pick';pick.title='Show '+safeName(item)+' in chart '+(state.active+1);
      const line=document.createElement('span');line.className='watch-symbol-line';
      const ticker=document.createElement('span');ticker.className='watch-tick';ticker.textContent=item.symbol;
      const q=getQuote(item.symbol);const price=document.createElement('span');price.className='watch-price';price.dataset.symbol=item.symbol;price.textContent=q?'$'+fmtMoney(q.price):'';
      const name=document.createElement('span');name.className='watch-name';name.textContent=safeName(item);
      line.append(ticker,price);pick.append(line,name);pick.addEventListener('click',()=>assign(state.active,item.symbol));
      const star=document.createElement('button');star.type='button';star.className='star'+(favorites.has(item.symbol)?' on':'');star.title=favorites.has(item.symbol)?'Remove favourite':'Save as favourite';star.setAttribute('aria-label',star.title);star.textContent=favorites.has(item.symbol)?'★':'☆';
      star.addEventListener('click',()=>{const next=new Set(state.settings.favorites);next.has(item.symbol)?next.delete(item.symbol):next.add(item.symbol);state.settings.favorites=[...next];renderWatchlist();save();});
      const remove=document.createElement('button');remove.type='button';remove.className='watch-remove';remove.title='Remove '+item.symbol;remove.setAttribute('aria-label','Remove '+item.symbol);remove.textContent='×';
      remove.addEventListener('click',async()=>{if(!window.confirm('Remove '+item.symbol+' from your AUGURSPEX watchlist?'))return;await setWatchlist('replace',state.watchlist.filter(x=>x.symbol!==item.symbol),true);});
      row.append(pick,star,remove);root.append(row);
    });
  }
}
function renderLayouts(){document.querySelectorAll('#layouts button').forEach(b=>{const current=Number(b.dataset.count)===state.settings.layout;b.classList.toggle('active',current);b.setAttribute('aria-pressed',String(current));});}
function tvLink(symbol){const ticker=mapSymbol(symbol);return ticker?'https://www.tradingview.com/chart/?symbol='+encodeURIComponent(ticker):'https://www.tradingview.com/widget/';}
function externalMarketLink(symbol){
  const ticker=mapSymbol(symbol),[ex,code]=ticker.split(':');
  // Public Google Finance pages identify these original exchange listings correctly.
  if(ex==='TSE')return {href:'https://www.google.com/finance/quote/'+encodeURIComponent(code+':TYO'),label:'Open on Google Finance ↗'};
  if(ex==='KRX')return {href:'https://www.google.com/finance/quote/'+encodeURIComponent(code+':KRX'),label:'Open on Google Finance ↗'};
  return {href:tvLink(symbol),label:'Open public market page ↗'};
}
function renderAll(){
  ensureSelections();renderLayouts();renderWatchlist();renderQuotes();
  $('workspace').value=state.settings.workspace;
  $('interval').value=state.settings.interval;$('chartStyle').value=state.settings.style;$('chartSize').value=state.settings.chart_size;
  $('sourceMode').value=state.settings.chart_provider||'auto';$('quoteProvider').value=state.settings.quote_provider||'auto';
  $('appShell').classList.toggle('sidebar-hidden',state.settings.sidebar_collapsed);
  const grid=$('chartGrid');grid.className='chart-grid layout-'+state.settings.layout+' size-'+state.settings.chart_size;
  const retain=state.focus!==null && state.focus<state.settings.layout;
  if(!retain)state.focus=null;
  for(const old of state.cards.values()){
    if(old._abort)old._abort.abort();
    if(old._observer)old._observer.disconnect();
    if(old._timeout)clearTimeout(old._timeout);
  }
  grid.replaceChildren();state.cards.clear();
  for(let i=0;i<state.settings.layout;i++){
    const card=createCard(i);grid.append(card);state.cards.set(i,card);
  }
  focusCards();
  for(let i=0;i<state.settings.layout;i++){
    const card=state.cards.get(i);
    setTimeout(()=>{if(state.cards.get(i)===card)loadWidget(i);},i*300);
  }
  setStatus(state.settings.layout+' charts · '+state.settings.workspace+' · Selected chart '+(state.active+1));
}
function createCard(slot){
  const card=document.createElement('article');card.className='chart-card';card.dataset.slot=String(slot);
  const header=document.createElement('div');header.className='chart-head';
  const number=document.createElement('span');number.className='chart-index';number.textContent=String(slot+1).padStart(2,'0');
  const dropdown=document.createElement('select');dropdown.className='market-select';dropdown.setAttribute('aria-label','Market for chart '+(slot+1));
  const groups=new Map();state.watchlist.forEach(item=>{const g=groupFor(item);if(!groups.has(g))groups.set(g,[]);groups.get(g).push(item);});
  for(const g of [...groups.keys()].sort((a,b)=>GROUPS.indexOf(a)-GROUPS.indexOf(b))){
    const optionGroup=document.createElement('optgroup');optionGroup.label=g;
    groups.get(g).forEach(item=>{const o=document.createElement('option');o.value=item.symbol;o.textContent=item.symbol+' · '+safeName(item);optionGroup.append(o);});dropdown.append(optionGroup);
  }
  const selected=state.settings.symbols[slot];
  if(selected && !state.watchlist.some(x=>x.symbol===selected)){
    const o=document.createElement('option');o.value=selected;o.textContent=selected;dropdown.prepend(o);
  }
  dropdown.value=selected;
  dropdown.addEventListener('change',e=>assign(slot,e.target.value));
  const actions=document.createElement('div');actions.className='card-tools';
  const focus=document.createElement('button');focus.type='button';focus.className='card-icon';focus.title='Expand this chart';focus.setAttribute('aria-label','Expand chart '+(slot+1));focus.textContent='⛶';focus.addEventListener('click',()=>toggleFocus(slot));
  const refresh=document.createElement('button');refresh.type='button';refresh.className='card-icon';refresh.title='Reconnect this chart';refresh.setAttribute('aria-label','Reconnect chart '+(slot+1));refresh.textContent='↻';refresh.addEventListener('click',()=>{state.active=slot;focusCards();loadWidget(slot,true);});
  const link=document.createElement('a');link.className='card-icon';link.title='Open market chart in browser';link.setAttribute('aria-label','Open chart '+(slot+1)+' externally');link.href=externalMarketLink(selected).href;link.target='_blank';link.rel='noopener noreferrer';link.textContent='↗';
  actions.append(focus,refresh,link);header.append(number,dropdown,actions);
  header.addEventListener('click',e=>{if(e.target.closest('button,select,a'))return;state.active=slot;focusCards();renderWatchlist();});
  const sub=document.createElement('div');sub.className='chart-meta';const ticker=document.createElement('span');ticker.className='chart-ticker';
  const badge=document.createElement('span');badge.className='market-badge';sub.append(ticker,badge);
  const view=document.createElement('div');view.className='chart-view';
  const foot=document.createElement('div');foot.className='chart-footer';
  const info=document.createElement('span');info.className='card-info';
  const attrib=document.createElement('a');attrib.href='https://www.tradingview.com/widget/';attrib.target='_blank';attrib.rel='noopener noreferrer';attrib.textContent='Chart source · TradingView';
  foot.append(info,attrib);card.append(header,sub,view,foot);
  card._view=view;card._ticker=ticker;card._badge=badge;card._info=info;card._dropdown=dropdown;card._focus=focus;card._open=link;card._observer=null;card._timeout=0;card._abort=null;
  updateCardInfo(card,selected);return card;
}
function updateCardInfo(card,symbol){
  const a=availability(symbol);card._ticker.textContent=mapSymbol(symbol)||'Select market';
  card._badge.textContent=a.label;card._badge.className='market-badge'+(a.status==='unavailable'||a.status==='invalid'?' unavailable':a.status==='delayed'?' delayed':'');
  if(KRYPTO[symbol] && getQuote(symbol)){
    const q=getQuote(symbol);card._info.textContent=q.venue+' spot $'+fmtMoney(q.price)+' · '+(q.hasTradeTime?'Trade ':'Update ')+new Date(q.timestamp||q.received).toLocaleTimeString();
  }else{
    card._info.textContent=a.status==='unavailable'?'No embedded feed for this exchange':a.status==='delayed'?'Stock feed may be delayed':'TradingView hosted chart';
  }
}
function focusCards(){
  const grid=$('chartGrid');grid.classList.toggle('focus-mode',state.focus!==null);
  for(const [i,card] of state.cards){
    card.classList.toggle('focused',i===state.active);card.classList.toggle('expanded',i===state.focus);
    card._focus.classList.toggle('active',i===state.focus);card._focus.title=state.focus===i?'Return to all charts':'Expand this chart';
    card._focus.textContent=state.focus===i?'⤢':'⛶';
  }
  $('exitFocus').hidden=state.focus===null;
}
function setSidebarVisible(visible){
  $('sidebar').classList.toggle('visible',Boolean(visible));
  $('sidebarBackdrop').hidden=!visible;
}
function toggleFocus(slot){state.focus=state.focus===slot?null:slot;state.active=slot;focusCards();renderWatchlist();if(state.focus!==null)$('chartGrid').scrollIntoView({block:'start',behavior:'smooth'});}
function assign(slot,symbol){
  if(!mapSymbol(symbol)){toast('Select a market with an explicit exchange.',true);return;}
  state.settings.symbols[slot]=symbol;state.active=slot;
  const card=state.cards.get(slot);
  if(card){if(![...card._dropdown.options].some(x=>x.value===symbol)){const o=new Option(symbol,symbol);card._dropdown.prepend(o);}card._dropdown.value=symbol;card._open.href=externalMarketLink(symbol).href;updateCardInfo(card,symbol);loadWidget(slot,true);}
  focusCards();renderWatchlist();save();
  if(window.innerWidth<980)setSidebarVisible(false);
}
function widgetConfiguration(symbol){
  return {autosize:true, symbol:mapSymbol(symbol), interval:state.settings.interval,
    timezone:'exchange', theme:'dark',style:state.settings.style,locale:'en',
    backgroundColor:'#10151c',gridColor:'rgba(145,161,175,0.10)',
    hide_top_toolbar:true,hide_side_toolbar:true,hide_legend:true,hide_volume:true,
    allow_symbol_change:false,withdateranges:false,save_image:false,calendar:false,
    details:false,hotlist:false,support_host:'https://www.tradingview.com',
    watchlist:[],studies:[],compareSymbols:[]};
}
function putMessage(view,kind,heading,message,external){
  view.replaceChildren();const layer=document.createElement('div');layer.className='widget-message '+kind;
  const h=document.createElement('strong');h.textContent=heading;const p=document.createElement('small');p.textContent=message;layer.append(h,p);
  if(external){const a=document.createElement('a');a.className='external-link';a.href=typeof external==='string'?external:external.href;a.rel='noopener noreferrer';a.target='_blank';a.textContent=typeof external==='string'?'Open external chart ↗':external.label;layer.append(a);}
  view.append(layer);return layer;
}
function loadHostedWidget(slot,manual=false){
  const card=state.cards.get(slot);if(!card)return;
  if(card._abort){card._abort.abort();card._abort=null;}
  const symbol=state.settings.symbols[slot];const a=availability(symbol);const view=card._view;
  if(card._observer){card._observer.disconnect();card._observer=null;}
  if(card._timeout){clearTimeout(card._timeout);card._timeout=0;}
  if(a.status==='invalid'){putMessage(view,'warn','Choose a market','Use the watchlist or the ticker selector to choose a market.');return;}
  if(a.status==='unavailable'){
    putMessage(view,'warn','No verified chart for '+mapSymbol(symbol),a.detail,externalMarketLink(symbol));
    return;
  }
  view.replaceChildren();
  const embed=document.createElement('div');embed.className='tradingview-widget-container';
  const body=document.createElement('div');body.className='tradingview-widget-container__widget';embed.append(body);
  const overlay=document.createElement('div');overlay.className='widget-message';
  const spinner=document.createElement('span');spinner.className='spinner';const status=document.createElement('span');status.textContent='Connecting to '+mapSymbol(symbol)+'…';overlay.append(spinner,status);
  view.append(embed,overlay);
  const fail=reason=>{
    if(!view.isConnected||!view.contains(overlay))return;
    overlay.className='widget-message failed';overlay.replaceChildren();
    const h=document.createElement('strong');h.textContent='Chart could not load';const p=document.createElement('small');p.textContent=reason;
    const ext=document.createElement('a');ext.className='external-link';ext.href=tvLink(symbol);ext.target='_blank';ext.rel='noopener noreferrer';ext.textContent='Open external chart ↗';
    overlay.append(h,p,ext);
  };
  const observer=new MutationObserver(()=>{
    if(embed.querySelector('iframe')){overlay.hidden=true;observer.disconnect();if(card._timeout){clearTimeout(card._timeout);card._timeout=0;}}
  });
  observer.observe(embed,{childList:true,subtree:true});card._observer=observer;
  const script=document.createElement('script');script.type='text/javascript';script.async=true;script.src=CHART_SRC;
  script.textContent=JSON.stringify(widgetConfiguration(symbol));script.onerror=()=>fail('The hosted widget is unavailable. Check your connection or content blocker.');
  embed.append(script);
  card._timeout=setTimeout(()=>{if(!embed.querySelector('iframe'))fail('The hosted chart did not respond in 20 seconds.');},20000);
  if(manual)toast('Loading '+mapSymbol(symbol));
}
async function setWatchlist(mode,items,allowEmpty=false){
  try{
    const r=await fetch('/api/watchlist',{method:'POST',headers:{'Content-Type':'application/json','X-Augurspex-Token':state.token},body:JSON.stringify({mode,items,confirm_empty:allowEmpty})});
    const data=await r.json();if(!r.ok)throw new Error(data.error||'Could not save the market list');
    state.watchlist=data.items;state.source=data.source;
    state.settings.favorites=state.settings.favorites.filter(s=>state.watchlist.some(x=>x.symbol===s));
    // Keep chart slots pointing to the chosen symbol if it was intentionally removed, but clear it visually.
    for(let i=0;i<state.settings.symbols.length;i++)if(!state.watchlist.some(x=>x.symbol===state.settings.symbols[i]))state.settings.symbols[i]='';
    renderAll();save();return data;
  }catch(e){toast(e.message,true);return null;}
}
async function addMarket(e){
  e.preventDefault();const sym=$('addSymbol').value.trim().toUpperCase(),tv=mapSymbol(sym);
  if(!tv){toast('Enter EXCHANGE:TICKER (ASX:BHP, NASDAQ:AMD) or a supported .AX/.T suffix.',true);return;}
  if(state.watchlist.some(x=>x.symbol===sym)){assign(state.active,sym);toast('Already in your watchlist');return;}
  const data=await setWatchlist('merge',[{symbol:sym,name:sym}]);
  if(data){state.settings.symbols[state.active]=sym;$('addSymbol').value='';renderAll();save();toast(sym+' added locally');}
}

// CSV supports quoted company names, commas and CRLF; all processing remains local.
function parseCsv(input){
  const result=[];let row=[],field='',quoted=false;
  for(let i=0;i<input.length;i++){
    const ch=input[i];
    if(ch==='"'){
      if(quoted&&input[i+1]==='"'){field+='"';i++;}
      else quoted=!quoted;
    }else if(!quoted&&ch===','){row.push(field);field='';}
    else if(!quoted&&(ch==='\n'||ch==='\r')){if(ch==='\r'&&input[i+1]==='\n')i++;row.push(field);if(row.some(v=>v.trim()))result.push(row);row=[];field='';}
    else field+=ch;
  }
  if(quoted)throw new Error('CSV contains an unclosed quotation mark');
  row.push(field);if(row.some(v=>v.trim()))result.push(row);
  return result;
}
function importSymbol(raw,ex){
  let s=String(raw??'').trim().toUpperCase(),e=String(ex??'').trim().toUpperCase();
  if(!s)return '';
  if(!mapSymbol(s)&&e&&/^[A-Z0-9_]+$/.test(e))s=e+':'+s;
  return mapSymbol(s)?s:'';
}
function normalizeImportEntry(raw){
  const item=typeof raw==='string'?{symbol:raw}:raw;
  if(!item||typeof item!=='object'||Array.isArray(item))return null;
  const rawSymbol=item.symbol??item.ticker??item.code??item.instrument??item.Symbol??item.Ticker;
  const symbol=importSymbol(rawSymbol,item.exchange??item.market??item.Exchange??'');
  if(!symbol)return null;
  const name=String(item.name??item.long_name??item.company??item.Name??item.Company??symbol).trim().slice(0,110)||symbol;
  return {symbol,name,tv:mapSymbol(symbol)};
}
function parseImportText(text,filename){
  const trimmed=text.trim();if(!trimmed)throw new Error('The selected file is empty');
  let raw=[];
  if(filename.toLowerCase().endsWith('.json')||trimmed.startsWith('{')||trimmed.startsWith('[')){
    const parsed=JSON.parse(trimmed);
    raw=Array.isArray(parsed)?parsed:parsed.markets??parsed.stocks??parsed.watchlist??parsed.assets??parsed.symbols??[];
    if(!Array.isArray(raw))throw new Error('JSON must contain a markets, stocks, watchlist, assets or symbols array');
  }else if(filename.toLowerCase().endsWith('.csv')||trimmed.split('\n')[0].includes(',')){
    const rows=parseCsv(trimmed);const header=rows[0].map(c=>c.replace(/^\uFEFF/,'').trim().toLowerCase());
    const symbolCol=header.findIndex(c=>['symbol','ticker','code','instrument','security'].includes(c));
    if(symbolCol>=0){
      const nameCol=header.findIndex(c=>['name','company','long_name','description'].includes(c));
      const exchangeCol=header.findIndex(c=>['exchange','market','venue'].includes(c));
      raw=rows.slice(1).map(row=>({symbol:row[symbolCol],name:nameCol<0?'':row[nameCol],exchange:exchangeCol<0?'':row[exchangeCol]}));
    }else raw=rows.map(row=>({symbol:row[0],name:row[1]||''}));
  }else raw=trimmed.split(/\r?\n/).map(s=>({symbol:s.trim()}));
  if(raw.length>300)throw new Error('Maximum 300 markets per import');
  const good=[],bad=[];const seen=new Set();
  raw.forEach((entry,index)=>{const normalized=normalizeImportEntry(entry);if(!normalized){bad.push(index+1);return;}if(!seen.has(normalized.symbol)){good.push(normalized);seen.add(normalized.symbol);}});
  return {good,bad,total:raw.length};
}
let importDraft=null;
async function previewImport(file){
  importDraft=null;$('applyImport').disabled=true;
  if(!file){$('importPreview').textContent='Select a file to preview its symbols before importing.';return;}
  if(file.size>1024*1024){$('importPreview').textContent='File too large (maximum 1 MB).';return;}
  try{
    const parsed=parseImportText(await file.text(),file.name);importDraft=parsed;
    const box=$('importPreview');box.replaceChildren();
    const line=document.createElement('strong');line.className='preview-good';line.textContent=parsed.good.length+' valid unique markets / '+parsed.total+' entries';box.append(line);
    if(parsed.bad.length){const warn=document.createElement('p');warn.className='preview-bad';warn.textContent=parsed.bad.length+' unsupported or invalid rows (numbers: '+parsed.bad.slice(0,18).join(', ')+'). These will be skipped.';box.append(warn);}
    const list=document.createElement('div');list.textContent=parsed.good.slice(0,15).map(x=>x.symbol+' · '+x.name).join('  |  ')+(parsed.good.length>15?' …':'');box.append(list);
    $('applyImport').disabled=!parsed.good.length;
  }catch(e){$('importPreview').textContent='Could not read file: '+e.message;}
}
function downloadFile(name,content,mime){
  const url=URL.createObjectURL(new Blob([content],{type:mime}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),3000);
}
function exportWatchlist(format){
  if(format==='json'){
    downloadFile('augurspex-markets.json',JSON.stringify({format:'augurspex-watchlist-v1',markets:state.watchlist.map(({symbol,name})=>({symbol,name}))},null,2)+'\n','application/json');
  }else{
    const escape=v=>'"'+String(v??'').replaceAll('"','""')+'"';
    const csv='symbol,name\r\n'+state.watchlist.map(x=>escape(x.symbol)+','+escape(x.name)).join('\r\n')+'\r\n';
    downloadFile('augurspex-markets.csv',csv,'text/csv;charset=utf-8');
  }
}

function useWorkspace(name){
  const old=state.settings.workspace;state.settings.workspaces[old]=copySnapshot(state.settings);
  state.settings.workspace=name;
  let snap=state.settings.workspaces[name];
  if(!snap){
    snap={layout:4,interval:'D',style:'2',symbols:[...(PRESET_SLOTS[name]||DEFAULT)]};
    state.settings.workspaces[name]=structuredClone(snap);
  }
  Object.assign(state.settings,copySnapshot(snap));state.active=0;state.focus=null;
  renderAll();save();toast('Loaded '+name+' workspace');
}
function updateCryptoStatus(status){
  const el=$('streamStatus'),dot=$('streamDot');el.textContent=status;
  dot.classList.toggle('connected',status==='Connected · live trades');
}
function cryptoRefresh(){
  renderQuotes();
  updateVenueHealth();
  // Keep DOM nodes and scroll position stable while live ticks arrive.
  document.querySelectorAll('.watch-price').forEach(el=>{const q=getQuote(el.dataset.symbol);el.textContent=q?'$'+fmtMoney(q.price):'';});
  for(let i=0;i<state.settings.layout;i++){const c=state.cards.get(i);if(c)updateCardInfo(c,state.settings.symbols[i]);}
  if(state.ws && state.ws.readyState===WebSocket.OPEN){
    const live=[...state.venueQuotes.values()].some(v=>[...v.values()].some(q=>Date.now()-q.received<45000));
    const stale=state.venueQuotes.size>0;
    updateCryptoStatus(live?'Connected · live trades':stale?'Connected · quotes stale':'Connected · awaiting trades');
  }
}
function startKraken(){
  if(!('WebSocket' in window)){updateCryptoStatus('WebSocket unavailable');return;}
  if(state.ws && (state.ws.readyState===WebSocket.OPEN||state.ws.readyState===WebSocket.CONNECTING))return;
  updateCryptoStatus('Connecting to Kraken…');
  let ws;
  try{ws=new WebSocket('wss://ws.kraken.com/v2');}catch(_){updateCryptoStatus('Connection unavailable');return;}
  state.ws=ws;
  ws.addEventListener('open',()=>{
    if(state.ws!==ws)return;state.wsRetry=0;
    ws.send(JSON.stringify({method:'subscribe',params:{channel:'ticker',symbol:Object.values(KRYPTO),event_trigger:'trades',snapshot:true}}));
    updateCryptoStatus('Connected · awaiting trades');
  });
  ws.addEventListener('message',e=>{
    let msg;try{msg=JSON.parse(e.data);}catch(_){return;}
    if(msg.channel!=='ticker'||!Array.isArray(msg.data))return;
    let changed=false;
    for(const record of msg.data){
      const sym=CRYPTO_REVERSE[record.symbol],price=Number(record.last);
      if(!sym || !Number.isFinite(price) || price<=0)continue;
      const pct=record.change_pct===undefined?NaN:Number(record.change_pct);
      const timestamp=Date.parse(record.timestamp||'');
      storeQuote(sym,'kraken',price,pct,Number.isFinite(timestamp)?timestamp:Date.now(),Number.isFinite(timestamp));changed=true;
    }
    if(changed && !cryptoPaintTimer){cryptoPaintTimer=setTimeout(()=>{cryptoPaintTimer=0;cryptoRefresh();},300);}
  });
  const reconnect=()=>{
    if(state.ws!==ws)return;state.ws=null;
    updateCryptoStatus('Disconnected · reconnecting');
    clearTimeout(state.wsTimer);
    const delay=Math.min(30000,2000*Math.pow(2,Math.min(4,state.wsRetry++)));
    state.wsTimer=setTimeout(startKraken,delay);
  };
  ws.addEventListener('close',reconnect);
  ws.addEventListener('error',()=>{updateCryptoStatus('Feed connection error');try{ws.close();}catch(_){/* nop */}});
}
function clockTick(){
  $('localClock').textContent=new Date().toLocaleTimeString(undefined,{hour:'2-digit',minute:'2-digit'});
  // Recalculate freshness without inventing a market quote.
  cryptoRefresh();
}

/* Multiple public markets, source integrity, and safe local historical OHLC. */
function updateVenueHealth(){
  const available=['kraken','coinbase'].map(venue=>{
    let fresh=false;
    for(const pair of state.venueQuotes.values())if(pair.has(venue)&&Date.now()-pair.get(venue).received<45000)fresh=true;
    return venue[0].toUpperCase()+venue.slice(1)+(fresh?' live':' waiting');
  });
  const el=$('quoteVenueStatus');if(el)el.textContent=available.join(' · ');
  const fresh=available.some(s=>s.endsWith('live'));
  if(fresh)updateCryptoStatus('Connected · live trades');
  else if(state.venueQuotes.size)updateCryptoStatus('Connected · quotes stale');
}
function startCoinbase(){
  if(!('WebSocket' in window))return;
  if(state.cbws && [WebSocket.OPEN,WebSocket.CONNECTING].includes(state.cbws.readyState))return;
  let ws;
  try{ws=new WebSocket('wss://ws-feed.exchange.coinbase.com');}catch(_){return;}
  state.cbws=ws;
  ws.addEventListener('open',()=>{
    if(state.cbws!==ws)return;
    state.cbRetry=0;
    ws.send(JSON.stringify({type:'subscribe',product_ids:Object.keys(KRYPTO),channels:['ticker']}));
    updateVenueHealth();
  });
  ws.addEventListener('message',e=>{
    let msg;try{msg=JSON.parse(e.data);}catch(_){return;}
    if(msg.type!=='ticker'||!Object.prototype.hasOwnProperty.call(KRYPTO,msg.product_id))return;
    const price=Number(msg.price),open=Number(msg.open_24h),t=Date.parse(msg.time||'');
    const pct=Number.isFinite(open)&&open>0?100*(price/open-1):NaN;
    if(storeQuote(msg.product_id,'coinbase',price,pct,t,Number.isFinite(t)))cryptoRefresh();
  });
  const reconnect=()=>{
    if(state.cbws!==ws)return;state.cbws=null;
    clearTimeout(state.cbTimer);
    state.cbTimer=setTimeout(startCoinbase,Math.min(30000,1500*2**Math.min(5,state.cbRetry++)));
    updateVenueHealth();
  };
  ws.addEventListener('close',reconnect);
  ws.addEventListener('error',()=>{try{ws.close()}catch(_){/* nop */}});
}
async function loadProviders(){
  try{
    const r=await fetch('/api/providers');if(!r.ok)throw new Error('Cannot access local provider registry');
    const data=await r.json();const dir=$('providerDirectory');const grid=document.createElement('div');grid.className='provider-list';
    for(const [key,info] of Object.entries(data.sources||{})){
      const item=document.createElement('div');item.className='provider-list-item';
      const name=document.createElement('strong');name.textContent=info.name;
      const content=document.createElement('span');content.textContent=info.coverage+' · '+info.timeliness;
      item.append(name,content);grid.append(item);
    }
    dir.replaceChildren(grid);
    $('providerStatus').textContent='Public feeds · explicit currency, source and observation date';
  }catch(e){$('providerStatus').textContent='Provider directory unavailable: '+e.message;}
}
async function loadFx(){
  const fx=$('fxReference');
  try{
    const r=await fetch('/api/fx?base=AUD&quote=USD');const d=await r.json();
    if(!r.ok||!Number.isFinite(Number(d.rate)))throw new Error(d.error||'FX unavailable');
    fx.textContent='AUD/USD '+Number(d.rate).toFixed(4)+' · '+(d.observation_date||'date unknown')+' reference';
    fx.title=d.note+' · '+d.source+' · '+(d.cache||'network');
  }catch(e){fx.textContent='AUD/USD reference unavailable';fx.title=e.message;}
}
function localSourceChoices(symbol){
  const ex=exchangeFor(symbol);
  if(KRYPTO[symbol])return true;
  return ['NASDAQ','NYSE','NYSEARCA','AMEX','CBOE','ASX','TSE','KRX','KOSDAQ'].includes(ex);
}
function loadWidget(slot,manual=false){
  const card=state.cards.get(slot);if(!card)return;
  const sym=state.settings.symbols[slot],availabilityInfo=availability(sym);
  const mode=state.settings.chart_provider||'auto';
  if(mode==='hosted'||(mode==='auto'&&availabilityInfo.status!=='unavailable')){
    loadHostedWidget(slot,manual);return;
  }
  if(!localSourceChoices(sym)){
    if(mode==='auto')loadHostedWidget(slot,manual);
    else putMessage(card._view,'warn','No public OHLC source for '+mapSymbol(sym),'This exchange has no verified keyless historical feed. No substitute ticker will be used.',externalMarketLink(sym));
    return;
  }
  loadPublicChart(slot,manual);
}
function formatObservation(s,asset='crypto'){
  if(asset==='equity')return /^\d{4}-\d{2}-\d{2}/.test(s||'')?s.slice(0,10)+' trading session':'date unknown';
  const t=Date.parse(s);return Number.isFinite(t)?new Date(t).toLocaleString(undefined,{year:'numeric',month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}):'date unknown';
}
function loadPublicChart(slot,manual=false){
  const card=state.cards.get(slot);if(!card)return;
  if(card._abort)card._abort.abort();
  const controller=new AbortController();card._abort=controller;
  if(card._observer){card._observer.disconnect();card._observer=null;}
  if(card._timeout){clearTimeout(card._timeout);card._timeout=0;}
  const sym=state.settings.symbols[slot],view=card._view;
  putMessage(view,'','Requesting public history for '+mapSymbol(sym),'Daily stock history or venue-specific spot OHLC. No account or key.');
  const qs=new URLSearchParams({symbol:sym,period:state.settings.interval,source:'auto'});
  fetch('/api/history?'+qs.toString(),{signal:controller.signal}).then(async r=>{
    const d=await r.json();if(!r.ok)throw new Error(d.error||'Public OHLC unavailable');return d;
  }).then(d=>{
    if(card._abort!==controller||!view.isConnected)return;
    drawLocalChart(view,d,sym,card,controller);
    const cache=d.cache==='stale'?'STALE CACHE':d.cache==='fresh'?'CACHED':'UPDATED';
    card._info.textContent=d.source+' · '+cache+' · Last '+formatObservation(d.latest_observation,d.asset);
    card._badge.textContent=d.asset==='equity'?'EOD · '+d.source:'Spot OHLC · '+d.source;
    card._badge.className='market-badge'+(d.asset==='equity'?' delayed':'');
  }).catch(e=>{
    if(e.name==='AbortError'||card._abort!==controller)return;
    putMessage(view,'failed','Public data unavailable for '+mapSymbol(sym),e.message,externalMarketLink(sym));
    card._info.textContent='No verified local history · '+e.message.slice(0,110);
  });
  if(manual)toast('Checking public source: '+mapSymbol(sym));
}
function drawLocalChart(view,d,symbol,card,controller){
  view.replaceChildren();
  const canvas=document.createElement('canvas');canvas.setAttribute('role','img');
  canvas.setAttribute('aria-label',d.source+' historical price chart for '+symbol+'; last '+d.latest_observation);
  view.append(canvas);
  const caption=document.createElement('div');caption.className='local-chart-legend';
  caption.textContent=d.source+' · '+d.currency+' · '+(d.asset==='equity'?'DAILY close':'SPOT OHLC')+(d.cache==='stale'?' · STALE':'');
  view.append(caption);
  const footer=document.createElement('div');footer.className='local-chart-watermark';
  footer.textContent='Last observation '+formatObservation(d.latest_observation,d.asset)+' · '+(d.warning||d.note);
  view.append(footer);
  const hover=document.createElement('div');hover.className='public-chart-info';view.append(hover);
  const rows=d.candles||[];
  if(!rows.length){putMessage(view,'failed','No candles returned','The provider returned an empty history.');return;}
  let plot;
  const draw=()=>{
    if(!view.isConnected||card._abort!==controller)return;
    const rect=canvas.getBoundingClientRect();const w=Math.max(200,rect.width),h=Math.max(220,rect.height);
    const ratio=Math.min(2,window.devicePixelRatio||1);canvas.width=Math.round(w*ratio);canvas.height=Math.round(h*ratio);
    const ctx=canvas.getContext('2d');if(!ctx)return;ctx.setTransform(ratio,0,0,ratio,0,0);
    const left=16,right=w-78,top=48,bottom=h-39;
    let low=Math.min(...rows.map(x=>x.low));let high=Math.max(...rows.map(x=>x.high));
    const pad=Math.max((high-low)*.08,high*.001,1e-8);low=Math.max(0,low-pad);high+=pad;
    const usableW=right-left,usableH=bottom-top;
    const yy=value=>bottom-(value-low)/(high-low)*usableH;
    const xx=i=>left+(i+.5)/rows.length*usableW;
    plot={left,right,top,bottom,xx,yy};
    ctx.clearRect(0,0,w,h);
    ctx.strokeStyle='#283947';ctx.lineWidth=1;ctx.fillStyle='#9bb1bd';ctx.font='11px system-ui';
    for(let t=0;t<=4;t++){const y=top+t*usableH/4;ctx.beginPath();ctx.moveTo(left,y);ctx.lineTo(right,y);ctx.stroke();ctx.fillText(fmtMoney(high-(high-low)*t/4),right+10,y+4);}
    const candleWidth=Math.max(1,Math.min(11,usableW/rows.length*.55));
    const candles=state.settings.style==='1';
    if(!candles){
      ctx.beginPath();rows.forEach((r,i)=>{const x=xx(i),y=yy(r.close);if(i)ctx.lineTo(x,y);else ctx.moveTo(x,y);});
      ctx.strokeStyle='#6bdbc3';ctx.lineWidth=1.8;ctx.stroke();
    }else{
      for(let i=0;i<rows.length;i++){
        const r=rows[i],x=xx(i),up=r.close>=r.open;
        ctx.strokeStyle=up?'#69d4b6':'#ee8e87';ctx.fillStyle=ctx.strokeStyle;
        ctx.beginPath();ctx.moveTo(x,yy(r.high));ctx.lineTo(x,yy(r.low));ctx.stroke();
        const topbody=Math.min(yy(r.open),yy(r.close));const bodyheight=Math.max(1.3,Math.abs(yy(r.close)-yy(r.open)));
        ctx.fillRect(x-candleWidth/2,topbody,candleWidth,bodyheight);
      }
    }
    for(const i of [0,Math.floor((rows.length-1)/2),rows.length-1]){
      const label=new Date(rows[i].time).toLocaleDateString(undefined,{month:'short',day:'numeric'});
      ctx.fillStyle='#91a8b4';ctx.fillText(label,Math.min(right-42,Math.max(left,xx(i)-24)),h-19);
    }
    hover.textContent='Close '+fmtMoney(rows.at(-1).close)+' '+d.currency;
  };
  draw();const observer=new ResizeObserver(()=>draw());observer.observe(view);
  // Abort old observers when panels are reselected; they do not poll the network.
  controller.signal.addEventListener('abort',()=>observer.disconnect(),{once:true});
  canvas.addEventListener('mousemove',e=>{
    if(!plot)return;
    const rect=canvas.getBoundingClientRect();const x=e.clientX-rect.left;
    const i=Math.max(0,Math.min(rows.length-1,Math.floor((x-plot.left)/(plot.right-plot.left)*rows.length)));
    const r=rows[i];hover.textContent=new Date(r.time).toLocaleDateString()+' · O '+fmtMoney(r.open)+' H '+fmtMoney(r.high)+' L '+fmtMoney(r.low)+' C '+fmtMoney(r.close)+' '+d.currency;
  });
  canvas.addEventListener('mouseleave',()=>{hover.textContent='Close '+fmtMoney(rows.at(-1).close)+' '+d.currency;});
}

async function boot(){
  try{
    const response=await fetch('/api/bootstrap');if(!response.ok)throw new Error('Cannot open local watchlist');
    const data=await response.json();state.token=data.token;state.settings=data.settings;state.watchlist=data.watchlist;state.source=data.source;
    if(!state.settings.workspaces||typeof state.settings.workspaces!=='object')state.settings.workspaces={};
    if(!Array.isArray(state.settings.favorites))state.settings.favorites=[];
    state.settings.workspace=state.settings.workspace||'Overview';
    state.settings.chart_size=state.settings.chart_size||'comfortable';state.settings.watch_filter=state.settings.watch_filter||'all';
    state.settings.workspaces[state.settings.workspace] ||= copySnapshot(state.settings);
    $('importNotice').textContent=data.source?.includes('/augurspex/watchlist.json')?'Your own AUGURSPEX list · Import, export or remove markets':data.source?'Read-only Merkato import · Edit freely in AUGURSPEX':'Starter markets · Import a CSV, JSON or TXT list';
    $('watchSearch').addEventListener('input',renderWatchlist);
    $('addForm').addEventListener('submit',addMarket);
    $('openImport').addEventListener('click',()=>{$('importDialog').showModal();$('listFile').value='';previewImport(null);});
    $('listFile').addEventListener('change',e=>previewImport(e.target.files[0]));
    $('applyImport').addEventListener('click',async()=>{
      if(!importDraft?.good.length)return;
      const mode=document.querySelector('input[name="importMode"]:checked').value;
      if(mode==='replace'&&!window.confirm('Replace your entire AUGURSPEX watchlist with '+importDraft.good.length+' markets? Your current local list will be backed up.'))return;
      const data=await setWatchlist(mode,importDraft.good);
      if(data){$('importDialog').close();toast('Imported '+importDraft.good.length+' markets · '+data.count+' total');}
    });
    $('exportCSV').addEventListener('click',()=>exportWatchlist('csv'));
    $('exportJSON').addEventListener('click',()=>exportWatchlist('json'));
    $('downloadTemplate').addEventListener('click',()=>downloadFile('augurspex-import-example.csv','symbol,name\r\n"ASX:RMD","ResMed"\r\n"TSE:4568","Daiichi Sankyo"\r\n"BTC-USD","Bitcoin"\r\n','text/csv;charset=utf-8'));

    document.querySelectorAll('[data-filter]').forEach(btn=>btn.addEventListener('click',()=>{state.settings.watch_filter=btn.dataset.filter;renderWatchlist();save();}));
    $('menuToggle').addEventListener('click',()=>{
      if(window.innerWidth<980)setSidebarVisible(!$('sidebar').classList.contains('visible'));
      else{state.settings.sidebar_collapsed=!state.settings.sidebar_collapsed;$('appShell').classList.toggle('sidebar-hidden',state.settings.sidebar_collapsed);save();}
    });
    $('closeSidebar').addEventListener('click',()=>setSidebarVisible(false));
    $('sidebarBackdrop').addEventListener('click',()=>setSidebarVisible(false));
    for(const b of document.querySelectorAll('#layouts button'))b.addEventListener('click',()=>{
      const n=Number(b.dataset.count);if(!LAYOUTS.includes(n))return;state.settings.layout=n;state.active=Math.min(state.active,n-1);if(state.focus!==null&&state.focus>=n)state.focus=null;renderAll();save();
    });
    $('workspace').addEventListener('change',e=>useWorkspace(e.target.value));
    $('interval').addEventListener('change',e=>{state.settings.interval=e.target.value;renderAll();save();});
    $('chartStyle').addEventListener('change',e=>{state.settings.style=e.target.value;renderAll();save();});
    $('chartSize').addEventListener('change',e=>{state.settings.chart_size=e.target.value;renderAll();save();});
    $('sourceMode').addEventListener('change',e=>{state.settings.chart_provider=e.target.value;renderAll();save();});
    $('quoteProvider').addEventListener('change',e=>{state.settings.quote_provider=e.target.value;cryptoRefresh();renderWatchlist();save();});
    $('providerDetails').addEventListener('click',()=>{$('providerDrawer').hidden=!$('providerDrawer').hidden;});
    $('reloadAll').addEventListener('click',()=>{for(const i of state.cards.keys())setTimeout(()=>loadWidget(i),i*240);toast('Reconnecting embedded charts');});
    $('exitFocus').addEventListener('click',()=>{state.focus=null;focusCards();});
    $('saveWorkspace').addEventListener('click',()=>{save();toast('Saved '+state.settings.workspace+' workspace on this computer');});
    $('quitButton').addEventListener('click',async()=>{
      try{await fetch('/api/quit',{method:'POST',headers:{'Content-Type':'application/json','X-Augurspex-Token':state.token},body:'{}'});$('quitOverlay').hidden=false;clearTimeout(state.wsTimer);clearTimeout(state.cbTimer);state.ws?.close();state.cbws?.close();}
      catch(e){toast('Could not stop app: '+e.message,true);}
    });
    window.addEventListener('keydown',e=>{
      if(e.key==='Escape'){state.focus=null;focusCards();setSidebarVisible(false);}
      if(e.key==='/'&&!/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName)){e.preventDefault();$('watchSearch').focus();}
      if(e.altKey&&/^[1-9]$/.test(e.key)&&Number(e.key)<=state.settings.layout){state.active=Number(e.key)-1;focusCards();renderWatchlist();}
    });
    window.addEventListener('pagehide',()=>{clearTimeout(state.wsTimer);clearInterval(state.quoteClock);clearInterval(state.nowTimer);if(state.ws)state.ws.close();if(state.cbws)state.cbws.close();clearTimeout(state.cbTimer);});
    renderAll();renderQuotes();startKraken();startCoinbase();loadProviders();loadFx();clockTick();
    state.quoteClock=setInterval(cryptoRefresh,10000);state.nowTimer=setInterval(clockTick,60000);
  }catch(e){setStatus('Could not start');toast(String(e.message||e),true);$('chartGrid').textContent='The local dashboard could not start. Launch the application again.';}
}
document.addEventListener('DOMContentLoaded',boot);
