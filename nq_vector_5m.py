#!/usr/bin/env python3
"""NQ Vector 5M - local CSV backtest dashboard. No trading or broker connection."""
import csv, io, json, math
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

PAGE = r'''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>NQ Vector 5M</title>
<style>
:root{color-scheme:dark;--bg:#0b0a12;--panel:#14121f;--line:#29243c;--purple:#a879ff;--muted:#a9a2bb;--good:#61d6a4;--bad:#ff758b}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:#f5f2fb;font:15px system-ui,Arial;padding:16px}.wrap{max-width:1000px;margin:auto}h1{font-size:25px;margin:6px 0}p{color:var(--muted);line-height:1.45}.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px;margin:14px 0}.grid{display:grid;grid-template-columns:repeat(4,minmax(125px,1fr));gap:10px}label{display:block;font-size:12px;color:var(--muted);margin-bottom:5px}input{width:100%;background:#0c0a14;color:#fff;border:1px solid var(--line);border-radius:8px;padding:10px;font-size:15px}input[type=file]{padding:8px}button{background:var(--purple);color:#160c27;border:0;border-radius:9px;padding:12px 18px;font-weight:700;font-size:15px;margin-top:12px;width:100%}button.alt{background:#281d3b;color:#eadfff;border:1px solid #59427d}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:9px}.metric{border:1px solid var(--line);border-radius:10px;padding:12px}.metric small{display:block;color:var(--muted)}.metric b{display:block;margin-top:5px;font-size:20px}.status{color:var(--muted);white-space:pre-wrap}.good{color:var(--good)}.bad{color:var(--bad)}canvas{width:100%;height:190px;background:#0c0a14;border-radius:9px}table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;border-bottom:1px solid var(--line);padding:8px 5px;white-space:nowrap}th{color:var(--muted)}.scroll{overflow:auto}.note{font-size:13px}.pill{color:#d8c5ff;background:#261b3b;padding:4px 8px;border-radius:99px;font-size:12px}@media(max-width:650px){body{padding:10px}.grid{grid-template-columns:repeat(2,1fr)}.metrics{grid-template-columns:repeat(2,1fr)}h1{font-size:22px}}
</style></head><body><main class="wrap"><span class="pill">LOCAL CSV BACKTEST · PAPER ONLY</span><h1>NQ Vector 5M</h1><p>Prueba una estrategia de retroceso a favor de tendencia en barras de 5 minutos. El panel funciona localmente en tu teléfono; no conecta con brokers ni envía órdenes.</p>
<div class="card"><label>Archivo CSV de MNQ</label><input id="file" type="file" accept=".csv,text/csv"><p class="note">Acepta CSV de NinjaTrader Minute (incluye exportaciones con punto y coma, sin encabezado y hora UTC) y archivos OHLCV con encabezados. Convierte y agrupa los datos a barras de 5 minutos.</p><div class="grid">
<div><label>EMA rápida</label><input id="fast" type="number" value="20"></div><div><label>EMA lenta</label><input id="slow" type="number" value="50"></div><div><label>ATR</label><input id="atr" type="number" value="14"></div><div><label>Objetivo (R)</label><input id="target" type="number" value="1.5" step="0.1"></div>
<div><label>MNQ valor por punto ($)</label><input id="point" type="number" value="2" step="0.25"></div><div><label>Contratos</label><input id="qty" type="number" value="1" min="1"></div><div><label>Comisión total ida/vuelta por contrato ($)</label><input id="commission" type="number" value="1.5" step="0.01"></div><div><label>Deslizamiento por lado (puntos)</label><input id="slippage" type="number" value="0.25" step="0.25"></div>
<div><label>Máx. operaciones por día</label><input id="maxtrades" type="number" value="3"></div><div><label>Límite pérdida diaria (R)</label><input id="daily" type="number" value="2" step="0.25"></div><div><label>Inicio sesión (hora CSV)</label><input id="start" type="time" value="09:35"></div><div><label>Fin sesión (hora CSV)</label><input id="end" type="time" value="15:55"></div>
</div><button id="run">Ejecutar backtest</button><button id="export" class="alt" style="display:none">Exportar NinjaScript C# (.cs)</button><div class="status" id="status"></div><p class="note">El archivo C# es para revisar y validar en NinjaTrader Strategy Analyzer. No lo actives en una cuenta real sin comparar sus operaciones y probarlo en simulación.</p></div>
<div id="results" style="display:none"><div class="card"><div class="metrics" id="metrics"></div></div><div class="card"><b>Curva de capital (PnL neto acumulado)</b><canvas id="chart" width="950" height="220"></canvas></div><div class="card"><b>Operaciones</b><div class="scroll"><table><thead><tr><th>Entrada</th><th>Lado</th><th>Precio</th><th>Salida</th><th>Precio</th><th>Motivo</th><th>PnL neto</th><th>R</th></tr></thead><tbody id="trades"></tbody></table></div></div></div>
<div class="card note"><b>Reglas incluidas</b><p>EMA rápida/lenta + precio respecto al VWAP de sesión; retroceso a EMA rápida en las 3 barras previas; vela de confirmación que supera el máximo/mínimo previo. Entrada en la apertura de la siguiente barra. Stop más allá del mínimo/máximo reciente con margen ATR; objetivo por múltiplo R. Si stop y objetivo aparecen dentro de la misma barra, el backtest asume primero el stop (supuesto conservador). Alcanza el límite de pérdida diaria y deja de abrir operaciones ese día.</p><p><b>Importante:</b> no demuestra rentabilidad futura. Incluye tus costos estimados, revisa que el CSV no tenga datos faltantes y valida en periodos no usados para ajustar parámetros antes de paper trading.</p></div></main>
<script>
const $=id=>document.getElementById(id);function val(id){return Number($(id).value)}let lastConfig=null;
function config(){return {fast:val('fast'),slow:val('slow'),atr:val('atr'),target:val('target'),point_value:val('point'),qty:val('qty'),commission:val('commission'),slippage:val('slippage'),max_trades:val('maxtrades'),daily_stop_r:val('daily'),session_start:$('start').value,session_end:$('end').value}}
$('run').onclick=async()=>{let f=$('file').files[0];$('export').style.display='none';if(!f){$('status').textContent='Selecciona primero el CSV de MNQ.';return} $('status').textContent='Procesando el archivo…';$('results').style.display='none';try{let body={csv:await f.text(),config:config()};let r=await fetch('/backtest',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});let d=await r.json();if(!r.ok)throw Error(d.error||'Error de backtest');lastConfig=body.config;show(d);$('export').style.display='block'}catch(e){$('status').textContent='No se pudo ejecutar: '+e.message}}
$('export').onclick=async()=>{if(!lastConfig)return;try{let r=await fetch('/export',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({config:lastConfig})});if(!r.ok){let d=await r.json();throw Error(d.error||'No se pudo exportar')}let blob=await r.blob(),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='NQVector5M_Export.cs';a.click();URL.revokeObjectURL(url)}catch(e){$('status').textContent='No se pudo exportar: '+e.message}}
function money(x){return '$'+Number(x).toFixed(2)}function show(d){$('status').textContent=`CSV: ${d.bars} barras · ${d.trades.length} operaciones · ${d.period}`;let m=[['PnL neto',money(d.metrics.net)],['Win rate',d.metrics.win_rate.toFixed(1)+'%'],['Expectativa / trade',money(d.metrics.expectancy)],['Factor de ganancia',d.metrics.profit_factor===null?'—':d.metrics.profit_factor.toFixed(2)],['Drawdown máximo',money(d.metrics.max_drawdown)],['Trades ganadores',d.metrics.wins],['Trades perdedores',d.metrics.losses],['R medio',d.metrics.avg_r.toFixed(2)+'R']];$('metrics').innerHTML=m.map(x=>`<div class="metric"><small>${x[0]}</small><b class="${x[0]==='PnL neto'?(d.metrics.net>=0?'good':'bad'):''}">${x[1]}</b></div>`).join('');$('trades').innerHTML=d.trades.slice().reverse().map(t=>`<tr><td>${t.entry_time}</td><td>${t.side}</td><td>${t.entry.toFixed(2)}</td><td>${t.exit_time}</td><td>${t.exit.toFixed(2)}</td><td>${t.reason}</td><td class="${t.pnl>=0?'good':'bad'}">${money(t.pnl)}</td><td>${t.r_multiple.toFixed(2)}</td></tr>`).join('');draw(d.equity);$('results').style.display='block'}
function draw(a){let c=$('chart'),x=c.getContext('2d'),w=c.width,h=c.height;x.clearRect(0,0,w,h);if(!a.length)return;let mn=Math.min(0,...a),mx=Math.max(0,...a);if(mx===mn)mx=mn+1;x.strokeStyle='#a879ff';x.lineWidth=2;x.beginPath();a.forEach((v,i)=>{let px=i*(w-20)/Math.max(1,a.length-1)+10,py=h-10-(v-mn)*(h-20)/(mx-mn);i?x.lineTo(px,py):x.moveTo(px,py)});x.stroke();x.strokeStyle='#39334b';x.beginPath();let zy=h-10-(0-mn)*(h-20)/(mx-mn);x.moveTo(0,zy);x.lineTo(w,zy);x.stroke()}
</script></body></html>'''

ALIASES = {
 'timestamp':['timestamp','datetime','date_time','time','date','bar_time'],
 'open':['open','o'], 'high':['high','h'], 'low':['low','l'],
 'close':['close','c'], 'volume':['volume','vol','v']
}
def utc_to_new_york(dt):
    # US DST rules in effect since 2007: second Sunday in March at 07:00 UTC
    # through first Sunday in November at 06:00 UTC. Avoids requiring tzdata
    # on Android/Termux while correctly handling the recent MNQ data used here.
    def nth_sunday(year, month, n):
        first_weekday=datetime(year,month,1).weekday()  # Monday=0, Sunday=6
        first_sunday=1+(6-first_weekday)%7
        return first_sunday+7*(n-1)
    year=dt.year
    dst_start=datetime(year,3,nth_sunday(year,3,2),7,0)
    dst_end=datetime(year,11,nth_sunday(year,11,1),6,0)
    return dt+timedelta(hours=-4 if dst_start<=dt<dst_end else -5)

def parse_csv(raw):
    raw=raw.lstrip('\ufeff')
    # Some NinjaTrader exports wrap each complete semicolon-delimited row in
    # one pair of quotes. Remove only that outer pair before parsing columns.
    cleaned=[]
    for line in raw.splitlines():
        line=line.strip()
        if line.startswith('"') and line.endswith('"'):
            line=line[1:-1].replace('""','"')
        cleaned.append(line)
    raw='\n'.join(cleaned)
    first=next((line for line in raw.splitlines() if line.strip()),'')
    delimiter=';' if first.count(';')>first.count(',') else ','
    records=list(csv.reader(io.StringIO(raw),delimiter=delimiter))
    records=[r for r in records if r and any(x.strip() for x in r)]
    if not records: raise ValueError('El archivo CSV está vacío.')
    normalized=[x.strip().lower().replace(' ','_') for x in records[0]]
    all_aliases={a for group in ALIASES.values() for a in group}
    has_header=any(x in all_aliases or x in ('date','date/time','datetime') for x in normalized)
    ninja_headerless=not has_header
    if ninja_headerless:
        if len(records[0])!=6:
            raise ValueError('El CSV de NinjaTrader sin encabezados debe tener 6 columnas: fecha/hora, open, high, low, close, volume.')
        body=records
        headers=['timestamp','open','high','low','close','volume']
    else:
        headers=records[0]
        body=records[1:]
        normalized=[x.strip().lower().replace(' ','_') for x in headers]
        keys={norm:original for norm,original in zip(normalized,headers)}
        cols={}
        for key, opts in ALIASES.items():
            found=next((keys[x] for x in opts if x in keys),None)
            if key=='timestamp' and 'date' in keys and 'time' in keys and found in (keys['date'],keys['time']):
                found=(keys['date'],keys['time'])
            if not found: raise ValueError('Falta columna requerida: '+key+' (encabezados detectados: '+', '.join(headers)+')')
            cols[key]=found
    rows=[]
    for n,values in enumerate(body,2 if has_header else 1):
        if len(values)<6: continue
        try:
            if ninja_headerless:
                ts=values[0].strip()
                vals=values[1:6]
            else:
                r=dict(zip(headers,values))
                if isinstance(cols['timestamp'],tuple): ts=(r[cols['timestamp'][0]]+' '+r[cols['timestamp'][1]]).strip()
                else: ts=r[cols['timestamp']].strip()
                vals=[r[cols[k]] for k in ('open','high','low','close','volume')]
            try: dt=datetime.fromisoformat(ts.replace('Z','+00:00'))
            except ValueError:
                dt=None
                for fmt in ('%Y%m%d %H%M%S','%Y%m%d %H%M','%m/%d/%Y %H:%M:%S','%m/%d/%Y %H:%M','%m/%d/%Y %I:%M:%S %p','%m/%d/%Y %I:%M %p','%Y/%m/%d %H:%M:%S','%Y/%m/%d %H:%M'):
                    try: dt=datetime.strptime(ts,fmt);break
                    except ValueError: pass
                if dt is None: raise ValueError('Formato de fecha/hora no reconocido')
            if ninja_headerless:
                # NinjaTrader exports historical timestamps in UTC and end-of-bar time.
                dt=utc_to_new_york(dt)
            elif dt.tzinfo is not None:
                dt=utc_to_new_york(dt.astimezone(timezone.utc).replace(tzinfo=None))
            row={'dt':dt,'open':float(vals[0]),'high':float(vals[1]),'low':float(vals[2]),'close':float(vals[3]),'volume':float(vals[4] or 0)}
            if row['high']<max(row['open'],row['close']) or row['low']>min(row['open'],row['close']) or row['high']<row['low']: raise ValueError('OHLC inválido')
            rows.append(row)
        except Exception as e: raise ValueError(f'Error en fila {n}: {e}')
    rows.sort(key=lambda x:x['dt'])
    if ninja_headerless:
        # NinjaTrader's Minute export contains 1-minute bars. Combine complete
        # groups of five end-stamped bars into the 5-minute bars this strategy uses.
        grouped={}
        for row in rows:
            dt=row['dt'].replace(second=0,microsecond=0)
            minute=((dt.minute+4)//5)*5
            if minute>=60:
                dt=dt.replace(minute=0)+timedelta(hours=1)
            else:
                dt=dt.replace(minute=minute)
            grouped.setdefault(dt,[]).append(row)
        rows=[]
        for dt,bars in sorted(grouped.items()):
            if len(bars)!=5: continue
            rows.append({'dt':dt,'open':bars[0]['open'],'high':max(x['high'] for x in bars),'low':min(x['low'] for x in bars),'close':bars[-1]['close'],'volume':sum(x['volume'] for x in bars)})
    if len(rows)<100: raise ValueError('Se necesitan al menos 100 barras para calcular indicadores con sentido.')
    return rows

def ema(vals,period):
    a=2/(period+1); out=[None]*len(vals)
    if not vals:return out
    out[0]=vals[0]
    for i in range(1,len(vals)):out[i]=a*vals[i]+(1-a)*out[i-1]
    return out

def compute(rows,cfg):
    fast,slow,ap=int(cfg['fast']),int(cfg['slow']),int(cfg['atr'])
    if min(fast,slow,ap)<2 or fast>=slow: raise ValueError('EMA rápida debe ser menor que EMA lenta; períodos deben ser al menos 2.')
    if cfg['target']<=0 or cfg['point_value']<=0 or cfg['qty']<1 or cfg['commission']<0 or cfg['slippage']<0: raise ValueError('Revisa objetivo, contratos y costos.')
    if cfg['max_trades']<1 or cfg['daily_stop_r']<=0: raise ValueError('Límite diario y operaciones deben ser mayores que cero.')
    start=cfg['session_start']; end=cfg['session_end']
    if start>=end: raise ValueError('La hora de inicio debe ser anterior al fin de sesión.')
    n=len(rows); cls=[r['close'] for r in rows]
    ef=ema(cls,fast); es=ema(cls,slow)
    atr=[None]*n; tr=[]
    for i,r in enumerate(rows):
        true=max(r['high']-r['low'],abs(r['high']-rows[i-1]['close']) if i else 0,abs(r['low']-rows[i-1]['close']) if i else 0);tr.append(true)
        if i>=ap-1:atr[i]=sum(tr[i-ap+1:i+1])/ap
    vw=[None]*n; accum_pv=accum_v=0; lastday=None; in_session=[False]*n
    for i,r in enumerate(rows):
        day=r['dt'].date()
        if day!=lastday:accum_pv=accum_v=0;lastday=day
        hm=r['dt'].strftime('%H:%M'); active=start<=hm<=end
        in_session[i]=active
        if active:
            typ=(r['high']+r['low']+r['close'])/3; v=max(0,r['volume']);accum_pv+=typ*v;accum_v+=v
            vw[i]=accum_pv/accum_v if accum_v else r['close']
    trades=[]; equity=[]; realized=0; peak=0; maxdd=0
    day_stats={}; i=max(slow,ap+3,4)
    while i<n-1:
        row=rows[i]; d=row['dt'].date(); hm=row['dt'].strftime('%H:%M')
        st=day_stats.setdefault(str(d),{'count':0,'r':0})
        if not in_session[i] or hm>=end or atr[i] is None or vw[i] is None:
            i+=1;continue
        if st['count']>=cfg['max_trades'] or st['r']<=-cfg['daily_stop_r']:
            i+=1;continue
        # Signal candle closes beyond prior candle extreme after a recent EMA20 pullback.
        prior=rows[i-3:i]
        touch_long=any(p['low']<=ef[j]+0.12*atr[i] for j,p in zip(range(i-3,i),prior))
        touch_short=any(p['high']>=ef[j]-0.12*atr[i] for j,p in zip(range(i-3,i),prior))
        long=ef[i]>es[i] and row['close']>vw[i] and row['close']>row['open'] and row['close']>rows[i-1]['high'] and touch_long
        short=ef[i]<es[i] and row['close']<vw[i] and row['close']<row['open'] and row['close']<rows[i-1]['low'] and touch_short
        if not (long or short): i+=1;continue
        side='LONG' if long else 'SHORT'; sign=1 if long else -1; ent_i=i+1
        if not in_session[ent_i] or rows[ent_i]['dt'].date()!=d: i+=1;continue
        ent_raw=rows[ent_i]['open']; ent=ent_raw+sign*cfg['slippage']
        swing=min(x['low'] for x in rows[i-3:i+1]) if long else max(x['high'] for x in rows[i-3:i+1])
        stop=swing-0.10*atr[i] if long else swing+0.10*atr[i]
        risk=sign*(ent-stop)
        if risk<=0 or risk>3*atr[i]:i+=1;continue
        target=ent+sign*risk*cfg['target']; stop_px=stop
        exit_i=None; reason='SESSION'; raw_exit=rows[ent_i]['close']
        for j in range(ent_i,n):
            if rows[j]['dt'].date()!=d or rows[j]['dt'].strftime('%H:%M')>end:
                exit_i=j-1;raw_exit=rows[exit_i]['close'];break
            hitstop=rows[j]['low']<=stop_px if long else rows[j]['high']>=stop_px
            hittarget=rows[j]['high']>=target if long else rows[j]['low']<=target
            if hitstop and hittarget:exit_i=j;raw_exit=stop_px;reason='STOP (same bar)';break
            if hitstop:exit_i=j;raw_exit=stop_px;reason='STOP';break
            if hittarget:exit_i=j;raw_exit=target;reason='TARGET';break
        if exit_i is None:exit_i=n-1;raw_exit=rows[-1]['close'];reason='END DATA'
        exitp=raw_exit-sign*cfg['slippage']; pnl=(exitp-ent)*sign*cfg['point_value']*cfg['qty']-cfg['commission']*cfg['qty']
        risk_cash=risk*cfg['point_value']*cfg['qty']; rm=pnl/risk_cash if risk_cash else 0
        trades.append({'entry_time':row['dt'].strftime('%Y-%m-%d %H:%M'),'side':side,'entry':ent,'exit_time':rows[exit_i]['dt'].strftime('%Y-%m-%d %H:%M'),'exit':exitp,'reason':reason,'pnl':pnl,'r_multiple':rm})
        realized+=pnl;st['count']+=1;st['r']+=rm;peak=max(peak,realized);maxdd=max(maxdd,peak-realized);equity.append(round(realized,2));i=exit_i+1
    wins=sum(t['pnl']>0 for t in trades);losses=sum(t['pnl']<0 for t in trades);gp=sum(t['pnl'] for t in trades if t['pnl']>0);gl=-sum(t['pnl'] for t in trades if t['pnl']<0)
    net=sum(t['pnl'] for t in trades); ntr=len(trades)
    metrics={'net':net,'win_rate':100*wins/ntr if ntr else 0,'expectancy':net/ntr if ntr else 0,'profit_factor':gp/gl if gl else (None if gp==0 else 999),'max_drawdown':maxdd,'wins':wins,'losses':losses,'avg_r':sum(t['r_multiple'] for t in trades)/ntr if ntr else 0}
    return {'bars':len(rows),'period':rows[0]['dt'].strftime('%Y-%m-%d')+' to '+rows[-1]['dt'].strftime('%Y-%m-%d'),'metrics':metrics,'trades':trades,'equity':equity}

def generate_ninjascript(cfg):
    def number(key,default):
        value=float(cfg.get(key,default))
        if not math.isfinite(value): raise ValueError('Parámetro inválido: '+key)
        return format(value,'.6g')
    def integer(key,default,minimum=1):
        value=int(cfg.get(key,default))
        if value<minimum: raise ValueError('Parámetro inválido: '+key)
        return str(value)
    def hhmm(key,default):
        value=str(cfg.get(key,default))
        try:
            h,m=map(int,value.split(':'))
            if h not in range(24) or m not in range(60): raise ValueError
            return f'{h:02d}{m:02d}'
        except Exception: raise ValueError('Hora inválida: '+key)
    values={
      '__FAST__':integer('fast',20,2),'__SLOW__':integer('slow',50,3),'__ATR__':integer('atr',14,2),
      '__TARGET__':number('target',1.5),'__POINT__':number('point_value',2),'__QTY__':integer('qty',1),
      '__COMM__':number('commission',1.5),'__MAXTRADES__':integer('max_trades',3),
      '__DAILY__':number('daily_stop_r',2),'__START__':hhmm('session_start','09:35'),
      '__END__':hhmm('session_end','15:55'),'__SLIPPAGE__':number('slippage',0.25)
    }
    if int(values['__FAST__'])>=int(values['__SLOW__']): raise ValueError('EMA rápida debe ser menor que EMA lenta.')
    template=r'''// Generated by NQ Vector 5M. Review and validate in Strategy Analyzer before use.
// CSV panel slippage assumption: __SLIPPAGE__ points per side.
// Set Strategy Analyzer slippage to the matching MNQ ticks (MNQ tick size is 0.25 points),
// and configure the actual commission there. Do not enable on a live account before simulation.
using System;
using System.ComponentModel.DataAnnotations;
using NinjaTrader.Cbi;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Indicators;

namespace NinjaTrader.NinjaScript.Strategies
{
    public class NQVector5M_Export : Strategy
    {
        private EMA fastEma;
        private EMA slowEma;
        private double sessionPv;
        private double sessionVolume;
        private DateTime currentDay = Core.Globals.MinDate;
        private int dailyTrades;
        private double dailyR;
        private double pendingStop;
        private double pendingAtr;
        private int pendingDirection;
        private double activeEntry;
        private double activeRisk;
        private int activeQuantity;
        private double exitCash;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "NQVector5M_Export";
                Description = "NQ Vector 5M strategy exported for validation. Use MNQ 5-minute bars.";
                Calculate = Calculate.OnBarClose;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = false;
                StopTargetHandling = StopTargetHandling.PerEntryExecution;
                StartBehavior = StartBehavior.WaitUntilFlat;
                FastPeriod = __FAST__;
                SlowPeriod = __SLOW__;
                AtrPeriod = __ATR__;
                BarsRequiredToTrade = Math.Max(SlowPeriod, AtrPeriod) + 4;
                TargetR = __TARGET__;
                PointValueUsd = __POINT__;
                TradeQuantity = __QTY__;
                RoundTripCommissionUsd = __COMM__;
                MaxTradesPerDay = __MAXTRADES__;
                DailyStopR = __DAILY__;
                SessionStart = __START__;
                SessionEnd = __END__;
            }
            else if (State == State.DataLoaded)
            {
                fastEma = EMA(FastPeriod);
                slowEma = EMA(SlowPeriod);
                AddChartIndicator(fastEma);
                AddChartIndicator(slowEma);
            }
        }

        protected override void OnBarUpdate()
        {
            if (BarsInProgress != 0 || CurrentBar < BarsRequiredToTrade)
                return;

            if (Time[0].Date != currentDay)
            {
                currentDay = Time[0].Date;
                dailyTrades = 0;
                dailyR = 0;
                sessionPv = 0;
                sessionVolume = 0;
            }

            int now = ToTime(Time[0]);
            int start = SessionStart * 100;
            int end = SessionEnd * 100;
            if (now >= start && now <= end)
            {
                double typical = (High[0] + Low[0] + Close[0]) / 3.0;
                double vol = Math.Max(0, (double)Volume[0]);
                sessionPv += typical * vol;
                sessionVolume += vol;
            }

            if (Position.MarketPosition != MarketPosition.Flat)
            {
                if (now >= end)
                {
                    if (Position.MarketPosition == MarketPosition.Long)
                        ExitLong("SessionEnd", "LongEntry");
                    else
                        ExitShort("SessionEnd", "ShortEntry");
                }
                return;
            }

            if (now < start || now >= end || dailyTrades >= MaxTradesPerDay || dailyR <= -DailyStopR)
                return;

            double atr = SimpleAtr();
            if (atr <= 0 || sessionVolume <= 0)
                return;
            double vwap = sessionPv / sessionVolume;
            bool touchLong = false;
            bool touchShort = false;
            for (int barsAgo = 1; barsAgo <= 3; barsAgo++)
            {
                if (Low[barsAgo] <= fastEma[barsAgo] + 0.12 * atr) touchLong = true;
                if (High[barsAgo] >= fastEma[barsAgo] - 0.12 * atr) touchShort = true;
            }

            bool goLong = fastEma[0] > slowEma[0] && Close[0] > vwap &&
                Close[0] > Open[0] && Close[0] > High[1] && touchLong;
            bool goShort = fastEma[0] < slowEma[0] && Close[0] < vwap &&
                Close[0] < Open[0] && Close[0] < Low[1] && touchShort;

            if (goLong)
            {
                double swingLow = Low[0];
                for (int barsAgo = 1; barsAgo <= 3; barsAgo++) swingLow = Math.Min(swingLow, Low[barsAgo]);
                pendingStop = swingLow - 0.10 * atr;
                pendingDirection = 1;
                pendingAtr = atr;
                double estimatedRisk = Close[0] - pendingStop;
                if (estimatedRisk > 0 && estimatedRisk <= 3 * atr)
                {
                    SetStopLoss("LongEntry", CalculationMode.Price, pendingStop, false);
                    SetProfitTarget("LongEntry", CalculationMode.Ticks, Math.Max(1, Math.Round(estimatedRisk * TargetR / TickSize)));
                    EnterLong(TradeQuantity, "LongEntry");
                }
            }
            else if (goShort)
            {
                double swingHigh = High[0];
                for (int barsAgo = 1; barsAgo <= 3; barsAgo++) swingHigh = Math.Max(swingHigh, High[barsAgo]);
                pendingStop = swingHigh + 0.10 * atr;
                pendingDirection = -1;
                pendingAtr = atr;
                double estimatedRisk = pendingStop - Close[0];
                if (estimatedRisk > 0 && estimatedRisk <= 3 * atr)
                {
                    SetStopLoss("ShortEntry", CalculationMode.Price, pendingStop, false);
                    SetProfitTarget("ShortEntry", CalculationMode.Ticks, Math.Max(1, Math.Round(estimatedRisk * TargetR / TickSize)));
                    EnterShort(TradeQuantity, "ShortEntry");
                }
            }
        }

        private double SimpleAtr()
        {
            double sum = 0;
            for (int barsAgo = 0; barsAgo < AtrPeriod; barsAgo++)
            {
                double priorClose = Close[barsAgo + 1];
                double tr = Math.Max(High[barsAgo] - Low[barsAgo],
                    Math.Max(Math.Abs(High[barsAgo] - priorClose), Math.Abs(Low[barsAgo] - priorClose)));
                sum += tr;
            }
            return sum / AtrPeriod;
        }

        protected override void OnExecutionUpdate(Execution execution, string executionId, double price,
            int quantity, MarketPosition marketPosition, string orderId, DateTime time)
        {
            if (execution == null || execution.Order == null || execution.Order.OrderState != OrderState.Filled)
                return;

            if (execution.Order.Name == "LongEntry" || execution.Order.Name == "ShortEntry")
            {
                activeEntry = price;
                activeQuantity = quantity;
                activeRisk = Math.Abs(activeEntry - pendingStop);
                exitCash = 0;
                dailyTrades++;
                if (activeRisk <= 0 || activeRisk > 3 * pendingAtr)
                {
                    if (pendingDirection > 0) ExitLong("InvalidRisk", "LongEntry");
                    else ExitShort("InvalidRisk", "ShortEntry");
                    return;
                }
                return;
            }

            if (execution.Order.FromEntrySignal == "LongEntry" || execution.Order.FromEntrySignal == "ShortEntry")
            {
                exitCash += (price - activeEntry) * pendingDirection * PointValueUsd * quantity;
                if (marketPosition == MarketPosition.Flat && activeRisk > 0 && activeQuantity > 0)
                {
                    double netTrade = exitCash - RoundTripCommissionUsd * activeQuantity;
                    dailyR += netTrade / (activeRisk * PointValueUsd * activeQuantity);
                    activeEntry = 0;
                    activeRisk = 0;
                    activeQuantity = 0;
                    exitCash = 0;
                }
            }
        }

        [NinjaScriptProperty]
        [Range(2, int.MaxValue)]
        [Display(Name = "EMA rápida", Order = 1, GroupName = "NQ Vector")]
        public int FastPeriod { get; set; }

        [NinjaScriptProperty]
        [Range(3, int.MaxValue)]
        [Display(Name = "EMA lenta", Order = 2, GroupName = "NQ Vector")]
        public int SlowPeriod { get; set; }

        [NinjaScriptProperty]
        [Range(2, int.MaxValue)]
        [Display(Name = "ATR", Order = 3, GroupName = "NQ Vector")]
        public int AtrPeriod { get; set; }

        [NinjaScriptProperty]
        [Range(0.1, double.MaxValue)]
        [Display(Name = "Objetivo (R)", Order = 4, GroupName = "NQ Vector")]
        public double TargetR { get; set; }

        [NinjaScriptProperty]
        [Range(0.01, double.MaxValue)]
        [Display(Name = "MNQ valor por punto ($)", Order = 5, GroupName = "NQ Vector")]
        public double PointValueUsd { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "Contratos", Order = 6, GroupName = "NQ Vector")]
        public int TradeQuantity { get; set; }

        [NinjaScriptProperty]
        [Range(0, double.MaxValue)]
        [Display(Name = "Comisión ida/vuelta ($)", Order = 7, GroupName = "NQ Vector")]
        public double RoundTripCommissionUsd { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "Máx. operaciones/día", Order = 8, GroupName = "NQ Vector")]
        public int MaxTradesPerDay { get; set; }

        [NinjaScriptProperty]
        [Range(0.1, double.MaxValue)]
        [Display(Name = "Límite pérdida diaria (R)", Order = 9, GroupName = "NQ Vector")]
        public double DailyStopR { get; set; }

        [NinjaScriptProperty]
        [Range(0, 2359)]
        [Display(Name = "Inicio sesión (HHmm)", Order = 10, GroupName = "NQ Vector")]
        public int SessionStart { get; set; }

        [NinjaScriptProperty]
        [Range(1, 2359)]
        [Display(Name = "Fin sesión (HHmm)", Order = 11, GroupName = "NQ Vector")]
        public int SessionEnd { get; set; }
    }
}
'''
    for key,value in values.items(): template=template.replace(key,value)
    return template

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def _send(self,status,body,typ='application/json; charset=utf-8'):
        data=body.encode() if isinstance(body,str) else body
        self.send_response(status);self.send_header('Content-Type',typ);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    def do_GET(self):
        if self.path=='/' or self.path.startswith('/?'):self._send(200,PAGE,'text/html; charset=utf-8')
        elif self.path=='/health':self._send(200,'{"ok":true}')
        else:self._send(404,'{"error":"No encontrado"}')
    def do_POST(self):
        path=urlparse(self.path).path
        try:
            length=int(self.headers.get('Content-Length','0'))
            if length>30_000_000:raise ValueError('Solicitud mayor de 30 MB.')
            req=json.loads(self.rfile.read(length))
            if path=='/backtest':
                rows=parse_csv(req['csv']);cfg=req['config'];out=compute(rows,cfg);self._send(200,json.dumps(out,allow_nan=False))
            elif path=='/export':
                source=generate_ninjascript(req['config']);self.send_response(200);self.send_header('Content-Type','text/plain; charset=utf-8');self.send_header('Content-Disposition','attachment; filename="NQVector5M_Export.cs"');self.send_header('Content-Length',str(len(source.encode())));self.end_headers();self.wfile.write(source.encode())
            else:self._send(404,'{"error":"No encontrado"}')
        except Exception as e:self._send(400,json.dumps({'error':str(e)}))

def main():
    port=8765
    try:HTTPServer(('127.0.0.1',port),Handler).serve_forever()
    except KeyboardInterrupt:print('\nPanel detenido.')
if __name__=='__main__':main()
