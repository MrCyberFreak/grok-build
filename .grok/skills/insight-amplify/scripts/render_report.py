#!/usr/bin/env python
"""render_report.py - the amplified insights report, with a per-BLOCK response UI overlaid.

DESIGN RULES (do not violate):
1. Keep the FULL report verbatim - the stats row, the Top Tools / Languages / Outcomes /
   Friction-Types charts, the Capability-Ecosystem counts, every section, and the full
   Boris/Karpathy persona reads (incl. where they AGREE and where they SPLIT). Never drop content.
2. Every run also has a LAYMANS version, generated PER BLOCK. LAYMANS != "plain": plain just
   defines jargon inline; laymans uses everyday analogies, zero jargon, and says what it means
   FOR YOU and what you'd do about it. Each text box toggles between its Laymans and Full wording
   on its own. Default is Laymans where a laymans twin exists.
3. GRAPHICS ARE CONSISTENT: the stats row, the charts, and the ecosystem-count grid are shown
   ONCE with no toggle (they are the same in both). Only text boxes toggle.
4. The only thing added on top is the response UI: a per-box Accept / Reject / Comment, the
   per-box Laymans/Full toggle, and Compose (paste-back plan prompt) + Export (decisions file).

Sources (verbatim):
  Full    - findings.json fields + deterministic usage charts/stats + relationship counts
  Laymans - findings.laymans (fallback findings.plain) : per-block laymans text, index-aligned
            to the findings arrays:
            { headline:str, key_pattern:str, work_areas:[str], usage_narrative:[str],
              ecosystem_summary:str, dead_capabilities:[str], overlaps:str, gaps:str,
              wins:[str], friction:[str], recommendations:[str], dropped:[str], horizon:[str],
              verify_loop:str }   (any subset; a block with no laymans twin = full only)
  Persona - findings.personas = {intro, groups:[{sub, blocks:[{style,tag,md}]}]}

Inputs: --findings --usage [--relationships] --out [--date]. ASCII-only output.
"""
import argparse
import html
import json
import os
import sys


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError, UnicodeDecodeError):
        return default if default is not None else {}


def esc(s):
    s = "" if s is None else str(s)
    return html.escape(s, quote=True).encode("ascii", "replace").decode("ascii")


def inline(s):
    s = esc(s)
    parts = s.split("**")
    out = []
    for idx, p in enumerate(parts):
        out.append(p)
        if idx < len(parts) - 1:
            out.append("<b>" if idx % 2 == 0 else "</b>")
    res = "".join(out)
    if res.count("<b>") != res.count("</b>"):
        res = res.replace("<b>", "").replace("</b>", "")
    return res


def md_render(text):
    blocks = []
    for b in str(text).split("\n\n"):
        b = b.strip("\n")
        if not b.strip():
            continue
        lines = b.split("\n")
        if all(ln.strip().startswith("- ") for ln in lines if ln.strip()):
            items = "".join("<li>%s</li>" % inline(ln.strip()[2:]) for ln in lines if ln.strip())
            blocks.append("<ul>%s</ul>" % items)
        else:
            blocks.append("<p>%s</p>" % "<br>".join(inline(ln) for ln in lines))
    return "".join(blocks)


def bars(data, color, limit=8):
    items = list(data.items())[:limit] if isinstance(data, dict) else []
    if not items:
        return '<div class="empty">no data</div>'
    mx = max((v for _, v in items), default=0) or 1
    rows = []
    for label, val in items:
        try:
            w = (float(val) / mx) * 100
        except (TypeError, ValueError):
            w = 0
        rows.append(
            '<div class="bar-row"><div class="bar-label">%s</div>'
            '<div class="bar-track"><div class="bar-fill" style="width:%.1f%%;background:%s"></div></div>'
            '<div class="bar-value">%s</div></div>' % (esc(label), w, color, esc(val)))
    return "\n".join(rows)


def stat(value, label):
    return ('<div class="stat"><div class="stat-value">%s</div>'
            '<div class="stat-label">%s</div></div>' % (esc(value), esc(label)))


def styled(style, inner, rank=None):
    rk = ('<span class="rec-rank">%s</span>' % esc(rank)) if rank not in (None, "") else ""
    return '<div class="%s">%s%s</div>' % (style, rk, inner)


def box_row(rid, section, style, full_inner, lay_text=None, rank=None, graphic=False):
    """One commentable row. Text boxes carry a per-box Laymans/Full toggle when a laymans twin
    exists. Graphics (graphic=True) are shown once with no toggle."""
    if graphic:
        content = full_inner  # already a complete graphic block
    elif lay_text:
        full_box = styled(style, full_inner, rank)
        lay_box = styled(style, '<div class="blk-body">%s</div>' % md_render(lay_text), rank)
        content = ('<div class="boxwrap">'
                   '<div class="seg light box-toggle"><button data-m="lay">Laymans</button><button data-m="full">Full</button></div>'
                   '<div class="box-lay">%s</div>'
                   '<div class="box-full" style="display:none">%s</div></div>' % (lay_box, full_box))
    else:
        content = styled(style, full_inner, rank)
    return ('<div class="row" data-id="%s" data-section="%s" data-view="block">'
            '<div class="row-content">%s</div><div class="row-comment"></div></div>'
            % (esc(rid), esc(section), content))


CSS = r"""
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; background: #f8fafc; color: #334155; line-height: 1.65; padding: 24px; }
.container { max-width: 1240px; margin: 0 auto; }
h1 { font-size: 30px; font-weight: 700; color: #0f172a; margin-bottom: 6px; }
h2 { font-size: 20px; font-weight: 600; color: #0f172a; margin-top: 38px; margin-bottom: 10px; }
.subtitle { color: #64748b; font-size: 14px; margin-bottom: 14px; }
.method { background: linear-gradient(135deg,#ecfeff,#cffafe); border:1px solid #06b6d4; border-radius:12px; padding:14px 18px; margin-bottom:14px; font-size:13px; color:#155e75; } .method b { color:#0e7490; }
.legend { background:#fffbeb; border:1px solid #fcd34d; border-radius:12px; padding:14px 18px; margin-bottom:18px; font-size:13px; color:#78350f; line-height:1.7; } .legend b { color:#92400e; }
.toolbar { position: sticky; top: 0; z-index: 30; display:flex; align-items:center; gap:12px; background:#0f172a; color:#e2e8f0; padding:10px 16px; border-radius:10px; margin-bottom:20px; font-size:13px; flex-wrap:wrap; }
.toolbar .grow { flex:1; } .toolbar .lbl { color:#94a3b8; }
.switch { display:flex; align-items:center; gap:8px; cursor:pointer; user-select:none; }
.switch input { width:36px; height:20px; appearance:none; background:#475569; border-radius:20px; position:relative; cursor:pointer; transition:.2s; }
.switch input:checked { background:#22c55e; }
.switch input::after { content:''; position:absolute; width:16px; height:16px; background:white; border-radius:50%; top:2px; left:2px; transition:.2s; }
.switch input:checked::after { left:18px; }
.count-pill { background:#1e293b; border:1px solid #334155; border-radius:20px; padding:4px 12px; font-size:12px; } .count-pill b { color:#38bdf8; }
.count-pill .a { color:#4ade80; } .count-pill .r { color:#f87171; } .count-pill .c { color:#fbbf24; }
.btn { border:none; border-radius:8px; padding:8px 14px; font-size:13px; font-weight:600; cursor:pointer; }
.btn-primary { background:#2563eb; color:white; } .btn-primary:disabled { background:#475569; cursor:not-allowed; }
.btn-ghost { background:transparent; color:#94a3b8; border:1px solid #334155; }
.seg { display:inline-flex; border:1px solid #334155; border-radius:8px; overflow:hidden; }
.seg button { background:transparent; color:#94a3b8; border:none; padding:6px 12px; font-size:12px; cursor:pointer; font-weight:600; }
.seg button.active { background:#2563eb; color:#fff; }
.seg.light { border:1px solid #cbd5e1; } .seg.light button { color:#94a3b8; padding:3px 10px; font-size:11px; } .seg.light button.active { background:#2563eb; color:#fff; }
.seg.verdict button { padding:5px 14px; font-size:12px; }
.seg.verdict button[data-v="accept"].active { background:#16a34a; color:#fff; }
.seg.verdict button[data-v="reject"].active { background:#dc2626; color:#fff; }
.row { display:grid; grid-template-columns: 1fr 330px; gap:18px; align-items:start; margin-bottom:12px; }
body.clean .row { grid-template-columns: 1fr; } body.clean .row-comment { display:none; }
.section-intro { font-size:14px; color:#64748b; margin:4px 0 10px; }
.boxwrap { position:relative; }
.box-toggle { position:absolute; top:8px; right:8px; z-index:2; background:rgba(255,255,255,.85); }
.nav-toc { display:flex; flex-wrap:wrap; gap:8px; margin:0 0 4px 0; padding:12px; background:white; border-radius:8px; border:1px solid #e2e8f0; }
.nav-toc a { font-size:12px; color:#64748b; text-decoration:none; padding:6px 12px; border-radius:6px; background:#f1f5f9; }
.nav-toc a:hover { background:#e2e8f0; color:#334155; }
.stats-row { display:flex; gap:22px; padding:18px; background:white; border:1px solid #e2e8f0; border-radius:8px; flex-wrap:wrap; }
.stat { text-align:center; } .stat-value { font-size:22px; font-weight:700; color:#0f172a; } .stat-label { font-size:11px; color:#64748b; text-transform:uppercase; }
.card { background:white; border:1px solid #e2e8f0; border-radius:8px; padding:14px 16px; font-size:13px; color:#475569; }
.card-title { font-weight:600; font-size:15px; color:#0f172a; margin-bottom:6px; }
.card-meta { font-size:12px; color:#64748b; background:#f1f5f9; padding:2px 8px; border-radius:4px; float:right; margin-left:8px; }
.card-desc { font-size:14px; color:#475569; }
.narrative { background:white; border:1px solid #e2e8f0; border-radius:8px; padding:16px; font-size:14px; color:#475569; } .narrative p { font-size:14px; color:#475569; }
.key-insight { background:#f0fdf4; border:1px solid #bbf7d0; border-radius:8px; padding:14px 16px; font-size:14px; color:#166534; } .key-insight b { color:#14532d; }
.charts-row { display:grid; grid-template-columns:1fr 1fr; gap:18px; }
.chart-card { background:white; border:1px solid #e2e8f0; border-radius:8px; padding:16px; }
.chart-title { font-size:12px; font-weight:600; color:#64748b; text-transform:uppercase; margin-bottom:12px; }
.bar-row { display:flex; align-items:center; margin-bottom:6px; }
.bar-label { width:130px; font-size:11px; color:#475569; flex-shrink:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.bar-track { flex:1; height:6px; background:#f1f5f9; border-radius:3px; margin:0 8px; }
.bar-fill { height:100%; border-radius:3px; } .bar-value { width:42px; font-size:11px; font-weight:500; color:#64748b; text-align:right; }
.empty { color:#94a3b8; font-size:13px; }
.eco-grid { display:grid; grid-template-columns:1fr 1fr 1fr; gap:14px; }
.eco-stat { background:white; border:1px solid #e2e8f0; border-radius:8px; padding:14px; text-align:center; }
.eco-num { font-size:24px; font-weight:700; color:#0f172a; } .eco-lbl { font-size:11px; color:#64748b; text-transform:uppercase; margin-top:2px; }
.eco { background:white; border:1px solid #e2e8f0; border-radius:8px; padding:14px 16px; font-size:13px; color:#475569; }
.win { background:#f0fdf4; border:1px solid #bbf7d0; border-radius:8px; padding:14px 16px; font-size:14px; color:#15803d; } .win b { color:#166534; } .win-title { font-weight:600; color:#166534; margin-bottom:4px; }
.friction { background:#fef2f2; border:1px solid #fca5a5; border-radius:8px; padding:14px 16px; font-size:13px; color:#7f1d1d; } .friction b { color:#991b1b; } .friction-title { font-weight:600; font-size:15px; color:#991b1b; }
.rec { background:#eff6ff; border:1px solid #bfdbfe; border-radius:8px; padding:14px 16px; font-size:13px; color:#334155; } .rec b { color:#1e3a8a; }
.rec-rank { display:inline-block; min-width:22px; height:22px; line-height:22px; text-align:center; background:#2563eb; color:white; border-radius:50%; font-size:12px; font-weight:700; margin-right:8px; }
.rec-title { font-weight:600; font-size:15px; color:#1e3a8a; }
.horizon { background:linear-gradient(135deg,#faf5ff,#f5f3ff); border:1px solid #c4b5fd; border-radius:8px; padding:14px 16px; font-size:13px; color:#334155; } .horizon b { color:#5b21b6; } .horizon-title { font-weight:600; color:#5b21b6; margin-bottom:4px; }
.dropped { background:#f8fafc; border:1px dashed #cbd5e1; border-radius:8px; padding:10px 14px; font-size:13px; color:#475569; } .dropped b { color:#0f172a; }
.blk-title { font-weight:600; color:#0f172a; }
.cat-pill { display:inline-block; font-size:11px; font-weight:600; text-transform:uppercase; background:#fee2e2; color:#b91c1c; padding:1px 8px; border-radius:10px; margin-left:8px; }
.line { font-size:13px; margin-top:8px; } .meta-line { font-size:12px; color:#64748b; margin-top:8px; }
.ev { margin:8px 0 0 18px; font-size:12px; color:#475569; } .ev li { margin-bottom:3px; }
.blk-body { margin-top:2px; } .blk-body p { margin:0 0 8px; } .blk-body p:last-child { margin:0; } .blk-body ul { margin:6px 0 0 18px; }
.home { display:inline-block; font-size:11px; font-weight:600; text-transform:uppercase; padding:2px 8px; border-radius:10px; margin-top:8px; }
.home-hook { background:#dcfce7; color:#15803d; } .home-rule { background:#fef9c3; color:#a16207; } .home-build { background:#e0f2fe; color:#0369a1; } .home-memory { background:#f3e8ff; color:#7e22ce; }
.persona-sub { font-size:13px; color:#475569; font-weight:700; margin:16px 0 8px; text-transform:uppercase; letter-spacing:.03em; }
.persona { background:white; border:1px solid #e2e8f0; border-radius:8px; padding:14px 16px; font-size:13px; color:#475569; }
.persona-tag { display:inline-block; font-size:11px; font-weight:700; text-transform:uppercase; padding:2px 9px; border-radius:10px; margin-bottom:6px; }
.persona.boris { border-left:4px solid #2563eb; } .persona.boris .persona-tag { background:#dbeafe; color:#1d4ed8; }
.persona.karpathy { border-left:4px solid #7c3aed; } .persona.karpathy .persona-tag { background:#ede9fe; color:#6d28d9; }
.persona.both { border-left:4px solid #0891b2; } .persona.both .persona-tag { background:#cffafe; color:#0e7490; }
.row.has-comment .row-content > * { box-shadow: -4px 0 0 0 #f59e0b; }
.row.v-accept .row-content > * { box-shadow: -4px 0 0 0 #22c55e; }
.row.v-reject .row-content > * { box-shadow: -4px 0 0 0 #ef4444; }
.cw { background:white; border:1px dashed #cbd5e1; border-radius:8px; padding:10px; }
.row.has-comment .cw, .row.v-accept .cw { border-style:solid; border-color:#cbd5e1; }
.row.v-accept .cw { border-color:#86efac; } .row.v-reject .cw { border-color:#fca5a5; } .row.has-comment .cw { border-color:#f59e0b; }
.cw-head { display:flex; align-items:center; gap:8px; margin-bottom:8px; }
.cw-clear { margin-left:auto; font-size:11px; color:#94a3b8; cursor:pointer; background:none; border:none; }
.cw-text { width:100%; min-height:46px; resize:vertical; font-family:inherit; font-size:13px; padding:8px; border:1px solid #e2e8f0; border-radius:6px; color:#334155; }
.cw-remember { display:none; align-items:center; gap:6px; font-size:11px; color:#b91c1c; margin-top:6px; }
.cw.show-remember .cw-remember { display:flex; }
.cw-hint { font-size:11px; color:#94a3b8; margin-top:6px; }
.overlay { display:none; position:fixed; inset:0; background:rgba(15,23,42,.6); z-index:50; align-items:center; justify-content:center; padding:24px; } .overlay.open { display:flex; }
.modal { background:white; border-radius:12px; max-width:820px; width:100%; max-height:88vh; display:flex; flex-direction:column; overflow:hidden; }
.modal-head { padding:16px 20px; border-bottom:1px solid #e2e8f0; } .modal-head h3 { font-size:16px; color:#0f172a; } .modal-head p { font-size:12px; color:#64748b; margin-top:2px; }
.modal-body { padding:16px 20px; overflow:auto; }
.modal-foot { padding:14px 20px; border-top:1px solid #e2e8f0; display:flex; gap:10px; justify-content:flex-end; align-items:center; } .modal-foot .grow { flex:1; font-size:12px; color:#64748b; }
#composeText { width:100%; min-height:360px; font-family:ui-monospace,Consolas,monospace; font-size:12px; line-height:1.5; padding:12px; border:1px solid #e2e8f0; border-radius:8px; color:#1e293b; background:#f8fafc; }
.toast { position:fixed; bottom:24px; left:50%; transform:translateX(-50%); background:#0f172a; color:white; padding:10px 18px; border-radius:8px; font-size:13px; opacity:0; transition:.3s; z-index:60; } .toast.show { opacity:1; }
.footer-note { margin-top:40px; padding:18px; background:#0f172a; border-radius:12px; color:#cbd5e1; font-size:13px; line-height:1.6; } .footer-note b { color:#f8fafc; }
@media (max-width:900px){ .row{grid-template-columns:1fr;} .charts-row,.eco-grid{grid-template-columns:1fr;} }
"""

JS = r"""
var STATS = JSON.parse(document.getElementById('stats').textContent);
var REPORT_DATE = STATS.date || '';
var STORE_KEY = 'amplify-feedback-' + REPORT_DATE;
var BOX_KEY = 'amplify-boxmode-' + REPORT_DATE;
// store[id] = { verdict:'accept'|'reject'|'', text:'', remember:false }
var store = {}; try { store = JSON.parse(localStorage.getItem(STORE_KEY) || '{}'); } catch(e){ store = {}; }
var boxModes = {}; try { boxModes = JSON.parse(localStorage.getItem(BOX_KEY) || '{}'); } catch(e){ boxModes = {}; }

function widgetHTML(id){
  var s = store[id] || {verdict:'', text:'', remember:false};
  var txt = (s.text||'').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  var showRem = (s.verdict==='reject' || (s.text||'').trim());
  return '<div class="cw'+(showRem?' show-remember':'')+'" data-id="'+id+'">'+
    '<div class="cw-head"><div class="seg verdict">'+
      '<button data-v="accept"'+(s.verdict==='accept'?' class="active"':'')+'>Accept</button>'+
      '<button data-v="reject"'+(s.verdict==='reject'?' class="active"':'')+'>Reject</button>'+
    '</div><button class="cw-clear" title="clear">clear</button></div>'+
    '<textarea class="cw-text" placeholder="Comment on this block (optional)...">'+txt+'</textarea>'+
    '<label class="cw-remember"><input type="checkbox" '+(s.remember?'checked':'')+'> remember this for future reports</label>'+
    '<div class="cw-hint">Accept = do / build this. Reject = skip it. Add a comment to refine either - or just comment.</div></div>';
}
function rowClasses(rw, id){
  var s = store[id] || {};
  rw.classList.toggle('v-accept', s.verdict==='accept');
  rw.classList.toggle('v-reject', s.verdict==='reject');
  rw.classList.toggle('has-comment', !s.verdict && !!(s.text||'').trim());
}
function mountWidgets(){
  document.querySelectorAll('.row').forEach(function(rw){
    var id=rw.dataset.id; rw.querySelector('.row-comment').innerHTML=widgetHTML(id);
    rowClasses(rw, id);
  });
  bind(); refreshCount();
}
function bind(){
  document.querySelectorAll('.cw').forEach(function(cw){
    var id=cw.dataset.id, text=cw.querySelector('.cw-text'),
        remember=cw.querySelector('.cw-remember input'), clear=cw.querySelector('.cw-clear');
    function cur(){ return store[id] || {verdict:'', text:'', remember:false}; }
    function save(s){
      store[id]=s; localStorage.setItem(STORE_KEY, JSON.stringify(store));
      cw.classList.toggle('show-remember', s.verdict==='reject' || (s.text||'').trim());
      rowClasses(cw.closest('.row'), id); refreshCount();
    }
    cw.querySelectorAll('.seg.verdict button').forEach(function(b){
      b.addEventListener('click', function(){
        var s=cur(); s.verdict = (s.verdict===b.dataset.v) ? '' : b.dataset.v;
        cw.querySelectorAll('.seg.verdict button').forEach(function(x){ x.classList.toggle('active', x.dataset.v===s.verdict); });
        save(s);
      });
    });
    text.addEventListener('input', function(){ var s=cur(); s.text=text.value; save(s); });
    remember.addEventListener('change', function(){ var s=cur(); s.remember=remember.checked; save(s); });
    clear.addEventListener('click', function(){
      delete store[id]; localStorage.setItem(STORE_KEY, JSON.stringify(store));
      text.value=''; remember.checked=false;
      cw.querySelectorAll('.seg.verdict button').forEach(function(x){ x.classList.remove('active'); });
      cw.classList.remove('show-remember'); rowClasses(cw.closest('.row'), id); refreshCount();
    });
  });
}
function tally(){
  var a=0,r=0,c=0;
  Object.keys(store).forEach(function(k){ var v=store[k]||{};
    if(v.verdict==='accept') a++; else if(v.verdict==='reject') r++;
    if(!v.verdict && (v.text||'').trim()) c++; });
  return {a:a,r:r,c:c,total:a+r+c};
}
function refreshCount(){
  var t=tally();
  document.getElementById('cA').textContent=t.a;
  document.getElementById('cR').textContent=t.r;
  document.getElementById('cC').textContent=t.c;
  document.getElementById('composeBtn').disabled = t.total===0;
  document.getElementById('exportBtn').disabled = t.total===0;
}
function visibleText(rw){
  var bw = rw.querySelector('.boxwrap');
  var el;
  if(bw){ var pl=bw.querySelector('.box-lay'), fu=bw.querySelector('.box-full');
    el = (pl && pl.style.display!=='none') ? pl : fu; }
  else { el = rw.querySelector('.row-content'); }
  return (el && el.textContent || '').replace(/\s+/g,' ').trim();
}
function curMode(rw){
  var bw = rw.querySelector('.boxwrap'); if(!bw) return 'n/a';
  var pl = bw.querySelector('.box-lay');
  return (pl && pl.style.display!=='none') ? 'laymans' : 'full';
}
function collect(){
  var rows=[];
  document.querySelectorAll('.row').forEach(function(rw){
    var id=rw.dataset.id, s=store[id];
    if(!s || (!s.verdict && !(s.text||'').trim())) return;
    var snippet=visibleText(rw); if(snippet.length>260) snippet=snippet.slice(0,260)+'...';
    rows.push({id:id, section:rw.dataset.section||id, mode:curMode(rw),
               verdict:s.verdict||'', comment:(s.text||'').trim(), remember:!!s.remember, snippet:snippet});
  });
  return rows;
}
function compose(){
  var rows=collect();
  var acc=rows.filter(function(x){return x.verdict==='accept';});
  var rej=rows.filter(function(x){return x.verdict==='reject';});
  var com=rows.filter(function(x){return !x.verdict && x.comment;});
  var out='# Feedback on Amplified Insights ('+REPORT_DATE+')\n';
  out+='Report: '+(STATS.reportPath||('amplified-insights-'+REPORT_DATE+'.html'))+'\n';
  if(!rows.length) return out+'\n(no responses yet)';
  function blk(title, list){
    if(!list.length) return '';
    var s='\n## '+title+'\n';
    list.forEach(function(item){
      s+='\n- '+item.section+(item.mode!=='n/a'?' ['+item.mode+' view]':'')+':\n  > '+item.snippet;
      if(item.comment) s+='\n  My note: '+item.comment;
      if(item.remember) s+='\n  (remember this for future reports)';
      s+='\n';
    });
    return s;
  }
  out+=blk('ACCEPTED - do / build these (plan first)', acc);
  out+=blk('REJECTED - skip these', rej);
  out+=blk('COMMENTS - no accept/reject, refine the analysis', com);
  out+='\n---\nINSTRUCTIONS - plan first, approval required:\n';
  out+='Do NOT make any changes, edits, or runs yet. First write a single PLAN that addresses everything above and present it to me for approval.\n';
  out+='- For ACCEPTED items: spell out exactly what you would build/edit, where, and the tradeoffs - as a proposal. Route config changes through /update-config, rules into the relevant CLAUDE.md, memory into the vault.\n';
  out+='- For REJECTED items: drop them; do not propose them again. If one was a correction of a wrong claim, fold the correction into the analysis as ground truth.\n';
  out+='- For COMMENTS: treat as ground truth / refinement; answer questions inside the plan.\n';
  out+='- Persist anything marked "remember" so future reports do not repeat it.\n';
  out+='Wait for my explicit approval of the plan before enacting anything.\n';
  return out;
}
function decisionsJSON(){
  var obj={report:(STATS.reportPath||''), date:REPORT_DATE, generated_by:'amplify response UI',
           summary:tally(), decisions:{}};
  collect().forEach(function(x){ obj.decisions[x.id]={section:x.section, view:x.mode,
     verdict:x.verdict||'comment', comment:x.comment, remember:x.remember}; });
  return JSON.stringify(obj, null, 2);
}

// per-BOX Laymans/Full toggle (default Laymans)
function setBoxMode(bw, mode){
  var pl=bw.querySelector('.box-lay'), fu=bw.querySelector('.box-full');
  if(pl) pl.style.display = (mode==='lay') ? '' : 'none';
  if(fu) fu.style.display = (mode==='full') ? '' : 'none';
  bw.querySelectorAll('.box-toggle button').forEach(function(b){ b.classList.toggle('active', b.dataset.m===mode); });
  var rw = bw.closest('.row'); if(rw){ boxModes[rw.dataset.id]=mode; localStorage.setItem(BOX_KEY, JSON.stringify(boxModes)); }
}
function initBoxes(){
  document.querySelectorAll('.boxwrap').forEach(function(bw){
    var rw=bw.closest('.row'); var id=rw?rw.dataset.id:'';
    setBoxMode(bw, boxModes[id] || 'lay');
    bw.querySelectorAll('.box-toggle button').forEach(function(b){
      b.addEventListener('click', function(){ setBoxMode(bw, b.dataset.m); });
    });
  });
}
function setAllBoxes(mode){
  document.querySelectorAll('.boxwrap').forEach(function(bw){ setBoxMode(bw, mode); });
}
var overlay = document.getElementById('overlay');
function openCompose(){
  var ta=document.getElementById('composeText'); ta.value=compose();
  var t=tally();
  document.getElementById('composeMeta').textContent = t.a+' accepted, '+t.r+' rejected, '+t.c+' comment'+(t.c===1?'':'s');
  overlay.classList.add('open'); setTimeout(function(){ ta.focus(); ta.select(); }, 30);
}
document.getElementById('composeBtn').addEventListener('click', openCompose);
document.getElementById('exportBtn').addEventListener('click', function(){
  var blob=new Blob([decisionsJSON()], {type:'application/json'});
  var a=document.createElement('a'); a.href=URL.createObjectURL(blob);
  a.download='amplified-insights-'+REPORT_DATE+'-decisions.json';
  document.body.appendChild(a); a.click(); a.remove();
  toast('Exported amplified-insights-'+REPORT_DATE+'-decisions.json');
});
document.getElementById('closeModal').addEventListener('click', function(){ overlay.classList.remove('open'); });
overlay.addEventListener('click', function(e){ if(e.target===overlay) overlay.classList.remove('open'); });
document.getElementById('copyBtn').addEventListener('click', async function(){
  var t=document.getElementById('composeText'); t.focus(); t.select(); try{ t.setSelectionRange(0,t.value.length); }catch(e){}
  var ok=false; try { if(navigator.clipboard && navigator.clipboard.writeText){ await navigator.clipboard.writeText(t.value); ok=true; } } catch(e){}
  if(!ok){ try { ok=document.execCommand('copy'); } catch(e){} }
  toast(ok ? 'Copied - paste it into Claude' : 'Could not auto-copy - text is selected, press Ctrl+C');
});
document.getElementById('dlPromptBtn').addEventListener('click', function(){
  var blob=new Blob([document.getElementById('composeText').value], {type:'text/markdown'});
  var a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download='amplified-insights-'+REPORT_DATE+'-plan-request.md';
  document.body.appendChild(a); a.click(); a.remove(); toast('Downloaded the plan request .md');
});
document.getElementById('reviewToggle').addEventListener('change', function(e){ document.body.classList.toggle('clean', !e.target.checked); });
document.getElementById('allLay').addEventListener('click', function(){ setAllBoxes('lay'); });
document.getElementById('allFull').addEventListener('click', function(){ setAllBoxes('full'); });
document.getElementById('clearAll').addEventListener('click', function(){
  if(!confirm('Clear all accept/reject/comments on this report?')) return;
  store={}; localStorage.removeItem(STORE_KEY); mountWidgets();
});
var toastT;
function toast(msg){ var el=document.getElementById('toast'); el.textContent=msg; el.classList.add('show'); clearTimeout(toastT); toastT=setTimeout(function(){ el.classList.remove('show'); },2200); }

mountWidgets();
initBoxes();
"""


def get_lay(lay, key, idx=None):
    v = lay.get(key)
    if v is None:
        return None
    if idx is None:
        return v if isinstance(v, str) and v.strip() else None
    if isinstance(v, list) and idx < len(v) and isinstance(v[idx], str) and v[idx].strip():
        return v[idx]
    return None


def build_body(f, usage, rel):
    lay = f.get("laymans") or f.get("plain") or {}
    totals = usage.get("totals", {})
    rcounts = rel.get("counts", {}) if rel else {}
    eco = f.get("ecosystem", {}) or {}
    out = []
    A = out.append

    # nav
    A('<nav class="nav-toc">'
      '<a href="#work">What You Work On</a><a href="#usage">How You Use CC</a>'
      '<a href="#eco">Capability Ecosystem</a><a href="#wins">What\'s Working</a>'
      '<a href="#friction">Where Things Go Wrong</a><a href="#new">Actually New</a>'
      '<a href="#dropped">Dropped</a><a href="#horizon">On the Horizon</a></nav>')

    # bottom line (toggle) + stats (graphic, no toggle)
    if f.get("headline"):
        A(box_row("headline", "Bottom line", "key-insight",
                  "<b>Bottom line:</b> %s" % inline(f["headline"]), lay_text=get_lay(lay, "headline")))
    statrow = ('<div class="stats-row">%s%s%s%s%s%s</div>' % (
        stat(totals.get("sessions", 0), "Sessions"),
        stat("+%s/-%s" % (totals.get("lines_added", 0), totals.get("lines_removed", 0)), "Lines"),
        stat(totals.get("files_modified", 0), "Files"),
        stat("%s/%s" % (totals.get("git_commits", 0), totals.get("git_pushes", 0)), "Commits/Pushes"),
        stat(len(usage.get("projects", {})), "Projects"),
        stat("%.1fM" % (totals.get("output_tokens", 0) / 1e6), "Output Tokens")))
    A(box_row("stats", "Headline stats (graphic)", "", statrow, graphic=True))

    A('<h2 id="work">What You Work On</h2>')
    for i, a in enumerate(f.get("work_areas") or []):
        full_inner = ('<span class="card-meta">%s</span><div class="card-title">%s</div>'
                      '<div class="card-desc">%s</div>'
                      % (esc(a.get("sessions", "")), esc(a.get("name", "")), inline(a.get("detail", ""))))
        A(box_row("work-%d" % i, "Work area: %s" % a.get("name", ""), "card", full_inner,
                  lay_text=get_lay(lay, "work_areas", i)))

    A('<h2 id="usage">How You Use Claude Code</h2>')
    for i, para in enumerate(f.get("usage_narrative") or []):
        A(box_row("usage-%d" % i, "How you use CC (%d)" % (i + 1), "narrative",
                  "<p>%s</p>" % inline(para), lay_text=get_lay(lay, "usage_narrative", i)))
    if f.get("key_pattern"):
        A(box_row("keypattern", "Key pattern", "key-insight",
                  "<b>Key pattern:</b> %s" % inline(f["key_pattern"]), lay_text=get_lay(lay, "key_pattern")))
    charts = ('<div class="charts-row">'
              '<div class="chart-card"><div class="chart-title">Top Tools</div>%s</div>'
              '<div class="chart-card"><div class="chart-title">Languages</div>%s</div></div>'
              '<div class="charts-row" style="margin-top:18px">'
              '<div class="chart-card"><div class="chart-title">Outcomes</div>%s</div>'
              '<div class="chart-card"><div class="chart-title">Friction Types</div>%s</div></div>'
              % (bars(usage.get("tools", {}), "#0891b2"), bars(usage.get("languages", {}), "#10b981"),
                 bars(usage.get("outcomes", {}), "#8b5cf6"), bars(usage.get("friction_types", {}), "#dc2626")))
    A(box_row("charts", "Usage charts (graphic)", "", charts, graphic=True))

    A('<h2 id="eco">Capability Ecosystem</h2>')
    ecogrid = ('<div class="eco-grid">'
               '<div class="eco-stat"><div class="eco-num">%s</div><div class="eco-lbl">Agents (%s ever invoked)</div></div>'
               '<div class="eco-stat"><div class="eco-num">%s</div><div class="eco-lbl">User skills (%s invoked)</div></div>'
               '<div class="eco-stat"><div class="eco-num">%s</div><div class="eco-lbl">Libraries (%s with an agent)</div></div></div>'
               % (esc(rcounts.get("agents", 0)), esc(rcounts.get("agents_ever_invoked", 0)),
                  esc(rcounts.get("user_skills", 0)), esc(rcounts.get("skills_ever_invoked", 0)),
                  esc(rcounts.get("libraries", 0)), esc(rcounts.get("agents_with_library", 0))))
    A(box_row("eco-grid", "Ecosystem counts (graphic)", "", ecogrid, graphic=True))
    if eco.get("summary"):
        A(box_row("eco-summary", "Ecosystem summary", "eco", inline(eco["summary"]),
                  lay_text=get_lay(lay, "ecosystem_summary")))
    for i, d in enumerate(eco.get("dead_capabilities") or []):
        full_inner = ('<span class="blk-title">%s (%s)</span><span class="cat-pill">%s</span>'
                      '<div class="blk-body"><p>%s</p></div>'
                      % (esc(d.get("name", "")), esc(d.get("kind", "")), esc(d.get("verdict", "")), inline(d.get("detail", ""))))
        A(box_row("dead-%d" % i, "Dead/latent: %s" % d.get("name", ""), "eco", full_inner,
                  lay_text=get_lay(lay, "dead_capabilities", i)))
    if eco.get("overlaps"):
        items = "".join("<li><b>%s</b> &harr; <b>%s</b> - %s</li>" % (inline(o.get("a", "")), inline(o.get("b", "")), inline(o.get("detail", o.get("verdict", "")))) for o in eco["overlaps"])
        A(box_row("overlaps", "Overlap / redundancy", "eco",
                  '<span class="blk-title">Overlap / redundancy</span><ul class="ev">%s</ul>' % items,
                  lay_text=get_lay(lay, "overlaps")))
    if eco.get("gaps"):
        items = "".join("<li><b>%s</b> - %s <i>(home: %s)</i></li>" % (inline(g.get("area", "")), inline(g.get("detail", "")), inline(g.get("proposed_home", "?"))) for g in eco["gaps"])
        A(box_row("gaps", "Gaps", "eco",
                  '<span class="blk-title">Gaps (work with no capability behind it)</span><ul class="ev">%s</ul>' % items,
                  lay_text=get_lay(lay, "gaps")))
    if eco.get("libraryless"):
        items = "".join("<li><b>%s</b> - %s</li>" % (inline(x.get("name", "")), inline(x.get("detail", ""))) for x in eco["libraryless"])
        A(box_row("libraryless", "Experts missing a corpus", "eco",
                  '<span class="blk-title">Experts missing a grounding corpus</span><ul class="ev">%s</ul>' % items))
    if eco.get("doc_drift"):
        items = "".join("<li><b>%s</b> - %s</li>" % (inline(x.get("item", "")), inline(x.get("detail", ""))) for x in eco["doc_drift"])
        A(box_row("docdrift", "Documentation drift", "eco",
                  '<span class="blk-title">Documentation drift</span><ul class="ev">%s</ul>' % items))

    A('<h2 id="wins">What\'s Working</h2>')
    for i, w in enumerate(f.get("wins") or []):
        full_inner = '<div class="win-title">%s</div>%s' % (esc(w.get("title", "")), md_render(w.get("detail", "")))
        A(box_row("win-%d" % i, "Win: %s" % w.get("title", ""), "win", full_inner,
                  lay_text=get_lay(lay, "wins", i)))

    A('<h2 id="friction">Where Things Go Wrong</h2>')
    for i, fr in enumerate(f.get("friction") or []):
        ev = "".join("<li>%s</li>" % inline(e) for e in (fr.get("evidence") or [])[:4])
        full_inner = ('<div class="friction-title">%s<span class="cat-pill">%s</span></div>'
                      '<div class="line"><b>Cost:</b> %s</div><div class="blk-body">%s</div>%s%s'
                      % (esc(fr.get("title", "")), esc(fr.get("category", "")), inline(fr.get("cost", "")),
                         md_render(fr.get("detail", "")), ('<ul class="ev">%s</ul>' % ev) if ev else "",
                         ('<div class="meta-line">ledger: %s</div>' % esc(fr["ledger_id"])) if fr.get("ledger_id") else ""))
        A(box_row("fr-%d" % i, "Friction: %s" % fr.get("title", ""), "friction", full_inner,
                  lay_text=get_lay(lay, "friction", i)))
    if f.get("verify_loop"):
        A(box_row("verify", "Verify loop", "key-insight", "<b>Verify loop:</b> %s" % inline(f["verify_loop"]),
                  lay_text=get_lay(lay, "verify_loop")))

    A('<h2 id="new">What Is Actually NEW For You</h2>')
    for i, rec in enumerate(f.get("recommendations") or []):
        hc = {"hook": "home-hook", "rule": "home-rule", "memory": "home-memory", "build": "home-build"}.get(rec.get("guard_home", ""), "home-rule")
        full_inner = ('<span class="rec-title">%s</span><div class="blk-body">%s</div>'
                      '<div><span class="home %s">home: %s</span></div>'
                      '<div class="line"><b>Guard:</b> %s</div>'
                      % (esc(rec.get("title", "")), md_render(rec.get("detail", "")),
                         hc, esc(rec.get("guard_home", "")), inline(rec.get("guard_desc", ""))))
        A(box_row("rec-%d" % i, "Rec #%s: %s" % (rec.get("rank", ""), rec.get("title", "")), "rec", full_inner,
                  lay_text=get_lay(lay, "recommendations", i), rank=rec.get("rank", "")))

    A('<h2 id="dropped">Dropped as Already-Satisfied <span style="font-size:13px;color:#64748b;font-weight:400">(proof the subtraction worked)</span></h2>')
    for i, d in enumerate(f.get("dropped_as_satisfied") or []):
        full_inner = "<b>%s</b> - %s" % (inline(d.get("suggestion", "")), inline(d.get("why_covered", "")))
        A(box_row("drop-%d" % i, "Dropped: %s" % d.get("suggestion", ""), "dropped", full_inner,
                  lay_text=get_lay(lay, "dropped", i)))

    if f.get("horizon"):
        A('<h2 id="horizon">On the Horizon</h2>')
        for i, h in enumerate(f["horizon"]):
            full_inner = ('<div class="horizon-title">%s</div>%s<div class="line"><b>Getting started:</b> %s</div>'
                          % (esc(h.get("title", "")), md_render(h.get("possible", "")), inline(h.get("getting_started", ""))))
            A(box_row("hz-%d" % i, "Horizon: %s" % h.get("title", ""), "horizon", full_inner,
                      lay_text=get_lay(lay, "horizon", i)))

    # persona reads (full content, commentable; no laymans/full toggle - one version)
    personas = f.get("personas") or {}
    if personas.get("groups"):
        A('<h2 style="margin-top:40px">Persona Reads</h2>')
        if personas.get("intro"):
            A('<p class="section-intro">%s</p>' % esc(personas["intro"]))
        cls_map = {"persona-both": "persona both", "persona-boris": "persona boris", "persona-karpathy": "persona karpathy"}
        for gi, g in enumerate(personas["groups"]):
            if g.get("sub"):
                A('<div class="persona-sub">%s</div>' % esc(g["sub"]))
            for bi, b in enumerate(g.get("blocks") or []):
                cls = cls_map.get(b.get("style", "persona-both"), "persona both")
                inner = (('<span class="persona-tag">%s</span>' % esc(b["tag"])) if b.get("tag") else "")
                inner += '<div class="blk-body">%s</div>' % md_render(b.get("md", ""))
                A(box_row("PER-%d-%d" % (gi, bi), "Persona > %s - %s" % (g.get("sub", ""), b.get("tag", "")), cls, inner))
    return "".join(out)


def build_html(f, usage, rel, date, out_path):
    totals = usage.get("totals", {})
    dr = usage.get("date_range", {})
    stats = {"date": date, "reportPath": os.path.abspath(out_path), "sessions": totals.get("sessions", 0)}
    body = build_body(f, usage, rel)
    parts = []
    A = parts.append
    A("<!DOCTYPE html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">")
    A("<title>Amplified Insights - annotated %s</title>" % esc(date))
    A("<link href='https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap' rel='stylesheet'>")
    A("<style>%s</style></head><body><div class=\"container\">" % CSS)
    A('<div class="toolbar">'
      '<label class="switch"><input type="checkbox" id="reviewToggle" checked> <span>Review mode</span></label>'
      '<span class="lbl">All:</span><div class="seg light"><button id="allLay">Laymans</button><button id="allFull">Full</button></div>'
      '<span class="grow"></span>'
      '<span class="count-pill"><b class="a" id="cA">0</b> accept &middot; <b class="r" id="cR">0</b> reject &middot; <b class="c" id="cC">0</b> comment</span>'
      '<button class="btn btn-ghost" id="clearAll">Clear all</button>'
      '<button class="btn btn-ghost" id="exportBtn" disabled>Export decisions</button>'
      '<button class="btn btn-primary" id="composeBtn" disabled>Compose plan request</button></div>')
    A('<h1>Amplified Insights</h1>')
    A('<p class="subtitle">%s sessions | %s messages | %s to %s &nbsp; - each text box toggles between '
      'Laymans (everyday-words) and Full; charts and stats are the same in both.</p>'
      % (esc(totals.get("sessions", 0)),
         esc(totals.get("user_message_count", 0) + totals.get("assistant_message_count", 0)),
         esc(dr.get("start", "")), esc(dr.get("end", ""))))
    A('<div class="method"><b>How this differs from /insights.</b> Built by a swarm reading the SAME raw '
      'data /insights reads, but it forms its own judgments, maps the relationships across your agents / '
      'skills / experts / libraries, and subtracts what you already built so only the genuinely-new survives. '
      'Adversarially verified. <b>Proposals only - nothing installed, no score.</b></div>')
    A('<div class="legend"><b>How to use this.</b> Each text box has a small <b>Laymans / Full</b> toggle '
      '(top-right of the box) - Laymans is the default everyday-words version (analogies, no jargon, what it '
      'means for you); Full is the precise wording. Beside every block you can <b>Accept</b> (do / build it), '
      '<b>Reject</b> (skip it), and/or <b>Comment</b>. When done, hit <b>Compose plan request</b> to copy a '
      'prompt that asks me to plan first and wait for your approval, or <b>Export decisions</b> to save your '
      'choices as a file. Charts and stats are graphics - identical in both views.</div>')
    A(body)
    A('<div class="footer-note"><b>Nothing here is installed.</b> Accept / Reject / Comment just records your '
      'choices; Compose turns them into a request for me to draft a PLAN you approve before anything changes - '
      'approved checks route through /update-config, rules into the relevant CLAUDE.md, memory into the vault. '
      'There is no score by design.</div>')
    A('</div>')
    A('<div class="overlay" id="overlay"><div class="modal">'
      '<div class="modal-head"><h3>Plan request (from your Accept / Reject / Comments)</h3>'
      '<p>This asks me to write a plan for your approval before anything is changed. Copy it into Claude, or download it and tell me to read the file.</p></div>'
      '<div class="modal-body"><textarea id="composeText" spellcheck="false"></textarea></div>'
      '<div class="modal-foot"><span class="grow" id="composeMeta"></span>'
      '<button class="btn btn-ghost" id="closeModal">Close</button>'
      '<button class="btn btn-ghost" id="dlPromptBtn">Download .md</button>'
      '<button class="btn btn-primary" id="copyBtn">Copy to clipboard</button></div></div></div>')
    A('<div class="toast" id="toast"></div>')
    A('<script type="application/json" id="stats">%s</script>' % json.dumps(stats))
    A("<script>%s</script>" % JS)
    A("</body></html>")
    return "".join(parts)


def main(argv):
    p = argparse.ArgumentParser(description="Render the per-block annotated amplified insights HTML report.")
    p.add_argument("--findings", required=True)
    p.add_argument("--usage", required=True)
    p.add_argument("--relationships", required=False, default=None)
    p.add_argument("--out", required=True)
    p.add_argument("--date", default=None)
    args = p.parse_args(argv)

    findings = read_json(args.findings, {})
    usage = read_json(args.usage, {})
    rel = read_json(args.relationships, {}) if args.relationships else {}
    date = args.date or usage.get("date_range", {}).get("end", "") or ""

    html_text = build_html(findings, usage, rel, date, args.out).encode("ascii", "replace").decode("ascii")
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(html_text)
    sys.stdout.write("wrote %s (%d bytes)\n" % (args.out, len(html_text)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
