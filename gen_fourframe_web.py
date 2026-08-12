# -*- coding: utf-8 -*-
"""四框架每日选品 · 三级别生成器 (15min/60min/日线) · 含点击详情(实时K线+策略)
对每个品种在三个时间框架分别做四框架评分(缠论+MACD/RSI+江恩+量价),
每个时间框架各自分类: 好3/坏3/中性待突破3/性价比3。
点击品种卡 → 详情弹窗: 该级别K线图(蜡烛+MA5/10/20+成交量) + 进场/止盈/止损。
日线: 知几(缓存或直连); 15/60min: 新浪实时。
用法: python gen_fourframe_web.py
输出: $OUT_HTML (默认 D:/claude/四框架选品_daily/index.html)
"""
import sys, json, re, urllib.request, datetime, os, subprocess, time
sys.stdout.reconfigure(encoding='utf-8')

CACHE = os.environ.get('ZHIJI_CACHE', 'D:/claude/zhiji_kline_cache.json')
OUT = os.environ.get('OUT_HTML', 'D:/claude/四框架选品_daily/index.html')
STALE = {'ZC', 'WR'}
ZHIJI_API_KEY = 'wk_cbf2f9ff16f924c8c1f156bfd80fcc9b'
ZHIJI_BASE = 'https://zhiji-ai.xyz/guan/api/kline'

NAMES = {
    'CU':'沪铜','AL':'沪铝','ZN':'沪锌','PB':'沪铅','NI':'沪镍','SN':'沪锡','AU':'沪金','AG':'沪银',
    'RB':'螺纹','HC':'热卷','SS':'不锈钢','RU':'橡胶','BU':'沥青','FU':'燃油','SP':'纸浆','AO':'氧化铝',
    'BR':'丁二烯橡胶','I':'铁矿','J':'焦炭','JM':'焦煤','M':'豆粕','Y':'豆油','P':'棕榈','A':'豆一',
    'C':'玉米','CS':'淀粉','L':'塑料','PP':'聚丙烯','V':'PVC','EG':'乙二醇','EB':'苯乙烯','PG':'液化气',
    'JD':'鸡蛋','LH':'生猪','CF':'棉花','SR':'白糖','TA':'PTA','MA':'甲醇','FG':'玻璃','SA':'纯碱',
    'UR':'尿素','OI':'菜油','RM':'菜粕','AP':'苹果','SM':'锰硅','SF':'硅铁','PF':'短纤','ZC':'动力煤',
    'IF':'沪深300','IH':'上证50','IC':'中证500','IM':'中证1000','T':'10年国债','TF':'5年国债',
    'SC':'原油','LU':'低硫燃油','NR':'20号胶','BC':'国际铜','SI':'工业硅','LC':'碳酸锂','SH':'烧碱',
    'PR':'瓶片','PX':'对二甲苯','PL':'丙烯','PK':'花生','CJ':'红枣','BZ':'纯苯','B':'豆二','LG':'原木',
    'PS':'多晶硅','PT':'铂','PD':'钯','EC':'集运欧线','AD':'铸造铝合金','WR':'线材',
}

def fetch_zhiji_daily(sym):
    url = f'{ZHIJI_BASE}?symbol={sym}&freq=D&cont=1&limit=120'
    try:
        cmd = ['curl', '-s', '--max-time', '20', '-H', f'X-Guan-Key: {ZHIJI_API_KEY}', url]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', timeout=25)
        return json.loads(r.stdout).get('bars', [])
    except Exception:
        return []

def load_cache():
    if os.path.exists(CACHE):
        try:
            return json.load(open(CACHE, encoding='utf-8'))
        except Exception:
            pass
    print('缓存不存在, 直连知几拉日线...')
    cache = {}
    all_syms = ['CU','AL','ZN','PB','NI','SN','AU','AG','RB','HC','SS','RU','BU','FU','SP','AO','BR',
                'I','J','JM','M','Y','P','A','C','CS','L','PP','V','EG','EB','PG','JD','LH',
                'CF','SR','TA','MA','FG','SA','UR','OI','RM','AP','SM','SF','PF',
                'IF','IH','IC','IM','SC','LU','NR','BC','SI','LC','SH','PR','PX','PL','PK','CJ',
                'BZ','B','LG','PS','PT','PD','EC','AD']
    for s in all_syms:
        bars = fetch_zhiji_daily(s)
        if bars:
            cache[s] = {'bars': bars}
        time.sleep(0.15)
    return cache

def sina_freq(sym, typ, limit=320):
    s = sym + '0'
    url = f'https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20X=/InnerFuturesNewService.getFewMinLine?symbol={s}&type={typ}'
    try:
        req = urllib.request.Request(url, headers={'Referer': 'https://finance.sina.com.cn', 'User-Agent': 'Mozilla/5.0'})
        t = urllib.request.urlopen(req, timeout=5).read().decode('utf-8')
        m = re.search(r'\((\[.*\])\)', t, re.S)
        if not m: return []
        return [{'time': x['d'], 'open': float(x['o']), 'high': float(x['h']),
                 'low': float(x['l']), 'close': float(x['c']), 'volume': float(x.get('v', 0))} for x in json.loads(m.group(1))]
    except Exception:
        return []

def ema(vals, n):
    out = [vals[0]]; k = 2 / (n + 1)
    for v in vals[1:]: out.append(v * k + out[-1] * (1 - k))
    return out

def macd(closes):
    if len(closes) < 35: return None
    e12 = ema(closes, 12); e26 = ema(closes, 26)
    dif = [e12[i] - e26[i] for i in range(len(closes))]
    dea = ema(dif, 9)
    return {'cross': '金叉' if dif[-1] > dea[-1] else '死叉', 'hist': (dif[-1] - dea[-1]) * 2}

def rsi(closes, n=14):
    if len(closes) < n + 1: return 50
    g = []; l = []
    for j in range(1, n + 1):
        d = closes[-j] - closes[-j-1]
        g.append(max(d, 0)); l.append(max(-d, 0))
    ag = sum(g) / n; al = sum(l) / n
    return 100 - 100 / (1 + ag / al) if al > 0 else 100

def ma_state(closes):
    def ma(n): return sum(closes[-n:]) / n if len(closes) >= n else None
    m5, m10, m20 = ma(5), ma(10), ma(20)
    if not all([m5, m10, m20]): return '震荡'
    p = closes[-1]
    if p > m5 > m10 > m20: return '多头'
    if p < m5 < m10 < m20: return '空头'
    return '震荡'

def position_pct(bars):
    highs = [b['high'] for b in bars[-60:]]; lows = [b['low'] for b in bars[-60:]]
    p = bars[-1]['close']
    hi = max(highs); lo = min(lows)
    return (p - lo) / (hi - lo) * 100 if hi > lo else 50, hi, lo

def chan_pivots(bars):
    highs = [b['high'] for b in bars]; lows = [b['low'] for b in bars]
    fs = []
    for i in range(1, len(highs) - 1):
        if highs[i] > highs[i-1] and highs[i] > highs[i+1] and lows[i] > lows[i-1] and lows[i] > lows[i+1]:
            fs.append(('顶', highs[i]))
        elif lows[i] < lows[i-1] and lows[i] < lows[i+1] and highs[i] < highs[i-1] and highs[i] < highs[i+1]:
            fs.append(('底', lows[i]))
    merged = []
    for f in fs:
        if merged and merged[-1][0] == f[0]:
            if f[0] == '顶' and f[1] >= merged[-1][1]: merged[-1] = f
            elif f[0] == '底' and f[1] <= merged[-1][1]: merged[-1] = f
        else:
            merged.append(f)
    return merged

def chan_status(piv, p):
    if len(piv) < 4: return '结构不明'
    last = piv[-5:]
    segs = []
    for j in range(len(last) - 1):
        lo = min(last[j][1], last[j+1][1]); hi = max(last[j][1], last[j+1][1])
        segs.append((lo, hi))
    if len(segs) < 3: return '结构不明'
    zg = min(s[1] for s in segs[-3:]); zd = max(s[0] for s in segs[-3:])
    if zg >= zd:
        if p > zg: return f'中枢[{zd:,.0f}~{zg:,.0f}]上 → B3'
        if p < zd: return f'中枢[{zd:,.0f}~{zg:,.0f}]下 → S3'
        return f'中枢[{zd:,.0f}~{zg:,.0f}]内'
    return '单边' + ('下' if last[-1][0] == '顶' else '上')

def vol_state(bars):
    vols = [b.get('volume', 0) for b in bars]
    if len(vols) < 25: return '量不足'
    v5 = sum(vols[-5:]) / 5; v20 = sum(vols[-25:-5]) / 20
    vr = v5 / v20 if v20 else 1
    return f'量比{vr:.2f}·{"放量" if vr > 1.3 else ("缩量" if vr < 0.7 else "平量")}'

def score_bars(bars):
    if len(bars) < 60: return None
    closes = [b['close'] for b in bars]
    p = closes[-1]
    m = macd(closes); r = rsi(closes); ms = ma_state(closes)
    pos, hi, lo = position_pct(bars)
    piv = chan_pivots(bars); cs = chan_status(piv, p)
    vs = vol_state(bars)
    if m is None: return None
    s = 0
    s += 25 if m['cross'] == '金叉' else -25
    s += max(-15, min(15, m['hist'] / abs(p) * 200))
    if ms == '多头': s += 20
    elif ms == '空头': s -= 20
    if pos < 25: s += 15
    elif pos > 75: s -= 10
    if r < 30: s += 10
    elif r > 70: s -= 10
    if '放量' in vs and m['cross'] == '金叉': s += 10
    if '缩量' in vs: s -= 5
    return {'score': s, 'price': p, 'macd': m['cross'], 'ma': ms, 'gann': round(pos), 'rsi': round(r),
            'chan': cs, 'vol': vs, 'hi': hi, 'lo': lo}

def strat_full(it, cat):
    p = it['price']; hi = it['hi']; lo = it['lo']
    if cat == 'best':
        return {'dir': '多头', 'entry': f'回踩{max(lo, p*0.99):,.0f}', 'tp': f'{hi:,.0f}', 'sl': f'{lo*0.99:,.0f}'}
    if cat == 'worst':
        return {'dir': '空头', 'entry': f'反弹{p*1.01:,.0f}', 'tp': f'{lo:,.0f}', 'sl': f'{hi*1.01:,.0f}'}
    if cat == 'neutral':
        return {'dir': '双向', 'entry': f'突破{hi:,.0f}多 / 跌破{lo:,.0f}空', 'tp': f'{hi*1.02:,.0f} / {lo*0.98:,.0f}', 'sl': f'{lo:,.0f} / {hi:,.0f}'}
    return {'dir': '多头', 'entry': f'回踩{lo:,.0f}', 'tp': f'{hi:,.0f}', 'sl': f'{lo*0.99:,.0f}'}

# ===== 主流程 =====
cache = load_cache()
universe = [sym for sym, d in cache.items()
            if sym not in STALE and isinstance(d, dict) and d.get('bars') and len(d['bars']) >= 60]

results = {'15min': {}, '60min': {}, '日线': {}}
all_bars = {'15min': {}, '60min': {}, '日线': {}}

sina_fail_streak = 0
sina_offline = os.environ.get('SKIP_SINA') == '1'
if sina_offline:
    print('SKIP_SINA=1, 跳过15/60min, 仅日线', flush=True)
for sym in universe:
    name = NAMES.get(sym, sym)
    bars = cache[sym]['bars'][-120:]
    all_bars['日线'][sym] = bars
    d = score_bars(bars)
    if d: results['日线'][sym] = dict(d, sym=sym, name=name)
    if sina_offline:
        continue
    for tf, typ in [('60min', '60'), ('15min', '15')]:
        ib = sina_freq(sym, typ)
        if len(ib) < 60:
            sina_fail_streak += 1
            if sina_fail_streak >= 8:
                sina_offline = True
                print('⚠ sina不可达(连续失败), 15/60min级别跳过, 仅出日线', flush=True)
                break
            continue
        sina_fail_streak = 0
        all_bars[tf][sym] = ib
        d = score_bars(ib)
        if d: results[tf][sym] = dict(d, sym=sym, name=name)

def classify(tf_results):
    items = list(tf_results.values())
    items.sort(key=lambda x: -x['score'])
    best = items[:3]
    worst = [x for x in items if x['rsi'] > 30][-3:]
    worst = list(reversed(worst))
    neutral = [x for x in items if abs(x['score']) < 25 and 35 < x['gann'] < 70]
    neutral.sort(key=lambda x: abs(x['gann'] - 50))
    neutral = neutral[:3]
    value = [x for x in items if x['gann'] < 40 and x['macd'] == '金叉']
    value.sort(key=lambda x: x['gann'])
    used = set(x['sym'] for x in best + worst + neutral)
    value = [x for x in value if x['sym'] not in used][:3]
    return [('好 · 技术图形最强', 'best', best), ('坏 · 空头最扎实', 'worst', worst),
            ('中性待突破 · 区间蓄势', 'neutral', neutral), ('性价比 · 低位金叉', 'value', value)]

groups_by_tf = {tf: classify(results[tf]) for tf in ['15min', '60min', '日线']}

kline_data = {}
for tf in ['15min', '60min', '日线']:
    kline_data[tf] = {}
    for title, key, items in groups_by_tf[tf]:
        for it in items:
            bars = all_bars.get(tf, {}).get(it['sym'], [])
            kline_data[tf][it['sym']] = {
                'name': it['name'], 'cat': key, 'score': it['score'],
                'price': it['price'], 'gann': it['gann'], 'rsi': it['rsi'],
                'bars': [{'t': b['time'], 'o': b['open'], 'h': b['high'], 'l': b['low'], 'c': b['close'], 'v': b.get('volume', 0)} for b in bars[-90:]],
                'strat': strat_full(it, key),
            }

now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
last_daily = max((cache[s]['bars'][-1]['time'] for s in universe if cache[s]['bars']), default='?')
sina_note = '⚠ 15/60min不可达·仅日线' if sina_offline else '15/60min已更新'

def render_card(it, tf):
    return f'''<article class="pcard" onclick="openDetail('{tf}','{it['sym']}')">
<div class="phead"><span class="sym">{it['sym']}</span><span class="pname">{it['name']}</span><span class="pprice">{it['price']:,.0f}</span><span class="pscore">{it['score']:+.0f}</span></div>
<table class="ft"><tr><td class="k">缠论</td><td>{it['chan']}</td></tr><tr><td class="k">MACD/RSI</td><td>{it['macd']} RSI{it['rsi']} · {it['ma']}</td></tr><tr><td class="k">江恩</td><td>位{it['gann']}% · {it['lo']:,.0f}~{it['hi']:,.0f}</td></tr><tr><td class="k">量价</td><td>{it['vol']}</td></tr></table>
<div class="hint">点击查看 K线 + 策略 →</div></article>'''

def render_tab(tf, groups):
    h = [f'<div class="tf-tab" id="tf-{tf}">']
    for title, key, items in groups:
        h.append(f'<h3 class="cat-title">{"🟢" if key=="best" else "🔴" if key=="worst" else "⚪" if key=="neutral" else "🎯"} {title}</h3><div class="cards">')
        for it in items:
            h.append(render_card(it, tf))
        h.append('</div>')
    h.append('</div>')
    return '\n'.join(h)

KJSON = json.dumps(kline_data, ensure_ascii=False, separators=(',', ':'))

body = f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>四框架每日选品 · 三级别</title>
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600&family=JetBrains+Mono&family=Noto+Sans+SC:wght@400;700&display=swap" rel="stylesheet">
<style>
:root{{--bg:#F6F4F0;--panel:#FFFFFF;--gold:#D4AF37;--rose:#C05050;--blue:#3B5998;--emerald:#4A8060;--ink:#2C2420;--ink2:#6b615c;--ink3:#9c938e;--line:#e3ddd3}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);background-image:radial-gradient(circle at 12% 15%,rgba(212,175,55,.06),transparent 24%),radial-gradient(circle at 88% 72%,rgba(59,89,152,.05),transparent 28%);color:var(--ink);font:14px/1.6 'Noto Sans SC',system-ui,sans-serif}}
.shell{{max-width:1600px;margin:auto;padding:26px}}header{{text-align:center;padding:20px 0 6px}}
.eyebrow{{color:var(--gold);letter-spacing:.34em;font-size:11px}}h1{{font-family:Cinzel,serif;font-size:clamp(30px,4.5vw,52px);margin:8px 0 6px}}
.sub{{color:var(--ink2);font-size:12px}}.meta{{display:flex;gap:14px;justify-content:center;flex-wrap:wrap;margin:14px 0;color:var(--ink3);font:11px 'JetBrains Mono',monospace}}
.meta b{{color:var(--gold)}}
.tabs{{display:flex;gap:8px;justify-content:center;margin:16px 0}}.tabs button{{padding:9px 22px;border:1px solid var(--line);border-radius:999px;background:var(--panel);color:var(--ink2);font:600 13px 'Noto Sans SC';cursor:pointer}}
.tabs button.active{{background:var(--gold);color:#fff;border-color:var(--gold)}}
.tf-tab{{display:none}}.tf-tab.active{{display:block}}
.cat-title{{font-family:Cinzel,serif;font-weight:600;font-size:19px;border-bottom:2px solid var(--gold);padding-bottom:6px;margin:22px 0 12px}}
.cards{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}}
.pcard{{background:var(--panel);border:1px solid var(--line);border-top-left-radius:40px;border-top-right-radius:40px;padding:16px 16px 10px;position:relative;overflow:hidden;cursor:pointer;transition:transform .15s,box-shadow .15s}}
.pcard:hover{{transform:translateY(-2px);box-shadow:0 8px 22px rgba(44,36,32,.10)}}
.pcard::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,var(--gold),#f0dfa8)}}
.phead{{display:flex;align-items:baseline;gap:8px;margin-bottom:10px}}.sym{{font:700 20px 'JetBrains Mono';color:var(--ink)}}
.pname{{color:var(--ink2);font-size:12px}}.pprice{{margin-left:auto;font:600 16px 'JetBrains Mono';color:var(--blue)}}
.pscore{{font:700 12px 'JetBrains Mono';color:var(--gold)}}
.ft{{width:100%;border-collapse:collapse;font-size:12px}}.ft td{{padding:5px 2px;border-bottom:1px solid var(--line);vertical-align:top}}
.ft td.k{{white-space:nowrap;color:var(--gold);font:600 11px;width:56px}}
.hint{{margin-top:8px;text-align:right;color:var(--blue);font:10px 'JetBrains Mono';opacity:.75}}
footer{{text-align:center;color:var(--ink3);font:10px 'JetBrains Mono';margin:26px 0;padding-top:12px;border-top:1px solid var(--line)}}
#modal{{display:none;position:fixed;inset:0;background:rgba(20,15,10,.55);z-index:50;align-items:center;justify-content:center}}
#modal.show{{display:flex}}
.mbox{{background:var(--bg);border:1px solid var(--gold);border-radius:18px;max-width:820px;width:92%;max-height:90vh;overflow:auto;padding:22px;box-shadow:0 20px 60px rgba(0,0,0,.3)}}
.mhead{{display:flex;align-items:baseline;gap:10px;margin-bottom:6px}}.mhead .sym{{font-size:26px}}.mhead .close{{margin-left:auto;background:none;border:1px solid var(--line);border-radius:8px;padding:4px 12px;cursor:pointer;color:var(--ink2);font-size:13px}}
.mchart{{width:100%;height:340px;background:#fff;border:1px solid var(--line);border-radius:12px;margin:12px 0}}
.strat-bar{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:12px}}
.sbox{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px;text-align:center}}
.sbox b{{display:block;color:var(--gold);font:10px 'JetBrains Mono';letter-spacing:.1em;margin-bottom:4px}}
.sbox span{{font:700 15px 'JetBrains Mono'}}
.sbox.dir span{{color:var(--emerald)}}.sbox.tp span{{color:var(--blue)}}.sbox.sl span{{color:var(--rose)}}
.mdet{{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;color:var(--ink2);font:11px 'JetBrains Mono'}}
.mdet i{{font-style:normal;background:var(--panel);border:1px solid var(--line);padding:3px 8px;border-radius:6px}}
@media(max-width:1000px){{.cards{{grid-template-columns:1fr 1fr}}}}
@media(max-width:640px){{.cards{{grid-template-columns:1fr}}.strat-bar{{grid-template-columns:1fr}}}}
</style></head><body><div class="shell">
<header><div class="eyebrow">FOUR-FRAME DAILY SELECTION</div>
<h1>四框架每日选品 · 三级别</h1>
<div class="sub">缠论 · MACD/RSI · 江恩 · 量价 ｜ 15分钟 / 60分钟 / 日线 ｜ 点击品种看K线+策略</div>
<div class="meta"><span>日线数据 <b>{last_daily}</b></span><span>生成 <b>{now}</b></span><span>品种 <b>{len(universe)}</b></span><span>{sina_note}</span></div></header>
<nav class="tabs"><button class="active" onclick="showTf('15min',this)">15分钟</button><button onclick="showTf('60min',this)">60分钟</button><button onclick="showTf('日线',this)">日线</button></nav>
{render_tab('15min', groups_by_tf['15min'])}
{render_tab('60min', groups_by_tf['60min'])}
{render_tab('日线', groups_by_tf['日线'])}
<footer>数据源：日线=知几 · 15/60min=新浪实时 ｜ 每级别独立四框架评分 ｜ 每日 09:05/11:25/14:00/21:30 自动更新 ｜ 不构成投资建议</footer>
<div id="modal" onclick="if(event.target===this)closeDetail()"><div class="mbox">
<div class="mhead"><span class="sym" id="m-sym">—</span><span class="pname" id="m-name"></span><span class="pprice" id="m-price"></span><button class="close" onclick="closeDetail()">关闭 ✕</button></div>
<div class="mdet" id="m-det"></div>
<canvas class="mchart" id="m-chart" width="760" height="340"></canvas>
<div class="strat-bar"><div class="sbox dir"><b>方向 / 进场</b><span id="m-entry">—</span></div><div class="sbox tp"><b>止盈</b><span id="m-tp">—</span></div><div class="sbox sl"><b>止损</b><span id="m-sl">—</span></div></div>
</div></div>
<script>
const KDATA = {KJSON};
function showTf(tf,btn){{document.querySelectorAll('.tf-tab').forEach(x=>x.classList.remove('active'));document.getElementById('tf-'+tf).classList.add('active');document.querySelectorAll('.tabs button').forEach(x=>x.classList.remove('active'));btn.classList.add('active')}}
function openDetail(tf,sym){{const d=KDATA[tf][sym];if(!d)return;document.getElementById('m-sym').textContent=sym;document.getElementById('m-name').textContent=d.name;document.getElementById('m-price').textContent=d.price.toLocaleString();const dirColor=d.strat.dir.includes('多')?'#4A8060':(d.strat.dir.includes('空')?'#C05050':'#D4AF37');document.getElementById('m-entry').textContent=d.strat.dir+' ｜ '+d.strat.entry;document.getElementById('m-entry').style.color=dirColor;document.getElementById('m-tp').textContent=d.strat.tp;document.getElementById('m-sl').textContent=d.strat.sl;document.getElementById('m-det').innerHTML=['评分 '+d.score,'江恩 '+d.gann+'%','RSI '+d.rsi].map(x=>'<i>'+x+'</i>').join('');drawKline(d.bars);document.getElementById('modal').classList.add('show')}}
function closeDetail(){{document.getElementById('modal').classList.remove('show')}}
function drawKline(bars){{
  const cv=document.getElementById('m-chart'),ctx=cv.getContext('2d'),W=cv.width,H=cv.height;
  ctx.clearRect(0,0,W,H);if(!bars||!bars.length)return;
  const n=bars.length,px=6,plotH=H*0.72,vpH=H*0.20,gap=14;
  let hi=Math.max(...bars.map(b=>b.h)),lo=Math.min(...bars.map(b=>b.l));
  const pad=(hi-lo)*0.06,priceH=plotH-gap;
  const yP=p=>gap+(hi+pad-p)/(hi-lo+2*pad)*priceH;
  const xP=i=>px+i*(W-2*px)/n;
  ctx.strokeStyle='#e6e0d5';ctx.lineWidth=1;ctx.strokeRect(px,gap,W-2*px,plotH-gap);
  const cw=Math.max(1.5,(W-2*px)/n*0.6);
  for(let i=0;i<n;i++){{
    const b=bars[i],up=b.c>=b.o;
    ctx.strokeStyle=up?'#C05050':'#4A8060';ctx.fillStyle=up?'#C05050':'#4A8060';
    ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(xP(i),yP(b.h));ctx.lineTo(xP(i),yP(b.l));ctx.stroke();
    const yO=yP(b.o),yC=yP(b.c),top=Math.min(yO,yC),hgt=Math.max(1,Math.abs(yO-yC));
    ctx.fillRect(xP(i)-cw/2,top,cw,hgt);
  }}
  const closes=bars.map(b=>b.c);
  [[5,'#D4AF37'],[10,'#3B5998'],[20,'#4A8060']].forEach(([p,col])=>{{
    ctx.strokeStyle=col;ctx.lineWidth=1.4;ctx.beginPath();let started=false;
    for(let i=p-1;i<n;i++){{const v=closes.slice(i-p+1,i+1).reduce((a,c)=>a+c,0)/p;const x=xP(i),y=yP(v);if(!started){{ctx.moveTo(x,y);started=true}}else ctx.lineTo(x,y)}}
    ctx.stroke();
  }});
  const vmax=Math.max(...bars.map(b=>b.v))||1;
  for(let i=0;i<n;i++){{const b=bars[i],up=b.c>=b.o;const vh=b.v/vmax*vpH;ctx.fillStyle=up?'rgba(192,80,80,.35)':'rgba(74,128,96,.35)';ctx.fillRect(xP(i)-cw/2,H-vh,cw,vh)}}
  ctx.fillStyle='#9c938e';ctx.font='10px JetBrains Mono';ctx.fillText('H '+hi.toLocaleString(),px+6,16);ctx.fillText('L '+lo.toLocaleString(),px+6,H-4);
}}
document.addEventListener('keydown',e=>{{if(e.key==='Escape')closeDetail()}});
</script>
</div></body></html>'''

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, 'w', encoding='utf-8') as f:
    f.write(body)
print(f'已生成: {OUT} ({len(body)/1024:.0f}KB, 含{sum(len(v) for v in kline_data.values())}品种详情)')
for tf, label in [('15min', '15分钟'), ('60min', '60分钟'), ('日线', '日线')]:
    print(f'===== {label}级别 =====')
    for title, key, items in groups_by_tf[tf]:
        print('  ' + title + ': ' + ', '.join(it['sym'] + '(' + format(it['score'], '+.0f') + ')' for it in items))
