#!/usr/bin/env python3
"""لیام تریدر ۹ — استراتژی داشبورد ۲.۶ (نسخهٔ فشرده)

این فایل برای جعبهٔ «استراتژی» داشبورد ساخته شده: همان کدِ کامل،
بدون کامنت و داک‌استرینگ، تا از سقف اندازهٔ جعبه رد نشود.
نسخهٔ خوانا و مستند در ریپو است — این‌جا فقط اجرا.

ساخت: 2026-08-29 13:21 UTC · کامیت f33e414161
منبع: claude-liam-signal/python/liam9_strategy.py
ساخته‌شده با: python3 -m hamid.build_dashboard

هر تغییرِ تحلیلی در ریپو انجام می‌شود و این فایل دوباره ساخته
می‌شود؛ دست‌کاری مستقیمِ این نسخه در دور بعدِ ساخت پاک می‌شود.
"""

""
import json 
import time 
import urllib .request 

REPO_RAW ="https://raw.githubusercontent.com/Auraliam/Liam-Trader-9/main"
PAGES ="https://auraliam.github.io/Liam-Trader-9"
PARAMS_PATH ="/signals/strategy-params.json"
EXPERIENCE_PATH ="/signals/experience.json"
TOP_LIQ_PATH ="/signals/top-liquidity.json"
EDGE_PATH ="/signals/edge.json"
BTC_SENS_PATH ="/signals/btc-sensitivity.json"

PARAMS ={
"version":"liam9-dash-2.8",
"ibs_long_max":0.30 ,
"ibs_short_min":0.70 ,
"min_net_rr":1.8 ,
"fee_round_trip_pct":0.15 ,
"atr_noise_mult":1.2 ,
"rr_target":2.0 ,
"max_stop_pct":2.0 ,
"pullback_min_ratio":0.25 ,
"pullback_max_ratio":0.90 ,
"exp_min_n":12 ,
"exp_veto_mean_r":-0.25 ,
"min_quality":55 ,

"tp1_close_pct":33 ,
"tp2_rr_mult":2.0 ,
"tp2_trail_lock_pct":85 ,
}

SCALP ={
"ibs_long_max":0.30 ,
"ibs_short_min":0.70 ,
"pullback_min_ratio":0.20 ,
"fee_round_trip_pct":0.15 ,
"max_fee_r":0.30 ,
"rr_target":1.5 ,
"lev_base":45 ,"lev_step":15 ,"lev_max":90 ,
"liq_guard":50.0 ,
"hold_bars":45 ,
}

LEV_MIN ,LEV_MAX_CONF =15 ,39 
MARGIN_PCT_MIN ,MARGIN_PCT_MAX =25.0 ,30.0 
MAX_CONCURRENT =3 
assert LEV_MIN >=1 and LEV_MAX_CONF <=50 ,"بازهٔ اهرم ۲۳ اوت خراب شد"

def _confidence01 (quality ):
    ""
    return max (0.0 ,min (1.0 ,(quality -40 )/60.0 ))

def margin_pct_for (quality ):
    ""
    c =_confidence01 (quality )
    return round (MARGIN_PCT_MIN +(MARGIN_PCT_MAX -MARGIN_PCT_MIN )*c ,1 )

EXPERIENCE ={}

TOP_LIQUIDITY =set ()
_TOP_LIQ_OK =False 

VENUES =[
("https://api.mexc.com/api/v3/klines?symbol={s}&interval={i}&limit={n}","mexc"),
("https://api.gateio.ws/api/v4/spot/candlesticks?currency_pair={g}&interval={i}&limit={n}","gate"),
("https://fapi.binance.com/fapi/v1/klines?symbol={s}&interval={i}&limit={n}","binance"),
]

RISK_CONTRACT ={
"needs_timeframes":{"swing":["4h","1h","15m"],"scalp":["1m"]},
"leverage":{"preferred_swing":10 ,"preferred_scalp_min":45 ,
"preferred_scalp_max":90 ,"hard_floor":3 ,
"note":"سقف پایین‌تر = فقط سایز کوچک‌تر؛ لبه عوض نمی‌شود"},
"stop_pct":{"swing_min":0.30 ,"swing_max":2.0 ,
"scalp_min":0.50 ,"scalp_max":1.6 ,
"note":"کفِ استاپِ داشبورد بالای این بازه = وتوی خاموش"},
"fees":{"round_trip_pct":0.15 ,
"note":"کارمزد کمتر از این در داشبورد = RR خوش‌بین"},
"concurrency":{"min_slots":3 ,"min_cooldown_s":0 ,
"max_hold_min_scalp":45 ,"max_hold_h_swing":24 },
"sizing":{"risk_per_trade_pct":[1.0 ,5.0 ],
"note":"سایز معکوس نوسان؛ سقف اکسپوژر کل با داشبورد"},

"execution":{"product":"futures_only",
"margin_mode":"isolated",
"cross_margin_forbidden":True ,
"sl_tp_mandatory":True ,
"note":("داشبورد باید SL و TP را همان لحظهٔ باز شدن روی "
"صرافی بگذارد؛ پوزیشن بدون هر دو = نقض قرارداد")},
}

ENV ={"margin_mode":None }

ANTI_REPEAT_S ={"swing":3 *3600 ,"scalp":1800 }
_LAST ={}

def _repeat_gate (symbol ,direction ,bar_ms ,mode ="swing"):
    ""
    key =f"{symbol}|{direction}|{mode}"
    win =ANTI_REPEAT_S .get (mode ,ANTI_REPEAT_S ["swing"])*1000 
    last =_LAST .get (key )
    if last is not None and last !=bar_ms and 0 <bar_ms -last <win :
        left =int ((win -(bar_ms -last ))/60000 )
        return (f"ضدتکرار: همین ارز/جهت {int((bar_ms - last) / 60000)} دقیقه "
        f"پیش سیگنال گرفته — {left} دقیقه تا آزاد شدن")
    _LAST [key ]=bar_ms 
    return None 

def _finalize (sig ):
    ""
    if sig .get ("action")in ("LONG","SHORT"):
        if ENV .get ("margin_mode")and "cross"in str (ENV ["margin_mode"]).lower ():
            return {"action":"NO_SIGNAL","symbol":sig .get ("symbol","?"),
            "why":("مارجین داشبورد CROSS است — تا وقتی در تنظیمات "
            "پوزیشن Isolated نشود هیچ سیگنالی صادر نمی‌شود "
            "(دستور صریح ۲۰ اوت)"),
            "panel":"لیام تریدر ۹"}
        if not (sig .get ("sl")and sig .get ("tp1")):
            return {"action":"NO_SIGNAL","symbol":sig .get ("symbol","?"),
            "why":"سیگنال بدون استاپ/تارگت باطل است — قرارداد اجرا",
            "panel":"لیام تریدر ۹"}
        sig ["product"]="futures"
        sig ["margin_mode"]="isolated"
        sig ["sl_tp_mandatory"]=True 
        sig ["stop_loss"]=sig ["sl"]
        sig ["take_profit"]=sig ["tp1"]
    return sig 

def market_gate (direction ,btc4h ,btc1h ):
    ""
    if not btc4h or not btc1h :
        return "veto","بستر BTC نرسیده — قانون ۱: بدون داده سیگنال نیست"
    b4 ,b1 =trend (btc4h ),trend (btc1h )
    if b4 is None or b1 is None :
        return "veto","روند BTC قابل‌سنجش نیست"
    opp ="down"if direction =="LONG"else "up"
    against =(b4 ==opp )+(b1 ==opp )
    if against ==2 :
        return "veto",f"هر دو تایم BTC ({b4}/{b1}) خلاف جهت — وتوی مطلق"
    if against ==1 :
        return "counter",f"یک تایم BTC خلاف جهت (۴س {b4} · ۱س {b1})"
    return "ok",f"بستر BTC هم‌قصه (۴س {b4} · ۱س {b1})"

def _get (url ,timeout =15 ):
    req =urllib .request .Request (url ,headers ={"User-Agent":"liam9-strategy"})
    with urllib .request .urlopen (req ,timeout =timeout )as r :
        return json .load (r )

def sync_params ():
    ""
    for base in (REPO_RAW ,PAGES ):
        try :
            d =_get (base +PARAMS_PATH )
            if isinstance (d ,dict )and d .get ("version"):
                PARAMS .update ({k :v for k ,v in d .items ()})
                return PARAMS ["version"]
        except Exception as e :
            print (f"⚠️ پارامترها از {base} نیامد ({type(e).__name__}) — "
            f"پیش‌فرض داخلی استفاده می‌شود",flush =True )
            continue 
    return None 

def sync_experience ():
    ""
    for base in (REPO_RAW ,PAGES ):
        try :
            d =_get (base +EXPERIENCE_PATH )
            if isinstance (d ,dict )and isinstance (d .get ("index"),dict ):
                EXPERIENCE .clear ()
                EXPERIENCE .update (d ["index"])
                return len (EXPERIENCE )
        except Exception :
            continue 
    return 0 

def sync_top_liquidity ():
    ""
    global _TOP_LIQ_OK 
    for base in (REPO_RAW ,PAGES ):
        try :
            d =_get (base +TOP_LIQ_PATH )
            syms =d .get ("symbols")if isinstance (d ,dict )else None 
            if isinstance (syms ,list )and syms :
                TOP_LIQUIDITY .clear ()
                TOP_LIQUIDITY .update (s .upper ()for s in syms )
                _TOP_LIQ_OK =True 
                return len (TOP_LIQUIDITY )
        except Exception as e :
            print (f"⚠️ لایهٔ نقدشوندگی از {base} نیامد ({type(e).__name__}) — "
            f"تا رفعش، سیگنال سوینگِ آلت صادر نمی‌شود (قانون ۱)",flush =True )
            continue 
    _TOP_LIQ_OK =False 
    return 0 

EDGE ={"rules":{},"stale":True }

EDGE_POINTS_PER_R =20 
EDGE_CAP =15 

def sync_edge ():
    for base in (REPO_RAW ,PAGES ):
        try :
            d =_get (base +EDGE_PATH )
            if isinstance (d ,dict )and isinstance (d .get ("rules"),dict ):
                EDGE .clear ()
                EDGE .update ({"rules":d ["rules"],
                "stale":bool (d .get ("stale",True )),
                "measured_at":d .get ("measured_at")})
                return 0 if EDGE ["stale"]else d .get ("n_rules",0 )
        except Exception :
            continue 
    return 0 

def edge_boost (strategy ,flags ):
    ""
    if EDGE .get ("stale")or not EDGE .get ("rules"):
        return 0 ,[],None 
    d =flags .get ("dir")
    tests ={
    "لانگ همسو با بیت‌کوین":d =="LONG"and flags .get ("btc_up"),
    "شورت همسو با بیت‌کوین":d =="SHORT"and flags .get ("btc_down"),
    "بیت‌کوین صعودی":bool (flags .get ("btc_up")),
    "بیت‌کوین نزولی":bool (flags .get ("btc_down")),
    "داخل اردر بلاک":bool (flags .get ("in_ob")),
    }
    total ,hits ,untested =0.0 ,[],0 
    for r in EDGE ["rules"].get (strategy ,[]):
        cond =r .get ("condition")
        if cond not in tests :
            untested +=1 
            continue 
        if tests [cond ]:
            total +=float (r .get ("delta")or 0 )
            hits .append ({"rule":cond ,"delta":r .get ("delta"),
            "n":r .get ("n")})
    if not hits :
        return 0 ,[],({"untested":untested }if untested else None )
    pts =max (-EDGE_CAP ,min (EDGE_CAP ,round (total *EDGE_POINTS_PER_R )))
    lines =[f"🎓 قانون تأییدشدهٔ بک‌تست: {h['rule']} "
    f"({h['delta']:+}R · n={h['n']})"for h in hits ]
    return pts ,lines ,{"boost_pts":pts ,"delta_r":round (total ,3 ),
    "rules":hits ,"untested":untested }

ROOM_W ={"weights":{},"stale":True ,"ctx":"unknown"}
ROOM_W_PATH ="/signals/agent-weights.json"
ROOM_W_CAP =10.0 

def sync_room_weights (ctx =None ):
    ""
    for base in (REPO_RAW ,PAGES ):
        try :
            d =_get (base +ROOM_W_PATH )
            if not isinstance (d ,dict )or not d .get ("rooms"):
                continue 
            age_h =(time .time ()*1000 -(d .get ("generated")or 0 ))/3_600_000 
            stale =age_h >48 
            use_ctx =ctx or d .get ("live_ctx")or "all"
            w ={}
            for room ,rec in (d .get ("rooms")or {}).items ():
                by =rec .get ("by_context")or {}
                pick =by .get (use_ctx )or by .get ("all")or {}
                w [room ]=1.0 if stale else float (pick .get ("weight")or 1.0 )
            ROOM_W .clear ()
            ROOM_W .update ({"weights":w ,"stale":stale ,"ctx":use_ctx ,
            "age_h":round (age_h ,1 )})
            return 0 if stale else len (w )
        except Exception :
            continue 
    return 0 

def room_weight (room ):
    ""
    if ROOM_W .get ("stale"):
        return 1.0 
    try :
        return float ((ROOM_W .get ("weights")or {}).get (room )or 1.0 )
    except (TypeError ,ValueError ):
        return 1.0 

def apply_room_weights (parts ):
    ""
    base =sum (p for _ ,p in parts )
    weighted =sum (p *room_weight (r )for r ,p in parts )
    delta =max (-ROOM_W_CAP ,min (ROOM_W_CAP ,weighted -base ))
    lines ,used =[],{}
    for r ,p in parts :
        w =room_weight (r )
        used [r ]=w 
        if p and abs (w -1.0 )>=0.05 :
            lines .append (f"⚖️ وزن اتاق {r}: ×{w:.2f} "
            f"(کارنامهٔ پیپر در بستر {ROOM_W.get('ctx')})")
    return round (delta ,1 ),lines ,used 

BTC_SENS ={"coins":{},"generated":0 }
BTC_SENS_STALE_H =24 
BTC_CTX_DAMP =0.5 

def sync_btc_sensitivity ():
    ""
    global BTC_SENS 
    for base in (REPO_RAW ,PAGES ):
        try :
            j =_get (base +BTC_SENS_PATH )
            if isinstance (j ,dict )and isinstance (j .get ("coins"),dict ):
                age_h =(time .time ()*1000 -(j .get ("generated")or 0 ))/3600e3 
                BTC_SENS =j if age_h <=BTC_SENS_STALE_H else {"coins":{},"generated":0 }
                return len (BTC_SENS .get ("coins")or {})
        except Exception :
            continue 
    BTC_SENS ={"coins":{},"generated":0 }
    return 0 

def btc_klass (symbol ):
    ""
    row =(BTC_SENS .get ("coins")or {}).get (symbol )
    if not isinstance (row ,dict ):
        return "UNKNOWN"
    age_h =(time .time ()*1000 -(row .get ("at")or 0 ))/3600e3 
    if age_h >BTC_SENS_STALE_H :
        return "UNKNOWN"
    return row .get ("klass","UNKNOWN")

def btc_ctx_weight (symbol ):
    ""
    return BTC_CTX_DAMP if btc_klass (symbol )=="INDEPENDENT"else 1.0 

def sync_all ():
    ""
    return {"params":sync_params (),"experience_pairs":sync_experience (),
    "top_liquidity":sync_top_liquidity (),
    "edge_rules":sync_edge (),
    "room_weights":sync_room_weights (),
    "btc_sensitivity":sync_btc_sensitivity ()}

def experience_of (symbol ,direction ):
    ""
    return EXPERIENCE .get (f"{symbol}|{direction}")

def fetch_klines (symbol ,interval ="15m",n =300 ):
    ""
    for tmpl ,venue in VENUES :
        url =tmpl .format (s =symbol ,n =n ,i =interval ,
        g =symbol .replace ("USDT","_USDT"))
        try :
            rows =_get (url )
            out =[]
            for k in rows :
                if venue =="gate":
                    out .append ({"t":int (k [0 ])*1000 ,"o":float (k [5 ]),
                    "h":float (k [3 ]),"l":float (k [4 ]),
                    "c":float (k [2 ])})
                else :
                    out .append ({"t":int (k [0 ]),"o":float (k [1 ]),
                    "h":float (k [2 ]),"l":float (k [3 ]),
                    "c":float (k [4 ])})
            if len (out )>=50 :
                return out 
        except Exception :
            continue 
    return None 

def ema (vals ,n ):
    if len (vals )<n :
        return None 
    k =2.0 /(n +1 )
    e =sum (vals [:n ])/n 
    for v in vals [n :]:
        e =v *k +e *(1 -k )
    return e 

def atr (cd ,n =14 ):
    if len (cd )<n +1 :
        return None 
    trs =[max (cd [i ]["h"]-cd [i ]["l"],abs (cd [i ]["h"]-cd [i -1 ]["c"]),
    abs (cd [i ]["l"]-cd [i -1 ]["c"]))for i in range (1 ,len (cd ))]
    a =sum (trs [:n ])/n 
    for t in trs [n :]:
        a =(a *(n -1 )+t )/n 
    return a 

def trend (cd ):
    ""
    closes =[k ["c"]for k in cd ]
    e50 ,e200 =ema (closes ,50 ),ema (closes ,200 )
    if e50 is None or e200 is None :
        return None 
    px =closes [-1 ]
    hi_now =max (k ["h"]for k in cd [-30 :])
    hi_prev =max (k ["h"]for k in cd [-60 :-30 ])
    lo_now =min (k ["l"]for k in cd [-30 :])
    lo_prev =min (k ["l"]for k in cd [-60 :-30 ])
    if e50 >e200 and px >e200 and hi_now >=hi_prev :
        return "up"
    if e50 <e200 and px <e200 and lo_now <=lo_prev :
        return "down"
    return "range"

def ibs (k ):
    rng =k ["h"]-k ["l"]
    return (k ["c"]-k ["l"])/rng if rng >0 else 0.5 

def candle_pattern (cd ,direction ):
    ""
    if len (cd )<3 :
        return None ,[]
    k ,p =cd [-1 ],cd [-2 ]
    rng =k ["h"]-k ["l"]
    if rng <=0 :
        return None ,[]
    body =abs (k ["c"]-k ["o"])
    up_w ,dn_w =k ["h"]-max (k ["c"],k ["o"]),min (k ["c"],k ["o"])-k ["l"]
    names =[]
    bull =k ["c"]>k ["o"]
    if body /rng >=0.60 :
        names .append ("بدنهٔ قاطع"+(" صعودی"if bull else " نزولی"))
    if dn_w >=2 *body and dn_w >up_w :
        names .append ("پین‌بار کف (رد فروش)")
    if up_w >=2 *body and up_w >dn_w :
        names .append ("پین‌بار سقف (رد خرید)")
    p_body =abs (p ["c"]-p ["o"])
    if body >p_body and ((bull and p ["c"]<p ["o"]and k ["c"]>=p ["o"])
    or (not bull and p ["c"]>p ["o"]and k ["c"]<=p ["o"])):
        names .append ("بلعنده")
    if not names :
        return None ,[]
    bullish =bull or "پین‌بار کف (رد فروش)"in names 
    align =("with"if (bullish and direction =="LONG")
    or (not bullish and direction =="SHORT")else "against")
    return align ,names 

CANDLE_GEOM_VERSION ="e09-geom-1.0"

def candle_geometry (cd ,n_atr =14 ):
    ""
    if len (cd )<n_atr +2 :
        return None 
    k =cd [-1 ]
    rng =k ["h"]-k ["l"]
    if rng <=0 :
        return None 
    a =atr (cd [-(n_atr +1 ):],n_atr )or 0 
    body =abs (k ["c"]-k ["o"])
    up_w =k ["h"]-max (k ["c"],k ["o"])
    dn_w =min (k ["c"],k ["o"])-k ["l"]
    return {
    "formula_version":CANDLE_GEOM_VERSION ,
    "body_range":round (body /rng ,3 ),
    "upper_wick_range":round (up_w /rng ,3 ),
    "lower_wick_range":round (dn_w /rng ,3 ),
    "ibs":round (ibs (k ),3 ),
    "atr_norm_range":round (rng /a ,3 )if a >0 else None ,
    "displacement":bool (a >0 and rng >=1.8 *a ),
    }

def order_block_zone (cd ,direction ,lookback =120 ,disp_atr_mult =1.8 ):
    ""
    if len (cd )<lookback +20 :
        return None 
    win =cd [-lookback :]
    a =atr (win )or 0 
    if a <=0 :
        return None 
    px =win [-1 ]["c"]
    want_role ="demand"if direction =="LONG"else "supply"
    best =None 
    for i in range (3 ,len (win )-1 ):
        body =win [i ]["c"]-win [i ]["o"]

        if want_role =="demand"and body <=disp_atr_mult *a :
            continue 
        if want_role =="supply"and -body <=disp_atr_mult *a :
            continue 

        j =i -1 
        if want_role =="demand"and win [j ]["c"]>=win [j ]["o"]:
            continue 
        if want_role =="supply"and win [j ]["c"]<=win [j ]["o"]:
            continue 
        lo ,hi =min (win [j ]["o"],win [j ]["c"]),max (win [j ]["o"],win [j ]["c"])
        if hi <=lo :
            continue 

        mitigated ,reactions =False ,0 
        for k in win [i +1 :]:
            if want_role =="demand"and k ["c"]<lo :
                mitigated =True 
            elif want_role =="supply"and k ["c"]>hi :
                mitigated =True 
            elif lo <=k ["h"]and k ["l"]<=hi :
                reactions +=1 
        dist_pct =abs (px -(lo if want_role =="demand"else hi ))/px *100 
        cand ={"lo":lo ,"hi":hi ,"role":want_role ,"reactions":reactions ,
        "fresh":not mitigated ,"mitigated":mitigated ,
        "dist_pct":round (dist_pct ,3 )}
        if best is None or dist_pct <best ["dist_pct"]:
            best =cand 
    return best 

def _pullback (c15 ,direction ,win_n =60 ,min_leg =8 ):
    ""
    win =c15 [-win_n :]
    px =win [-1 ]["c"]
    if direction =="LONG":
        hi_i =max (range (len (win )),key =lambda i :win [i ]["h"])
        if hi_i <min_leg or hi_i >len (win )-2 :
            return None 
        lo_i =min (range (hi_i +1 ),key =lambda i :win [i ]["l"])
        hi ,lo =win [hi_i ]["h"],win [lo_i ]["l"]
        pull_lo =min (k ["l"]for k in win [hi_i :])
        if hi <=lo :
            return None 
        return (hi -px )/(hi -lo ),pull_lo 
    lo_i =min (range (len (win )),key =lambda i :win [i ]["l"])
    if lo_i <min_leg or lo_i >len (win )-2 :
        return None 
    hi_i =max (range (lo_i +1 ),key =lambda i :win [i ]["h"])
    hi ,lo =win [hi_i ]["h"],win [lo_i ]["l"]
    pull_hi =max (k ["h"]for k in win [lo_i :])
    if hi <=lo :
        return None 
    return (px -lo )/(hi -lo ),pull_hi 

def _exit_plan (direction ,entry ,tp1 ,risk ,P ):
    ""
    fee_buf =entry *(P ["fee_round_trip_pct"]/100 )
    close1 =P ["tp1_close_pct"]
    tp2_dist =(tp1 -entry )*P ["tp2_rr_mult"]if direction =="LONG"else (entry -tp1 )*P ["tp2_rr_mult"]
    if direction =="LONG":
        stop_after_tp1 =entry +fee_buf 
        tp2 =entry +tp2_dist 
    else :
        stop_after_tp1 =entry -fee_buf 
        tp2 =entry -tp2_dist 

    trail_arm =entry +fee_buf if direction =="LONG"else entry -fee_buf 
    return {"tp1_close_pct":close1 ,
    "trail_arm":round (trail_arm ,8 ),
    "stop_after_tp1":round (stop_after_tp1 ,8 ),
    "tp2":round (tp2 ,8 ),
    "tp2_trail_lock_pct":P ["tp2_trail_lock_pct"],
    "note":(f"روی تی‌پی۱: {close1}٪ ببند، استاپ باقیمانده روی "
    f"{round(stop_after_tp1, 8)} (ورود+کارمزد) — برایند کل "
    "قطعاً مثبت. روی تی‌پی۲: استاپ در "
    f"{P['tp2_trail_lock_pct']}٪ فاصلهٔ سود قفل، فقط "
    "بالا می‌رود — این عدد را در تریل داشبورد بگذار.")}

_LIQ_LEV =((10 ,1.0 ),(25 ,0.8 ),(50 ,0.6 ),(100 ,0.4 ))

def _liq_map (cd ,look =48 ,bins =60 ,span_pct =6.0 ):
    ""
    if not cd or len (cd )<look +2 :
        return None 
    px =cd [-1 ]["c"]
    lo ,hi =px *(1 -span_pct /100 ),px *(1 +span_pct /100 )
    step =(hi -lo )/bins 
    if step <=0 or px <=0 :
        return None 
    heat =[0.0 ]*bins 
    window =cd [-look :]
    vmax =max (c .get ("v")or 0 for c in window )or 1.0 
    for c in window :
        w_vol =(c .get ("v")or 0 )/vmax 
        for lev ,w in _LIQ_LEV :
            for liq_px in (c ["c"]*(1 -1 /lev ),c ["c"]*(1 +1 /lev )):
                k =int ((liq_px -lo )/step )
                if 0 <=k <bins :
                    heat [k ]+=w_vol *w 
    peak =max (heat )or 1.0 
    clusters =[{"price":round (lo +(k +0.5 )*step ,10 ),
    "pct_away":round (((lo +(k +0.5 )*step )/px -1 )*100 ,2 ),
    "score":round (h /peak *100 )}
    for k ,h in enumerate (heat )if h >=peak *0.35 ]
    above =sorted ([c for c in clusters if c ["pct_away"]>0 ],
    key =lambda c :c ["pct_away"])[:3 ]
    below =sorted ([c for c in clusters if c ["pct_away"]<0 ],
    key =lambda c :-c ["pct_away"])[:3 ]
    sa ,sb =sum (c ["score"]for c in above ),sum (c ["score"]for c in below )
    magnet =None 
    if sa or sb :
        magnet ="above"if sa >sb *1.3 else ("below"if sb >sa *1.3 
        else "balanced")
    return {"above":above ,"below":below ,"magnet":magnet ,
    "note":"تخمین از کندل واقعی (حجم × اهرم‌های رایج)"}

def _liq_line (lm ):
    ""
    bits =[]
    if lm ["above"]:
        a =lm ["above"][0 ]
        bits .append (f"خوشهٔ لیکویید بالا {a['pct_away']:+}٪ (شدت {a['score']})")
    if lm ["below"]:
        b =lm ["below"][0 ]
        bits .append (f"پایین {b['pct_away']:+}٪ (شدت {b['score']})")
    if not bits :
        return None 
    tail ={"above":"— آهن‌ربا بالا","below":"— آهن‌ربا پایین",
    "balanced":"— متوازن"}.get (lm ["magnet"],"")
    return "💧 "+" · ".join (bits )+(f" {tail}"if tail else "")

def analyze (symbol ,c4h ,c1h ,c15 ,btc4h =None ,btc1h =None ):
    ""
    P =PARAMS 
    def no (why ):
        return {"action":"NO_SIGNAL","symbol":symbol ,"why":why ,
        "version":P ["version"],"panel":"لیام تریدر ۹"}

    if not c4h or not c1h or not c15 or len (c15 )<60 :
        return no ("دادهٔ ناکافی — قانون ۱: حدس ممنوع")
    t4 ,t1 =trend (c4h ),trend (c1h )
    if t4 is None or t1 is None :
        return no ("روند تایم بالا قابل‌سنجش نیست (کندل کم)")
    if t4 =="up"and t1 !="down":
        direction ="LONG"
    elif t4 =="down"and t1 !="up":
        direction ="SHORT"
    else :
        return no (f"روند ۴س ({t4}) و ۱س ({t1}) هم‌قصه نیستند — وتوی روند")

    is_btc =symbol .upper ().replace ("USDT","").replace ("USD","")=="BTC"
    if not is_btc and (not _TOP_LIQ_OK or symbol .upper ()not in TOP_LIQUIDITY ):
        return no ("خارج از لایهٔ نقدشوندگی برتر ۶۰ یا لایه همگام نشده — "
        "تنها لایهٔ سنجیده‌شده با CI بالای صفر (۲۱ اوت: top60 "
        "CI[+0.199,+0.669]؛ رتبهٔ ۶۱+ هنوز صفر داخلش هست)")
    mkt ,mkt_why =("ok","خود بازار است")if is_btc else market_gate (direction ,btc4h ,btc1h )
    if mkt =="veto":
        return no (f"دروازهٔ بازار: {mkt_why}")
    pb =_pullback (c15 ,direction )
    if pb is None :
        return no ("موج/پولبک معتبری در ۱۵د نیست")
    ratio ,pull_ext =pb 
    if not (P ["pullback_min_ratio"]<=ratio <=P ["pullback_max_ratio"]):
        return no (f"عمق پولبک {ratio:.2f} خارج از بازهٔ سالم")
    k_last =c15 [-1 ]
    i =ibs (k_last )
    if direction =="LONG"and i >P ["ibs_long_max"]:
        return no (f"IBS={i:.2f} — تأیید لانگ نیست (کف {P['ibs_long_max']})")
    if direction =="SHORT"and i <P ["ibs_short_min"]:
        return no (f"IBS={i:.2f} — تأیید شورت نیست (سقف {P['ibs_short_min']})")

    entry =k_last ["c"]
    a15 =atr (c15 [-80 :])or 0 
    if direction =="LONG":
        sl =min (pull_ext ,entry -P ["atr_noise_mult"]*a15 )
        risk =entry -sl 
        tp1 =entry +P ["rr_target"]*risk 
    else :
        sl =max (pull_ext ,entry +P ["atr_noise_mult"]*a15 )
        risk =sl -entry 
        tp1 =entry -P ["rr_target"]*risk 
    if risk <=0 :
        return no ("هندسهٔ استاپ نامعتبر")
    stop_pct =risk /entry *100 
    if stop_pct >P ["max_stop_pct"]:
        return no (f"استاپ {stop_pct:.2f}٪ — بزرگ‌تر از سقف {P['max_stop_pct']}٪")
    fee_r =(P ["fee_round_trip_pct"]/100 )*entry /risk 
    net_rr =P ["rr_target"]-fee_r 
    if net_rr <P ["min_net_rr"]:
        return no (f"RR خالص {net_rr:.2f} زیر کف {P['min_net_rr']} — دام کارمزد")

    exp =experience_of (symbol ,direction )
    exp_used =bool (exp and not exp .get ("thin"))
    if exp_used and exp ["mean_r"]<=P ["exp_veto_mean_r"]:
        return no (f"کارنامهٔ همین ارز/جهت: {exp['n']} معامله، "
        f"میانگین {exp['mean_r']:+.2f}R — تجربه می‌گوید نرو")

    align ,pat_names =candle_pattern (c15 ,direction )

    quality =60 
    why =[f"روند ۴س {t4} · ۱س {t1} هم‌جهت",
    f"پولبک {ratio:.2f} در جهت روند",
    f"IBS {i:.2f} تأیید ورود",
    f"استاپ بیرون نویز ({P['atr_noise_mult']}×ATR)",
    f"RR خالص از کارمزد {net_rr:.2f}"]

    room_parts =[]
    if exp_used :
        _p =20 if exp ["mean_r"]>0 else 5 
        quality +=_p 
        room_parts .append (("experience",_p ))
        why .append (f"تجربه: {exp['n']} معاملهٔ بسته، برد {exp['win_pct']}٪، "
        f"میانگین {exp['mean_r']:+.2f}R "
        f"(عامل ۸۶.۹٪-برد دفتر ما)")
    elif exp :
        why .append (f"تاریخچهٔ نازک ({exp['n']} معامله) — گزارش، بدون وزن")
    if align =="with":
        quality +=10 
        room_parts .append (("candles",10 ))
        why .append ("کندل هم‌جهت: "+"، ".join (pat_names ))
    elif align =="against":
        quality -=5 
        room_parts .append (("candles",-5 ))
        why .append ("کندل مخالف: "+"، ".join (pat_names ))
    if 0.38 <=ratio <=0.705 :
        quality +=5 
        room_parts .append (("fib",5 ))
        why .append ("عمق پولبک در ناحیهٔ طلایی فیبوناچی (آزمایشی)")

    _bt =t4 if is_btc else (trend (btc4h )if btc4h else None )
    _ob =order_block_zone (c1h ,direction )
    edge_pts ,edge_lines ,edge_rec =edge_boost ("ibs",{
    "dir":direction ,"btc_up":_bt =="up","btc_down":_bt =="down",
    "in_ob":bool (_ob and _ob .get ("fresh")
    and _ob ["lo"]<=k_last ["c"]<=_ob ["hi"])})
    quality +=edge_pts 
    why +=edge_lines 

    if edge_pts :
        room_parts .append (("smc",edge_pts ))
    room_delta ,room_lines ,room_used =apply_room_weights (room_parts )
    quality +=room_delta 
    why +=room_lines 
    quality =max (0 ,min (100 ,round (quality )))
    if quality <P ["min_quality"]:
        return no (f"امتیاز کیفیت {quality} زیر کف {P['min_quality']}")

    if mkt =="counter":
        if align !="with"or quality <70 :
            return no (f"خلاف بازار ({mkt_why}) بدون تأیید کامل — "
            f"کندل {align}، کیفیت {quality}")
        why .append (f"⚠️ خلاف بازار — {mkt_why}؛ با تأیید کامل عبور کرد")
    else :
        why .append (mkt_why )

    rep =_repeat_gate (symbol ,direction ,k_last ["t"],"swing")
    if rep :
        return no (rep )

    lm =_liq_map (c1h )
    if lm is None :
        return no ("نقشهٔ نقدینگی از کندل ۱س ساختنی نیست — بررسی نقدینگی اجباری است")
    _ll =_liq_line (lm )
    if _ll :
        why .append (_ll )

    plan =_exit_plan (direction ,entry ,tp1 ,risk ,P )
    why .append (f"🪜 نردبان خروج: تی‌پی۱ {plan['tp1_close_pct']}٪ ببند → "
    f"استاپ {plan['stop_after_tp1']} (برایند مثبت قطعی) · "
    f"تی‌پی۲ {plan['tp2']} → تریل {plan['tp2_trail_lock_pct']}٪ "
    "فاصلهٔ سود، فقط بالا")

    return _finalize ({"action":direction ,"symbol":symbol ,
    "entry":round (entry ,8 ),"sl":round (sl ,8 ),
    "tp1":round (tp1 ,8 ),"rr_net":round (net_rr ,2 ),
    "stop_pct":round (stop_pct ,3 ),"ibs":round (i ,2 ),
    "pullback":round (ratio ,3 ),"trend_4h":t4 ,"trend_1h":t1 ,
    "quality":quality ,"exp_used":exp_used ,"liq_map":lm ,

    "edge":edge_rec ,"edge_used":bool (edge_pts ),

    "room_weights":room_used ,"room_delta":room_delta ,
    "room_ctx":ROOM_W .get ("ctx"),
    "experience":exp ,"pattern_align":align ,"patterns":pat_names ,
    "leverage":suggest_leverage (stop_pct ,quality ,mode ="swing"),
    "margin_pct":margin_pct_for (quality ),
    "exit_plan":plan ,
    "mode":"swing","tf":"15m",
    "panel":"لیام تریدر ۹","version":P ["version"],
    "t":int (time .time ()*1000 ),"why":why })

def session_of (ms ):
    ""
    h =time .gmtime (ms /1000 ).tm_hour 
    if 12 <=h <16 :
        return "overlap"
    if 7 <=h <16 :
        return "london"
    if 16 <=h <21 :
        return "ny"
    return "asia"

def suggest_leverage (stop_pct ,quality ,mode ="swing"):
    ""
    if stop_pct <=0 :
        return None 
    guard =int (SCALP ["liq_guard"]/stop_pct )

    want =LEV_MIN +round ((LEV_MAX_CONF -LEV_MIN )*_confidence01 (quality ))
    lev =min (want ,guard )
    return lev if lev >=LEV_MIN else None 

def scalp_decide (c1m ,symbol ="?"):
    ""
    S =SCALP 
    def no (why ):
        return {"action":"NO_SIGNAL","symbol":symbol ,"mode":"scalp",
        "tf":"1m","why":why ,"panel":"لیام تریدر ۹"}

    if not c1m or len (c1m )<90 :
        return no ("کندل ۱ دقیقه کافی نیست — قانون ۱")

    _now =int (time .time ()*1000 )
    if c1m and _now -c1m [-1 ]["t"]<60_000 :
        c1m =c1m [:-1 ]
        if len (c1m )<90 :
            return no ("بعد از حذف کندل باز، کندل کافی نیست — قانون ۱")
    closes =[k ["c"]for k in c1m ]
    e21 ,e55 =ema (closes [-90 :],21 ),ema (closes [-90 :],55 )
    if e21 is None or e55 is None :
        return no ("EMA کوتاه قابل‌محاسبه نیست")
    px =closes [-1 ]
    if e21 >e55 and px >e55 :
        direction ="LONG"
    elif e21 <e55 and px <e55 :
        direction ="SHORT"
    else :
        return no ("روند ۱ دقیقه خنثی — اسکلپ در رنجِ بی‌جهت ممنوع")

    pb =_pullback (c1m ,direction ,win_n =45 ,min_leg =6 )
    if pb is None :
        return no ("پولبک معتبری در ۱د نیست")
    ratio ,pull_ext =pb 
    if ratio <S ["pullback_min_ratio"]:
        return no (f"پولبک {ratio:.2f} کم‌عمق — لرزش، نه پولبک")
    k_last =c1m [-1 ]
    i =ibs (k_last )
    if direction =="LONG"and i >S ["ibs_long_max"]:
        return no (f"IBS={i:.2f} تأیید لانگ نیست")
    if direction =="SHORT"and i <S ["ibs_short_min"]:
        return no (f"IBS={i:.2f} تأیید شورت نیست")

    entry =px 
    sl =pull_ext 
    risk =entry -sl if direction =="LONG"else sl -entry 
    if risk <=0 :
        return no ("هندسهٔ استاپ نامعتبر")
    stop_pct =risk /entry *100 
    fee_r =(S ["fee_round_trip_pct"]/100 )*entry /risk 
    if fee_r >=S ["max_fee_r"]:
        return no (f"دام کارمزد: کارمزد {fee_r:.2f}R از استاپ {stop_pct:.2f}٪ "
        f"— استاپ باید بالای ~۰.۵٪ باشد")
    tp1 =(entry +S ["rr_target"]*risk if direction =="LONG"
    else entry -S ["rr_target"]*risk )

    opp_dir ="SHORT"if direction =="LONG"else "LONG"
    opp_ob =order_block_zone (c1m ,opp_dir )
    if opp_ob and opp_ob ["fresh"]:
        blocks_path =((direction =="LONG"and entry <opp_ob ["lo"]<=tp1 )or 
        (direction =="SHORT"and entry >opp_ob ["hi"]>=tp1 ))
        if blocks_path :
            return no (f"اردر بلاک مخالفِ تازه بین ورود و تارگت است "
            f"({opp_ob['dist_pct']:.2f}٪ فاصله) — مسیر مسدود")
    own_ob =order_block_zone (c1m ,direction )
    ob_bonus =bool (own_ob and own_ob ["fresh"]and own_ob ["dist_pct"]<=0.6 )

    align ,pat_names =candle_pattern (c1m ,direction )
    geom =candle_geometry (c1m )
    sess =session_of (k_last ["t"])
    quality =55 +(10 if align =="with"else -10 if align =="against"else 0 )
    quality +=10 if sess in ("london","ny","overlap")else 0 
    quality +=8 if ob_bonus else 0 
    exp =experience_of (symbol ,direction )
    if exp and not exp .get ("thin"):
        quality +=15 if exp ["mean_r"]>0 else -10 
    quality =max (0 ,min (100 ,quality ))
    lev =suggest_leverage (stop_pct ,quality ,mode ="scalp")
    if lev is None :
        return no (f"استاپ {stop_pct:.2f}٪ برای اهرم اسکلپ زیادی گشاد است "
        f"(محافظ فاصلهٔ لیکویید)")
    rep =_repeat_gate (symbol ,direction ,k_last ["t"],"scalp")
    if rep :
        return no (rep )

    lm =_liq_map (c1m )
    if lm is None :
        return no ("نقشهٔ نقدینگی از کندل ۱د ساختنی نیست — بررسی نقدینگی اجباری است")

    zone =0.35 *abs (entry -sl )
    return _finalize ({"action":direction ,"symbol":symbol ,"mode":"scalp","tf":"1m",
    "entry":round (entry ,8 ),"sl":round (sl ,8 ),"tp1":round (tp1 ,8 ),
    "entry_zone":[round (entry -zone ,8 ),round (entry +zone ,8 )],
    "expiry_rule":"بیرون از entry_zone = EXPIRED؛ ورود نکن",
    "max_hold_min":S ["hold_bars"],
    "margin_pct":margin_pct_for (quality ),
    "stop_pct":round (stop_pct ,3 ),"fee_r":round (fee_r ,3 ),
    "rr_net":round (S ["rr_target"]-fee_r ,2 ),"ibs":round (i ,2 ),
    "pullback":round (ratio ,3 ),"session":sess ,"leverage":lev ,
    "quality":quality ,"pattern_align":align ,"patterns":pat_names ,
    "candle_evidence":geom ,"order_block":own_ob ,"liq_map":lm ,
    "trail_at":round (entry +(tp1 -entry )/3 ,8 ),
    "panel":"لیام تریدر ۹","version":PARAMS ["version"],
    "t":int (time .time ()*1000 ),
    "why":[f"روند ۱د {'صعودی' if direction == 'LONG' else 'نزولی'} "
    f"(EMA21/55)",
    f"پولبک {ratio:.2f} در جهت روند",
    f"IBS {i:.2f} تأیید",
    f"سشن {sess}"]+(
    [f"در باکس اردر بلاک تازه ({own_ob['dist_pct']:.2f}٪ فاصله)"]
    if ob_bonus else [])+[
    f"کارمزد {fee_r:.2f}R زیر سقف {S['max_fee_r']}",
    f"اهرم {lev}× با محافظ لیکویید (استاپ ≤ نصف راه)",
    "🪜 تریل: در ⅓ مسیر، استاپ به سربه‌سرِ کارمزددار"]})

def signal (symbol ):
    ""
    c15 =fetch_klines (symbol ,"15m",300 )
    c1h =fetch_klines (symbol ,"1h",260 )
    c4h =fetch_klines (symbol ,"4h",260 )
    if not (c15 and c1h and c4h ):
        return {"action":"NO_SIGNAL","symbol":symbol ,
        "why":"کندل از هیچ منبعی نرسید — قانون ۱"}
    btc4h =btc1h =None 
    if symbol .upper ().replace ("USDT","").replace ("USD","")!="BTC":
        btc4h =fetch_klines ("BTCUSDT","4h",260 )
        btc1h =fetch_klines ("BTCUSDT","1h",260 )
    return analyze (symbol ,c4h ,c1h ,c15 ,btc4h =btc4h ,btc1h =btc1h )

def scalp_signal (symbol ):
    c1m =fetch_klines (symbol ,"1m",300 )
    if not c1m :
        return {"action":"NO_SIGNAL","symbol":symbol ,"mode":"scalp",
        "why":"کندل ۱ دقیقه نرسید — قانون ۱"}
    return scalp_decide (c1m ,symbol )

_RISK_KEYS ={
"max_leverage":("leverage_cap","max_leverage","maxLeverage",
"leverage_max","max_lev"),
"min_stop_pct":("min_stop_pct","min_stop_distance_pct","minStopPct",
"min_sl_pct"),
"max_positions":("max_positions","max_open_positions","maxPositions",
"max_concurrent"),
"fee_pct":("fee_pct","taker_fee","commission","fee_round_trip_pct"),
"cooldown_s":("cooldown_s","cooldown_seconds","trade_cooldown"),
"min_notional":("min_notional","min_order_usd","minNotional"),
"timeframes":("timeframes","intervals","supported_timeframes"),
"margin_mode":("margin_mode","marginMode","margin_type","marginType"),
}

def _dig (obj ,names ):
    ""
    for n in names :
        if isinstance (obj ,dict )and n in obj :
            return obj [n ]
        if hasattr (obj ,n ):
            v =getattr (obj ,n )
            if not callable (v ):
                return v 
    return None 

def audit_environment (risk =None ,dashboard =None ):
    ""
    src =[x for x in (risk ,dashboard )if x is not None ]
    found ={}
    for key ,names in _RISK_KEYS .items ():
        for s in src :
            v =_dig (s ,names )
            if v is not None :
                found [key ]=v 
                break 
    issues ,notes =[],[]
    RC =RISK_CONTRACT 

    mm =found .get ("margin_mode")
    if mm is not None and "cross"in str (mm ).lower ():
        issues .append ("مارجین داشبورد CROSS است — دستور صریح: فقط ایزوله؛ "
        "تا اصلاح، هیچ پوزیشنی باز نشود")
    elif mm is None :
        notes .append ("حالت مارجین داشبورد نامعلوم — باید ایزوله باشد (کراس ممنوع)")

    lev =found .get ("max_leverage")
    if lev is None :
        notes .append ("سقف اهرم داشبورد نامعلوم — بررسی دستی لازم است")
    elif lev <RC ["leverage"]["preferred_scalp_min"]:
        notes .append (
        f"سقف اهرم {lev}× زیر بازهٔ اسکلپ "
        f"({RC['leverage']['preferred_scalp_min']}–"
        f"{RC['leverage']['preferred_scalp_max']}×) — "
        "تداخلِ سیگنالی نیست: فقط سایز کوچک‌تر و لیکویید دورتر. "
        "استراتژی خودش را با همین سقف تنظیم می‌کند.")
        if lev <RC ["leverage"]["hard_floor"]:
            issues .append (f"سقف اهرم {lev}× زیر کف عملی "
            f"{RC['leverage']['hard_floor']}× — سایز به صفر "
            "میل می‌کند")

    ms =found .get ("min_stop_pct")
    if ms is None :
        notes .append ("کف فاصلهٔ استاپ داشبورد نامعلوم — مهم‌ترین عامل تداخل")
    elif ms >RC ["stop_pct"]["scalp_max"]:
        issues .append (
        f"کف استاپ داشبورد {ms}٪ بالاتر از سقف استاپ اسکلپ "
        f"{RC['stop_pct']['scalp_max']}٪ — همهٔ ستاپ‌های ۱ دقیقه در "
        "سکوت رد می‌شوند (وتوی خاموش)")
    elif ms >RC ["stop_pct"]["swing_max"]:
        issues .append (f"کف استاپ {ms}٪ بالاتر از سقف استاپ سوینگ "
        f"{RC['stop_pct']['swing_max']}٪ — صفر معامله")

    fee =found .get ("fee_pct")
    if fee is None :
        notes .append ("مدل کارمزد داشبورد نامعلوم — RR ممکن است خوش‌بین باشد")
    elif float (fee )<RC ["fees"]["round_trip_pct"]/3 :
        issues .append (f"کارمزد داشبورد {fee}٪ خیلی پایین‌تر از واقعیت "
        f"({RC['fees']['round_trip_pct']}٪ رفت‌وبرگشت) — "
        "نتیجهٔ پیپر خوش‌بین می‌شود")

    mp =found .get ("max_positions")
    if mp is not None and mp <RC ["concurrency"]["min_slots"]:
        issues .append (f"سقف پوزیشن هم‌زمان {mp} — اسکلپ چند نماد را "
        "هم‌زمان می‌بیند و صف می‌ماند")

    tfs =found .get ("timeframes")
    if tfs :
        have ={str (x ).lower ()for x in tfs }
        for mode ,need in RC ["needs_timeframes"].items ():
            missing =[t for t in need if t not in have ]
            if missing :
                issues .append (f"تایم‌فریم‌های لازم برای {mode} موجود نیست: "
                f"{'، '.join(missing)} → NO_SIGNAL دائمی")
    else :
        notes .append ("فهرست تایم‌فریم‌های داشبورد نامعلوم — ۴س/۱س/۱۵د و ۱د لازم است")

    mn =found .get ("min_notional")
    if mn is not None and mn >50 :
        notes .append (f"حداقل نوشنال {mn} — سایزهای کوچک اسکلپ رد می‌شوند")

    return {"contract":RC ,"detected":found ,
    "conflicts":issues ,"notes":notes ,
    "verdict":"تداخل جدی"if issues else 
    ("بدون تداخل قطعی؛ موارد نامعلوم را دستی چک کن"
    if notes else "سازگار")}

def set_environment (risk =None ,dashboard =None ):
    ""
    a =audit_environment (risk ,dashboard )
    mm =a ["detected"].get ("margin_mode")
    ENV ["margin_mode"]=str (mm ).lower ()if mm is not None else None 
    return a 

def print_audit (risk =None ,dashboard =None ):
    a =audit_environment (risk ,dashboard )
    print ("── ممیزی تداخل استراتژی ↔ داشبورد ──")
    print ("یافته‌ها:",json .dumps (a ["detected"],ensure_ascii =False )or "—")
    for x in a ["conflicts"]:
        print ("  ⛔",x )
    for x in a ["notes"]:
        print ("  ⚠️",x )
    print ("حکم:",a ["verdict"])
    return a 

def _selftest ():
    def mk (path ,tf_ms =900000 ,t0 =0 ):
        return [{"t":t0 +i *tf_ms ,"o":p ,"h":p *1.004 ,"l":p *0.996 ,
        "c":p }for i ,p in enumerate (path )]
    up =[100 +i *0.4 for i in range (230 )]
    dn =[200 -i *0.4 for i in range (230 )]
    c4 =c1 =mk (up )
    b4 ,b1 =mk (up ),mk (up )
    pull =up +[up [-1 ]-i *0.5 for i in range (1 ,16 )]
    c15 =mk (pull )
    c15 [-1 ]["l"],c15 [-1 ]["c"]=c15 [-1 ]["c"]*0.99 ,c15 [-1 ]["c"]*0.9905 
    EXPERIENCE .clear ()
    global _TOP_LIQ_OK 
    TOP_LIQUIDITY .clear ()
    TOP_LIQUIDITY .update ({"TESTUSDT","BTCUSDT"})
    _TOP_LIQ_OK =True 
    r =analyze ("TESTUSDT",c4 ,c1 ,c15 ,btc4h =b4 ,btc1h =b1 )
    assert r ["action"]=="LONG",r 
    assert r ["sl"]<r ["entry"]<r ["tp1"]
    assert r ["exp_used"]is False and 0 <=r ["quality"]<=100 

    assert "liq_map"in r and r ["liq_map"]is not None ,r 
    assert _liq_map (c1 [:20 ])is None 
    _lm_v =_liq_map ([{"t":i ,"o":100 ,"h":101 ,"l":99 ,"c":100 +(i %5 ),
    "v":1.0 +(i %3 )}for i in range (60 )])
    assert _lm_v and (_lm_v ["above"]or _lm_v ["below"]),_lm_v 
    assert _liq_line (_lm_v )and "لیکویید"in _liq_line (_lm_v )

    assert r ["margin_mode"]=="isolated"and r ["product"]=="futures",r 
    assert r ["sl_tp_mandatory"]and r ["stop_loss"]==r ["sl"]and r ["take_profit"]==r ["tp1"],r 

    ep =r ["exit_plan"]
    assert ep ["tp1_close_pct"]==33 
    fee_r_check =PARAMS ["fee_round_trip_pct"]/100 *r ["entry"]
    assert abs (ep ["stop_after_tp1"]-(r ["entry"]+fee_r_check ))<1e-6 ,ep 
    assert ep ["tp2"]>r ["tp1"]>r ["entry"],ep 
    assert abs ((ep ["tp2"]-r ["entry"])-2 *(r ["tp1"]-r ["entry"]))<1e-6 ,ep 
    banked =PARAMS ["rr_target"]*(ep ["tp1_close_pct"]/100 )
    r_risk =r ["entry"]-r ["sl"]
    rest_worst_r =fee_r_check /r_risk *(1 -ep ["tp1_close_pct"]/100 )
    assert banked +rest_worst_r >0 ,(banked ,rest_worst_r )
    assert ep ["tp2_trail_lock_pct"]==85 

    g0 =analyze ("TESTUSDT",c4 ,c1 ,c15 )
    assert g0 ["action"]=="NO_SIGNAL"and "بازار"in g0 ["why"],g0 

    g2 =analyze ("TESTUSDT",c4 ,c1 ,c15 ,btc4h =mk (dn ),btc1h =mk (dn ))
    assert g2 ["action"]=="NO_SIGNAL"and "وتوی مطلق"in g2 ["why"],g2 

    assert analyze ("BTCUSDT",c4 ,c1 ,c15 )["action"]=="LONG"

    TOP_LIQUIDITY .discard ("TESTUSDT")
    g3 =analyze ("TESTUSDT",c4 ,c1 ,c15 ,btc4h =b4 ,btc1h =b1 )
    assert g3 ["action"]=="NO_SIGNAL"and "نقدشوندگی"in g3 ["why"],g3 
    TOP_LIQUIDITY .add ("TESTUSDT")

    _TOP_LIQ_OK =False 
    g4 =analyze ("TESTUSDT",c4 ,c1 ,c15 ,btc4h =b4 ,btc1h =b1 )
    assert g4 ["action"]=="NO_SIGNAL"and "نقدشوندگی"in g4 ["why"],g4 
    assert analyze ("BTCUSDT",c4 ,c1 ,c15 )["action"]=="LONG","قطع همگام‌سازی نباید خود BTC را ببندد"
    _TOP_LIQ_OK =True 
    assert analyze ("TESTUSDT",c4 ,c1 ,c15 ,btc4h =b4 ,btc1h =b1 )["action"]=="LONG"

    EXPERIENCE ["TESTUSDT|LONG"]={"n":30 ,"win_pct":80.0 ,"mean_r":0.4 ,
    "thin":False }
    r2 =analyze ("TESTUSDT",c4 ,c1 ,c15 ,btc4h =b4 ,btc1h =b1 )
    assert r2 ["exp_used"]and r2 ["quality"]>r ["quality"],(r2 ,r )

    EXPERIENCE ["TESTUSDT|LONG"]={"n":30 ,"win_pct":20.0 ,"mean_r":-0.6 ,
    "thin":False }
    r3 =analyze ("TESTUSDT",c4 ,c1 ,c15 ,btc4h =b4 ,btc1h =b1 )
    assert r3 ["action"]=="NO_SIGNAL"and "تجربه"in r3 ["why"],r3 

    EXPERIENCE ["TESTUSDT|LONG"]={"n":3 ,"win_pct":0.0 ,"mean_r":-0.9 ,
    "thin":True }
    assert analyze ("TESTUSDT",c4 ,c1 ,c15 ,btc4h =b4 ,btc1h =b1 )["action"]=="LONG"
    EXPERIENCE .clear ()

    assert analyze ("TESTUSDT",c4 ,c1 ,mk ([100.0 ]*10 ),btc4h =b4 ,btc1h =b1 )["action"]=="NO_SIGNAL"
    mixed =analyze ("TESTUSDT",mk (dn ),c1 ,c15 ,btc4h =b4 ,btc1h =b1 )
    assert mixed ["action"]=="NO_SIGNAL"and "وتو"in mixed ["why"]

    up1 =[100 +i *0.05 for i in range (120 )]
    p1 =up1 +[up1 [-1 ]-i *0.03 for i in range (1 ,7 )]
    c1m =mk (p1 ,tf_ms =60000 ,t0 =int (time .time ()*1000 )-126 *60000 )
    c1m [-1 ]["l"],c1m [-1 ]["c"]=c1m [-1 ]["c"]*0.998 ,c1m [-1 ]["c"]*0.9982 
    c1m [-4 ]["l"]=c1m [-1 ]["c"]*0.993 
    s =scalp_decide (c1m ,"TESTUSDT")
    assert s ["action"]=="LONG",s 
    assert 15 <=s ["leverage"]<=39 ,s 
    assert 25.0 <=s ["margin_pct"]<=30.0 ,s 
    assert s ["entry_zone"][0 ]<s ["entry"]<s ["entry_zone"][1 ],s 
    assert s ["max_hold_min"]==45 ,s 
    assert s ["leverage"]<=int (50.0 /s ["stop_pct"]),s 
    assert s ["fee_r"]<SCALP ["max_fee_r"],s 
    assert "candle_evidence"in s and s ["candle_evidence"]["formula_version"]==CANDLE_GEOM_VERSION ,s 
    assert "liq_map"in s and s ["liq_map"]is not None ,s 
    assert "order_block"in s ,s 

    global order_block_zone 
    _real_ob =order_block_zone 

    def _fake_ob (cd ,direction ,**kw ):
        if direction =="SHORT":
            return {"lo":s ["entry"]*1.001 ,"hi":s ["entry"]*1.003 ,
            "role":"supply","reactions":2 ,"fresh":True ,
            "mitigated":False ,"dist_pct":0.1 }
        return None 
    order_block_zone =_fake_ob 
    try :
        blocked =scalp_decide (c1m ,"TESTUSDT")
        assert blocked ["action"]=="NO_SIGNAL"and "مسدود"in blocked ["why"],blocked 
    finally :
        order_block_zone =_real_ob 

    def _flat (n ,px =100.0 ,t0 =0 ,tf =60000 ):
        return [{"t":t0 +i *tf ,"o":px ,"h":px *1.001 ,"l":px *0.999 ,
        "c":px }for i in range (n )]
    ob_cd =_flat (40 )
    ob_o ,ob_c =100.0 ,99.5 
    ob_cd .append ({"t":40 *60000 ,"o":ob_o ,"h":ob_o *1.0005 ,
    "l":ob_c *0.999 ,"c":ob_c })
    disp_c =ob_c *1.02 
    ob_cd .append ({"t":41 *60000 ,"o":ob_c ,"h":disp_c *1.001 ,
    "l":ob_c *0.999 ,"c":disp_c })
    px =disp_c 
    for k in range (42 ,50 ):
        px *=1.001 
        ob_cd .append ({"t":k *60000 ,"o":px *0.999 ,"h":px *1.002 ,
        "l":px *0.998 ,"c":px })
    ob =order_block_zone (ob_cd ,"LONG",lookback =30 )
    assert ob and ob ["role"]=="demand"and ob ["fresh"],ob 
    lo ,hi =min (ob_o ,ob_c ),max (ob_o ,ob_c )
    assert abs (ob ["lo"]-lo )<1e-9 and abs (ob ["hi"]-hi )<1e-9 ,ob 

    mitigated_cd =ob_cd +[{"t":51 *60000 ,"o":lo *0.9995 ,"h":lo *0.9996 ,
    "l":lo *0.997 ,"c":lo *0.997 }]
    ob2 =order_block_zone (mitigated_cd ,"LONG",lookback =30 )
    assert ob2 and not ob2 ["fresh"]and ob2 ["mitigated"],ob2 

    geo_cd =_flat (15 )+[{"t":15 *60000 ,"o":100 ,"h":106 ,"l":99 ,"c":104 }]
    geo =candle_geometry (geo_cd )
    assert geo ["formula_version"]==CANDLE_GEOM_VERSION ,geo 
    assert abs (geo ["body_range"]-4 /7 )<0.01 ,geo 
    assert abs (geo ["ibs"]-5 /7 )<0.01 ,geo 
    assert 0 <=geo ["upper_wick_range"]<=1 and 0 <=geo ["lower_wick_range"]<=1 ,geo 

    _LAST .clear ()
    assert _repeat_gate ("XUSDT","LONG",1000000 ,"swing")is None 
    assert _repeat_gate ("XUSDT","LONG",1000000 ,"swing")is None 
    assert _repeat_gate ("XUSDT","LONG",1000000 +900000 ,"swing")
    assert _repeat_gate ("XUSDT","SHORT",1000000 +900000 ,"swing")is None 
    assert _repeat_gate ("XUSDT","LONG",1000000 +4 *3600000 ,"swing")is None 
    _LAST .clear ()

    assert suggest_leverage (3.0 ,100 ,mode ="scalp")==16 
    assert suggest_leverage (3.4 ,100 ,mode ="scalp")is None 
    assert suggest_leverage (0.7 ,90 ,mode ="scalp")<=int (50 /0.7 )

    assert suggest_leverage (0.5 ,40 ,mode ="scalp")==15 
    assert suggest_leverage (0.5 ,100 ,mode ="scalp")==39 
    assert suggest_leverage (0.5 ,70 ,mode ="scalp")==27 
    assert suggest_leverage (2.0 ,100 ,mode ="scalp")==25 
    assert suggest_leverage (0.5 ,100 ,mode ="swing")==39 
    assert margin_pct_for (40 )==25.0 and margin_pct_for (100 )==30.0 
    ep =_exit_plan ("LONG",100.0 ,101.5 ,1.0 ,PARAMS )
    assert ep ["trail_arm"]==100.15 
    assert _exit_plan ("SHORT",100.0 ,98.5 ,1.0 ,PARAMS )["trail_arm"]==99.85 

    a =audit_environment ({"max_leverage":20 ,"min_stop_pct":2.5 ,
    "timeframes":["15m","1h","4h"]})
    assert a ["conflicts"],a 
    assert any ("۱ دقیقه"in x or "1m"in x for x in a ["conflicts"]),a 

    a2 =audit_environment ({"max_leverage":20 ,"min_stop_pct":0.3 ,
    "timeframes":["1m","15m","1h","4h"],
    "fee_pct":0.15 })
    assert not a2 ["conflicts"],a2 

    _edge_bak =dict (EDGE )
    try :
        EDGE .clear ()
        EDGE .update ({"stale":False ,"rules":{"ibs":[
        {"condition":"لانگ همسو با بیت‌کوین","delta":0.2 ,
        "ci":[0.01 ,0.4 ],"n":231 },
        {"condition":"شرط ناشناخته","delta":9.9 ,
        "ci":[1 ,2 ],"n":50 }]}})
        pts ,lines ,rec =edge_boost ("ibs",{"dir":"LONG","btc_up":True })
        assert pts ==4 and len (lines )==1 ,(pts ,lines )
        assert rec ["untested"]==1 ,rec 
        pts2 ,_ ,_ =edge_boost ("ibs",{"dir":"SHORT","btc_up":True })
        assert pts2 ==0 ,pts2 
        EDGE ["rules"]["ibs"][0 ]["delta"]=5.0 
        pts3 ,_ ,_ =edge_boost ("ibs",{"dir":"LONG","btc_up":True })
        assert pts3 ==EDGE_CAP ,pts3 
        EDGE ["stale"]=True 
        assert edge_boost ("ibs",{"dir":"LONG","btc_up":True })[0 ]==0 
    finally :
        EDGE .clear ()
        EDGE .update (_edge_bak )
    print ("✓ خودآزمایی استراتژی ۲.۸ گذشت — سوینگ، نردبان خروج، تجربه، اسکلپ، نقشهٔ نقدینگی، قفسهٔ لبه، ممیزی")

try :
    from strategy_base import BaseStrategy 
except Exception :
    try :
        from base_strategy import BaseStrategy 
    except Exception :
        class BaseStrategy :
            pass 

class Liam9Strategy (BaseStrategy ):
    ""

    meta ={
    "name":"لیام تریدر ۹ — IBS + پولبک + تجربه",
    "id":"liam9-ibs-pullback",
    "version":PARAMS ["version"],
    "author":"لیام تریدر ۹",
    "timeframes":["4h","1h","15m"],
    "market":"crypto-futures",
    "risk_contract":RISK_CONTRACT ,
    "description":("سلسله‌مراتب روند ۴س/۱س → پولبک ۱۵د → تأیید IBS → "
    "استاپ بیرون نویز → دروازهٔ کارمزد → لایهٔ تجربه "
    "(۸۶.۹٪ برد در دفتر ما)؛ NO_SIGNAL تصمیم معتبر است"),
    }

    def __init__ (self ,*a ,**kw ):
        try :
            super ().__init__ (*a ,**kw )
        except Exception :
            pass 
        sync_all ()

        if kw .get ("risk")is not None or kw .get ("dashboard")is not None :
            set_environment (kw .get ("risk"),kw .get ("dashboard"))
        self .meta ["version"]=PARAMS ["version"]

    def generate_signal (self ,symbol ,c4h =None ,c1h =None ,c15 =None ,**kw ):
        if c4h and c1h and c15 :
            return analyze (symbol ,c4h ,c1h ,c15 ,
            btc4h =kw .get ("btc4h"),btc1h =kw .get ("btc1h"))
        return signal (symbol )

    def on_bar (self ,symbol ,candles =None ,**kw ):
        if candles and len (candles )>=60 :
            c1h =fetch_klines (symbol ,"1h",260 )
            c4h =fetch_klines (symbol ,"4h",260 )
            if c1h and c4h :
                btc4h =btc1h =None 
                if symbol .upper ().replace ("USDT","").replace ("USD","")!="BTC":
                    btc4h =fetch_klines ("BTCUSDT","4h",260 )
                    btc1h =fetch_klines ("BTCUSDT","1h",260 )
                return analyze (symbol ,c4h ,c1h ,candles ,
                btc4h =btc4h ,btc1h =btc1h )
        return self .generate_signal (symbol ,**kw )

    def run (self ,symbol ,**kw ):
        return self .generate_signal (symbol ,**kw )

    def audit (self ,risk =None ,dashboard =None ):
        return audit_environment (risk ,dashboard )

class Liam9ScalpStrategy (BaseStrategy ):
    ""

    meta ={
    "name":"لیام تریدر ۹ — اسکلپ ۱ دقیقه",
    "id":"liam9-scalp-1m",
    "version":PARAMS ["version"],
    "author":"لیام تریدر ۹",
    "timeframes":["1m"],
    "market":"crypto-futures",
    "risk_contract":RISK_CONTRACT ,
    "description":("IBS + پولبک روی ۱د با سشن و کندل قبلی؛ اهرم "
    "۴۵–۹۰ فقط با محافظ فاصلهٔ لیکویید و دروازهٔ "
    "کارمزد — پیپر"),
    }

    def __init__ (self ,*a ,**kw ):
        try :
            super ().__init__ (*a ,**kw )
        except Exception :
            pass 
        sync_all ()

    def generate_signal (self ,symbol ,candles =None ,**kw ):
        if candles and len (candles )>=90 :
            return scalp_decide (candles ,symbol )
        return scalp_signal (symbol )

    def on_bar (self ,symbol ,candles =None ,**kw ):
        return self .generate_signal (symbol ,candles =candles ,**kw )

    def run (self ,symbol ,**kw ):
        return self .generate_signal (symbol ,**kw )

    def audit (self ,risk =None ,dashboard =None ):
        return audit_environment (risk ,dashboard )

if __name__ =="__main__":
    import sys 
    if "--selftest"in sys .argv :
        _selftest ()
    elif "--audit"in sys .argv :
        print_audit ()
        print ("\nبرای ممیزی واقعی، آبجکت ریسک داشبورد را بده:")
        print ("  liam9_strategy.print_audit(risk=dashboard.risk_engine)")
    else :
        scalp_mode ="--scalp"in sys .argv 
        args =[a for a in sys .argv [1 :]if not a .startswith ("--")]
        sym =args [0 ]if args else "BTCUSDT"
        v =sync_all ()
        print (f"پارامترها: {v['params'] or 'پیش‌فرض (اتصال نشد)'} · "
        f"کارنامهٔ تجربه: {v['experience_pairs']} جفت")
        out =scalp_signal (sym )if scalp_mode else signal (sym )
        print (json .dumps (out ,ensure_ascii =False ,indent =1 ))
