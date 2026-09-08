#!/usr/bin/env python3
"""لیام تریدر ۹ — موتور شورت، نسخهٔ تک‌فایلِ داشبورد.

**این فایل تولید می‌شود؛ دستی ویرایشش نکن.**
    python3 -m hamid.build_short_dashboard

کلِ فایل را در جعبهٔ «استراتژی» داشبورد بگذار. فقط کتابخانهٔ
استاندارد پایتون لازم دارد.

ماژول‌های زیر عیناً از ریپو آمده‌اند و این‌جا به‌عنوان ماژولِ واقعی
نصب می‌شوند — پس تعریفِ ساختار/اردر بلاک/کارمزد **دقیقاً** همان
چیزی است که بک‌تست با آن سنجیده شده:
    hamid.structure · hamid.orderblocks · hamid.fees

مرز: این موتور هنوز مجوز تولید ندارد (PRODUCTION_APPROVED=False).
خروجی‌اش پیشنهادِ سنجش‌پذیر است، نه سیگنالِ تأییدشده.
"""
import sys as _sys, types as _types

_BUNDLED = {}
_BUNDLED['hamid.structure'] = r'''

""
from dataclasses import dataclass ,field 
from statistics import fmean 

def atr (cd ,n =14 ):
    ""
    if len (cd )<2 :
        return 0.0 
    trs =[]
    for i in range (1 ,len (cd )):
        h ,l ,pc =cd [i ]["h"],cd [i ]["l"],cd [i -1 ]["c"]
        trs .append (max (h -l ,abs (h -pc ),abs (l -pc )))
    tail =trs [-n :]if len (trs )>=n else trs 
    return fmean (tail )if tail else 0.0 

@dataclass 
class Swing :
    i :int 
    t :int 
    price :float 
    kind :str 

def swings (cd ,left =2 ,right =2 ):
    ""
    out =[]
    for i in range (left ,len (cd )-right ):
        h ,l =cd [i ]["h"],cd [i ]["l"]
        if all (cd [j ]["h"]<=h for j in range (i -left ,i ))and all (cd [j ]["h"]<h for j in range (i +1 ,i +right +1 )):
            out .append (Swing (i ,cd [i ]["t"],h ,"high"))
        if all (cd [j ]["l"]>=l for j in range (i -left ,i ))and all (cd [j ]["l"]>l for j in range (i +1 ,i +right +1 )):
            out .append (Swing (i ,cd [i ]["t"],l ,"low"))
    return out 

@dataclass 
class Level :
    price :float 
    kind :str 
    born_i :int 
    born_t :int 
    touches :int =0 
    reactions :int =0 
    flipped :bool =False 
    last_touch_i :int =-1 
    touch_bars :list =field (default_factory =list )

    @property 
    def valid (self ):
        return self .reactions >=2 

def _reacted (cd ,i ,price ,tol ,bars =6 ,mult =3.0 ):
    ""
    end =min (len (cd ),i +bars +1 )
    if end <=i +1 or i <1 :
        return False 
    prev =cd [i -1 ]["c"]
    if abs (prev -price )<tol :
        return False 
    side =1 if prev >price else -1 
    after =cd [i +1 :end ]
    if side >0 and min (c ["c"]for c in after )<price -tol :
        return False 
    if side <0 and max (c ["c"]for c in after )>price +tol :
        return False 
    away =(max (c ["c"]for c in after )-price )if side >0 else (price -min (c ["c"]for c in after ))
    return away >=mult *tol 

def _tally (cd ,price ,tol ,born_i ):
    ""
    touches =reactions =0 
    last =-99 
    flipped =False 
    for i in range (born_i +3 ,len (cd )):
        c =cd [i ]
        if not (c ["l"]-tol <=price <=c ["h"]+tol ):
            continue 
        if i -last <3 :
            continue 
        touches +=1 
        last =i 
        if _reacted (cd ,i ,price ,tol ):
            reactions +=1 
            if cd [i -1 ]["c"]>price :
                flipped =True 
    return touches ,reactions ,flipped 

def _noise_floor (cd ,tol ,samples =28 ):
    ""
    lo =min (c ["l"]for c in cd )
    hi =max (c ["h"]for c in cd )
    if hi <=lo :
        return 0.0 
    rates =[]
    n =len (cd )
    for k in range (samples ):
        price =lo +(hi -lo )*((k +0.5 )/samples )
        born =int (n *0.1 )+(k *(n //2 ))//max (samples ,1 )
        born =min (born ,n -12 )
        if born <0 :
            continue 
        _ ,r ,_ =_tally (cd ,price ,tol ,born )
        rates .append (r /max (1 ,n -born )*100 )
    if not rates :
        return 0.0 
    rates .sort ()
    return rates [int (len (rates )*0.80 )]

def levels (cd ,tol =None ,min_reactions =2 ,keep =8 ):
    ""
    if len (cd )<20 :
        return []
    tol =tol if tol is not None else max (atr (cd )*0.25 ,cd [-1 ]["c"]*0.0005 )
    floor =_noise_floor (cd ,tol )
    n =len (cd )
    out =[]
    for s in swings (cd ):
        t ,r ,flip =_tally (cd ,s .price ,tol ,s .i )
        rate =r /max (1 ,n -s .i )*100 
        if r <min_reactions or rate <=floor :
            continue 
        lv =Level (price =s .price ,kind =s .kind ,born_i =s .i ,born_t =s .t ,
        touches =t ,reactions =r )

        lv .flipped =flip if s .kind =="high"else not flip 
        out .append (lv )

    out .sort (key =lambda l :(-l .reactions ,-l .touches ))

    merged =[]
    for l in out :
        if not any (abs (l .price /m .price -1 )<0.0015 for m in merged ):
            merged .append (l )
    return merged [:keep ]

def trend (cd ,lookback =60 ):
    ""
    sw =[s for s in swings (cd )if s .i >=len (cd )-lookback ]
    hi =[s .price for s in sw if s .kind =="high"][-3 :]
    lo =[s .price for s in sw if s .kind =="low"][-3 :]
    span =cd [-lookback :]if len (cd )>lookback else cd 
    if len (span )<5 :
        return "range"
    drift =span [-1 ]["c"]/span [0 ]["c"]-1 
    a =atr (span )
    strong =abs (span [-1 ]["c"]-span [0 ]["c"])>3 *a if a else abs (drift )>0.03 

    if len (hi )>=2 and len (lo )>=2 :
        up =hi [-1 ]>hi [0 ]and lo [-1 ]>lo [0 ]
        down =hi [-1 ]<hi [0 ]and lo [-1 ]<lo [0 ]
        return "up"if up else "down"if down else "range"

    if len (hi )>=2 and strong :
        return "up"if hi [-1 ]>hi [0 ]and drift >0 else "down"if hi [-1 ]<hi [0 ]and drift <0 else "range"
    if len (lo )>=2 and strong :
        return "up"if lo [-1 ]>lo [0 ]and drift >0 else "down"if lo [-1 ]<lo [0 ]and drift <0 else "range"
    return "range"

def _fit (points ):
    ""
    if len (points )<2 :
        return None 
    xs =[p [0 ]for p in points ]
    ys =[p [1 ]for p in points ]
    mx ,my =fmean (xs ),fmean (ys )
    den =sum ((x -mx )**2 for x in xs )
    if den ==0 :
        return None 
    m =sum ((x -mx )*(y -my )for x ,y in zip (xs ,ys ))/den 
    return m ,my -m *mx 

@dataclass 
class Channel :
    upper :tuple 
    lower :tuple 
    position :float 
    width :float 
    slope :str 

    def at (self ,i ):
        return self .upper [0 ]*i +self .upper [1 ],self .lower [0 ]*i +self .lower [1 ]

    def mid (self ,i ):
        u ,l =self .at (i )
        return (u +l )/2 

def channel (cd ,lookback =90 ):
    ""
    start =max (0 ,len (cd )-lookback )
    sw =[s for s in swings (cd )if s .i >=start ]
    hi =[(s .i ,s .price )for s in sw if s .kind =="high"]
    lo =[(s .i ,s .price )for s in sw if s .kind =="low"]
    if len (hi )<2 or len (lo )<2 :
        return None 
    up ,dn =_fit (hi ),_fit (lo )
    if not up or not dn :
        return None 
    i =len (cd )-1 
    u ,l =up [0 ]*i +up [1 ],dn [0 ]*i +dn [1 ]
    if u <=l :
        return None 
    price =cd [-1 ]["c"]
    avg =(up [0 ]+dn [0 ])/2 
    ref =cd [-1 ]["c"]/max (len (cd ),1 )
    slope ="up"if avg >ref *0.02 else "down"if avg <-ref *0.02 else "flat"
    return Channel (up ,dn ,(price -l )/(u -l ),u -l ,slope )

def reentry (cd ,ch ,settle =3 ):
    ""
    if ch is None or len (cd )<settle +4 :
        return None 
    n =len (cd )
    inside =[]
    for i in range (n -settle -6 ,n ):
        if i <0 :
            continue 
        u ,l =ch .at (i )
        inside .append ((i ,l <=cd [i ]["c"]<=u ,cd [i ]["c"]>u ,cd [i ]["c"]<l ))
    if len (inside )<settle +2 :
        return None 
    tail =inside [-settle :]
    if not all (x [1 ]for x in tail ):
        return None 
    before =inside [:-settle ]
    broke_up =any (x [2 ]for x in before )
    broke_dn =any (x [3 ]for x in before )
    if not (broke_up or broke_dn ):
        return None 
    i =n -1 
    u ,l =ch .at (i )
    return {
    "side":"from_above"if broke_up else "from_below",
    "target1":ch .mid (i ),
    "target2":l if broke_up else u ,
    "note":"بعد از تثبیت در کانال: اول میدلاین، بعد سمت مقابل",
    }

if __name__ =="__main__":
    import sys 
    from pathlib import Path 
    sys .path .insert (0 ,str (Path (__file__ ).resolve ().parent .parent ))
    from hamid .selfcheck import main 
    main ()

@dataclass 
class Trendline :
    slope :float 
    intercept :float 
    kind :str 
    touches :int 
    first_i :int 
    last_i :int 
    broken :bool =False 
    t0 :int =0 
    step_ms :int =0 

    def at (self ,i ):
        return self .slope *i +self .intercept 

    def at_t (self ,t ,cd =None ):
        ""
        step =self .step_ms or ((cd [1 ]["t"]-cd [0 ]["t"])
        if cd and len (cd )>1 else 0 )
        if not step :
            return None 
        return self .at ((t -self .t0 )/step )

def trendline (cd ,lookback =120 ,min_touches =3 ,tol_mult =0.6 ):
    ""
    start =max (0 ,len (cd )-lookback )
    win =cd [start :]
    if len (win )<20 :
        return None 
    tol =atr (win )*tol_mult 
    if not tol or tol <=0 :
        return None 
    sw =[s for s in swings (win )if s .i <len (win )]
    best =None 
    for kind ,want in (("support","low"),("resistance","high")):
        pts =[(s .i ,s .price )for s in sw if s .kind ==want ]
        if len (pts )<2 :
            continue 

        for a in range (len (pts )):
            for b in range (a +1 ,len (pts )):
                (x1 ,y1 ),(x2 ,y2 )=pts [a ],pts [b ]
                if x2 ==x1 :
                    continue 
                m =(y2 -y1 )/(x2 -x1 )
                c =y1 -m *x1 

                if abs (m )*len (win )<tol :
                    continue 

                if (kind =="support")!=(m >0 ):
                    continue 

                if abs (x2 -x1 )<len (win )*0.35 :
                    continue 
                if abs (m )*len (win )<tol *3 :
                    continue 
                touches ,bad ,last_touch =0 ,0 ,-99 
                for i ,k in enumerate (win ):
                    line =m *i +c 
                    if kind =="support":

                        if min (k ["o"],k ["c"])<line -tol :
                            bad +=1 
                            continue 
                        near =abs (k ["l"]-line )<=tol 
                    else :
                        if max (k ["o"],k ["c"])>line +tol :
                            bad +=1 
                            continue 
                        near =abs (k ["h"]-line )<=tol 

                    if near and i -last_touch >3 :
                        touches +=1 
                        last_touch =i 
                if touches <min_touches :
                    continue 

                broken =bad >max (2 ,len (win )//40 )
                cand =Trendline (m ,c ,kind ,touches ,min (x1 ,x2 ),max (x1 ,x2 ),
                broken ,t0 =win [0 ]["t"],
                step_ms =(win [1 ]["t"]-win [0 ]["t"]
                if len (win )>1 else 0 ))
                score =(0 if broken else 1 ,touches ,max (x1 ,x2 ))
                if best is None or score >best [0 ]:
                    best =(score ,cand )
    return best [1 ]if best else None 

'''

_BUNDLED['hamid.orderblocks'] = r'''
""
import sys 
from pathlib import Path 

HERE =Path (__file__ ).resolve ().parent 
sys .path .insert (0 ,str (HERE .parent ))

from hamid .structure import atr 

MAX_BACK =300 
IMP_ATR =4.5 
IMP_BARS =12 

def _body (c ):
    return abs (c ["c"]-c ["o"])

def _wicks (c ):
    return (c ["h"]-c ["l"])-_body (c )

def hamid_candle (c ):
    ""
    return _body (c )>_wicks (c )and _body (c )>0 

def _full_atr (cd ):
    ""
    if len (cd )<2 :
        return 0.0 
    trs =[max (cd [i ]["h"]-cd [i ]["l"],abs (cd [i ]["h"]-cd [i -1 ]["c"]),
    abs (cd [i ]["l"]-cd [i -1 ]["c"]))for i in range (1 ,len (cd ))]
    return sum (trs )/len (trs )

def _impulses (cd ):
    ""
    a =_full_atr (cd )
    if not a :
        return []
    out =[]
    n =len (cd )
    last_dn ,last_up =-9 ,-9 
    for i in range (max (3 ,n -MAX_BACK ),n -2 ):
        win =cd [max (0 ,i -3 ):i +2 ]
        end =min (n ,i +IMP_BARS +1 )
        if i -last_dn >=4 and cd [i ]["h"]>=max (x ["h"]for x in win ):

            j0 =max (range (i ,min (i +5 ,n )),key =lambda x :cd [x ]["h"])
            e2 =min (n ,j0 +IMP_BARS +1 )
            drop =cd [j0 ]["c"]-min ((x ["c"]for x in cd [j0 +1 :e2 ]),
            default =cd [j0 ]["c"])
            if drop >=IMP_ATR *a :
                out .append ({"i":j0 ,"dir":"down","mag_atr":round (drop /a ,2 )})
                last_dn =j0 
                continue 
        if i -last_up >=4 and cd [i ]["l"]<=min (x ["l"]for x in win ):
            j0 =min (range (i ,min (i +5 ,n )),key =lambda x :cd [x ]["l"])
            e2 =min (n ,j0 +IMP_BARS +1 )
            rise =max ((x ["c"]for x in cd [j0 +1 :e2 ]),
            default =cd [j0 ]["c"])-cd [j0 ]["c"]
            if rise >=IMP_ATR *a :
                out .append ({"i":j0 ,"dir":"up","mag_atr":round (rise /a ,2 )})
                last_up =j0 
    return out 

def _ob_candle (cd ,start_i ,lookback =6 ):
    ""
    for j in range (start_i ,max (-1 ,start_i -lookback ),-1 ):
        if hamid_candle (cd [j ]):
            return j 
    return None 

def _score_box (cd ,lo ,hi ,born_i ,role =None ):
    ""
    a =atr (cd )
    tol =max (a *0.25 ,(hi -lo )*0.25 ,cd [-1 ]["c"]*0.0005 )
    touches =reactions =hunts =0 
    broken_at =None 
    last =-99 
    visit_open =False 
    visit_hunted =False 
    side =0 
    n =len (cd )
    for i in range (born_i +3 ,n ):
        c =cd [i ]
        if c ["l"]>hi +tol or c ["h"]<lo -tol :
            visit_open =False 
            continue 
        prev =cd [i -1 ]["c"]
        new_visit =not (lo <prev <hi )and (i -last >=3 or not visit_open )
        if not new_visit :

            if visit_open and not visit_hunted :
                deep =(c ["l"]<(lo +tol )if side >0 else c ["h"]>(hi -tol ))
                out_close =(c ["c"]>hi if side >0 else c ["c"]<lo )
                if deep and out_close :
                    hunts +=1 
                    visit_hunted =True 
            continue 
        side =1 if prev >=hi else -1 

        if role =="down"and side !=-1 :
            continue 
        if role =="up"and side !=1 :
            continue 
        touches +=1 
        last =i 
        visit_open ,visit_hunted =True ,False 
        edge =hi if side >0 else lo 
        far =lo if side >0 else hi 
        after =cd [i +1 :min (n ,i +7 )]
        if not after :
            continue 
        closed_through =(min (x ["c"]for x in after )<far -tol if side >0 
        else max (x ["c"]for x in after )>far +tol )
        if closed_through :
            if broken_at is None :
                broken_at =i 
            visit_open =False 
            continue 

        away =(max (x ["c"]for x in after )-edge )if side >0 else (edge -min (x ["c"]for x in after ))
        stay_out =sum (1 for x in after 
        if (x ["c"]>hi if side >0 else x ["c"]<lo ))>=len (after )//2 
        if away >=max (3 *tol ,2.5 *a )and stay_out :
            reactions +=1 
            if (c ["l"]<far +tol if side >0 else c ["h"]>far -tol ):
                hunts +=1 
                visit_hunted =True 
    return touches ,reactions ,hunts ,broken_at 

def _noise_floor (cd ,height ,born_i ,samples =20 ):
    ""
    lo_all =min (c ["l"]for c in cd )
    hi_all =max (c ["h"]for c in cd )
    if hi_all -lo_all <=height :
        return 0.0 
    n =len (cd )
    born =min (born_i ,n -15 )
    rates =[]
    for k in range (samples ):
        base =lo_all +(hi_all -lo_all -height )*((k +0.5 )/samples )
        _ ,r ,_ ,_ =_score_box (cd ,base ,base +height ,born )
        rates .append (r /max (1 ,n -born )*100 )
    rates .sort ()
    return rates [int (len (rates )*0.8 )]

def find (cd ,tf ="1h",min_reactions =2 ):
    ""
    if len (cd )<60 :
        return []
    px =cd [-1 ]["c"]
    boxes =[]
    for imp in _impulses (cd ):
        j =_ob_candle (cd ,imp ["i"])
        if j is None :
            continue 
        lo ,hi =cd [j ]["l"],cd [j ]["h"]
        if hi <=lo :
            continue 
        touches ,reactions ,hunts ,broken_at =_score_box (cd ,lo ,hi ,j ,role =imp ["dir"])
        boxes .append ({"tf":tf ,"i":j ,"t":cd [j ]["t"],"low":round (lo ,10 ),
        "high":round (hi ,10 ),"move":imp ["dir"],
        "mag_atr":imp ["mag_atr"],"touches":touches ,
        "reactions":reactions ,"hunts":hunts ,
        "broken":broken_at is not None ,
        "fresh":touches ==0 and broken_at is None ,
        "age":len (cd )-1 -j ,
        "inside_now":lo <=px <=hi })

    boxes .sort (key =lambda b :-b ["reactions"])
    merged =[]
    for b in boxes :
        dup =any (not (b ["high"]<m ["low"]or b ["low"]>m ["high"])
        and abs (b ["i"]-m ["i"])<6 for m in merged )
        if not dup :
            merged .append (b )

    keep =[]
    for b in merged :
        if b ["fresh"]and b ["age"]<=MAX_BACK :
            keep .append (b )
            continue 
        if b ["reactions"]<min_reactions or b ["broken"]:
            continue 
        keep .append (b )
    keep .sort (key =lambda b :(-b ["reactions"],b ["age"]))
    return keep [:8 ]

def near (cd ,tf ="1h"):
    ""
    px =cd [-1 ]["c"]
    a =atr (cd )or px *0.005 
    best_in ,best_near =None ,None 
    for b in find (cd ,tf =tf ):
        if b ["low"]<=px <=b ["high"]:
            if best_in is None :
                best_in =b 
        elif min (abs (px -b ["low"]),abs (px -b ["high"]))<=2 *a :
            if best_near is None :
                best_near =b 
    return best_in ,best_near 

def note_fa (b ,where ="داخل"):
    ""
    tag ="تازه (هنوز لمس‌نشده)"if b ["fresh"]else f"{b['reactions']} واکنش"+(f"، {b['hunts']} هانت"if b ["hunts"]else "")
    return (f"اردر بلاک {b['tf']} ({where}، {tag}"
    f"{'، مصرف‌شده' if b['broken'] else ''})")

'''

_BUNDLED['hamid.fees'] = r'''
""
import json 
from pathlib import Path 

HERE =Path (__file__ ).resolve ().parent 
ROOT =HERE .parent .parent .parent 
CFG =ROOT /"config"/"fees.json"

DEFAULTS ={
"exchange":"bitunix",
"futures_maker_pct":0.020 ,
"futures_taker_pct":0.060 ,
"slippage_pct_per_leg":0.015 ,
"zero_fee_symbols":[],
"zero_fee_status":"UNVERIFIED",
"us_market_hours_symbols":[],
"verified_at":"2026-08-16",
"sources":[
"https://tradersunion.com/brokers/crypto/view/bitunix/fees/",
"https://www.bitunix.com/hub/blog/bitunix-features/bitunix-fees-spot-futures-vip-trading-discounts",
"https://www.mexc.com/news/1135898",
],
}

def config ():
    cfg =dict (DEFAULTS )
    try :
        cfg .update (json .loads (CFG .read_text ()))
    except Exception :
        pass 
    return cfg 

def round_trip_pct (symbol =None ,entry_maker =False ,exit_maker =False ,
with_slippage =True ):
    ""
    c =config ()
    if symbol and symbol in (c .get ("zero_fee_symbols")or [])and c .get ("zero_fee_status")=="VERIFIED":
        fee =0.0 
    else :
        fee =((c ["futures_maker_pct"]if entry_maker else c ["futures_taker_pct"])
        +(c ["futures_maker_pct"]if exit_maker else c ["futures_taker_pct"]))
    if with_slippage :
        fee +=2 *c ["slippage_pct_per_leg"]
    return round (fee ,4 )

def cost_in_r (entry ,sl ,symbol =None ,entry_maker =False ,exit_maker =False ):
    ""
    if not entry or not sl or entry ==sl :
        return None 
    risk_pct =abs (entry -sl )/entry *100 
    return round (round_trip_pct (symbol ,entry_maker ,exit_maker )/risk_pct ,3 )

def apply_net (rows ):
    ""
    for r in rows :
        if r .get ("_R_net_stored")is not None :
            continue 
        r ["_R_net_stored"]=r .get ("R_net")
        fr =None 
        try :
            fr =cost_in_r (r .get ("entry"),r .get ("sl"),r .get ("sym"))
        except Exception :
            fr =None 
        r ["_fee_r"]=fr if fr is not None else r .get ("fee_r")
        if fr is not None and r .get ("R")is not None :
            r ["R_net"]=round (r ["R"]-fr ,4 )
    return rows 

def net_rr (entry ,sl ,tp ,symbol =None ,entry_maker =False ,exit_maker =False ):
    ""
    if not entry or not sl or not tp or entry ==sl :
        return None 
    gross =abs (tp -entry )/abs (entry -sl )
    fee_r =cost_in_r (entry ,sl ,symbol ,entry_maker ,exit_maker )
    return None if fee_r is None else round (gross -fee_r ,3 )

def gate (entry ,sl ,tp ,symbol =None ,min_net_rr =1.8 ,
entry_maker =False ,exit_maker =False ):
    ""
    fee_r =cost_in_r (entry ,sl ,symbol ,entry_maker ,exit_maker )
    nrr =net_rr (entry ,sl ,tp ,symbol ,entry_maker ,exit_maker )
    if fee_r is None or nrr is None :
        return dict (ok =False ,reason ="ورودی ناقص (entry/sl/tp)",fee_r =None ,
        net_rr =None )
    ok =nrr >=min_net_rr 
    kind =("میکر/میکر"if entry_maker and exit_maker else 
    "تیکر/تیکر"if not entry_maker and not exit_maker else "ترکیبی")
    reason =(f"کارمزد {kind} رفت‌وبرگشت = {fee_r}R؛ RR خالص {nrr} "
    +("≥"if ok else "<")+f" حد {min_net_rr}"
    +(""if ok else " — پوزیشن باز نمی‌شود؛ سود اسمی را کارمزد می‌خورد"))
    return dict (ok =ok ,fee_r =fee_r ,net_rr =nrr ,reason =reason )

if __name__ =="__main__":
    import sys 
    e ,s_ ,t =(float (x )for x in sys .argv [1 :4 ])
    print (json .dumps (gate (e ,s_ ,t ,*(sys .argv [4 :5 ]or [None ])),
    ensure_ascii =False ,indent =1 ))

'''


def _install_bundled():
    pkgs = {}
    for _name in list(_BUNDLED) :
        _top = _name.split('.')[0]
        if _top not in _sys.modules:
            _p = _types.ModuleType(_top)
            _p.__path__ = []
            _sys.modules[_top] = _p
        pkgs[_top] = _sys.modules[_top]
    for _name, _src in _BUNDLED.items():
        if _name in _sys.modules:
            continue
        _m = _types.ModuleType(_name)
        _m.__file__ = '<bundled:' + _name + '>'
        _sys.modules[_name] = _m
        exec(compile(_src, _m.__file__, 'exec'), _m.__dict__)
        _top, _, _leaf = _name.rpartition('.')
        if _top:
            setattr(pkgs[_top], _leaf, _m)


_install_bundled()



""
import json 
import sys 
import time 
from pathlib import Path 

HERE =Path (__file__ ).resolve ().parent 
sys .path .insert (0 ,str (HERE ))
ROOT =HERE .parents [1 ]

STRATEGY_ID ="liam9_short"
STRATEGY_VERSION ="v2.0"
PANEL_NAME ="لیام تریدر ۹"

VALIDATION_STATUS ="BACKTESTED_UNDECIDED_N208"
PRODUCTION_APPROVED =False 

P ={

"min_stop_pct":1.00 ,
"max_stop_pct":3.30 ,

"rr_target":2.00 ,
"min_net_rr":1.50 ,

"min_chan_pos":0.70 ,

"ob_buffer":0.25 ,

"max_leverage":20 ,
"liq_guard":50.0 ,
"risk_pct":2.0 ,
"max_hold_bars":120 ,
"stale_max_s":300 ,
"min_bars":60 ,

"dom_max_age_min":45 ,
}

DOM ={"stance":None ,"why":None ,"generated":0 ,"source":None }

DOM_VETO_SHORT =("LONG_ALT","LONG_ALT_STRONG")
DOM_FAVORS_SHORT =("SHORT_ALT","SHORT_ALT_STRONG")

def sync_dominance (raw_url =None ,timeout =10 ):
    ""
    import urllib .request 
    url =raw_url or ("https://raw.githubusercontent.com/AuraLiam/"
    "Liam-Trader-9/main/signals/dominance.json")
    try :
        req =urllib .request .Request (url ,headers ={"User-Agent":"liam9-short"})
        with urllib .request .urlopen (req ,timeout =timeout )as r :
            d =json .load (r )
    except Exception as e :
        DOM ["source"]=f"خطا: {type(e).__name__}"
        return False 
    return load_dominance (d )

def load_dominance (dom_json ):
    ""
    st_ =((dom_json or {}).get ("stables")or {}).get ("alt_stance")or {}
    if not st_ .get ("stance"):
        DOM ["source"]="کلید stables.alt_stance روی dominance.json نیست"
        return False 
    DOM .update ({"stance":st_ ["stance"],"why":st_ .get ("why"),
    "generated":dom_json .get ("generated")or 0 ,
    "cause":st_ .get ("cause"),
    "disagrees_with_naive":st_ .get ("disagrees_with_naive"),
    "source":"signals/dominance.json"})
    return True 

def dominance_gate (symbol ,now_ms ,stance =None ,generated =None ):
    ""
    s =stance or DOM .get ("stance")
    gen =generated if generated is not None else DOM .get ("generated")or 0 
    if not s :
        return False ,None ,("بسترِ دامیننس نرسیده — قانون ۰۱ بند ۳: "
        f"({DOM.get('source') or 'همگام نشده'})")
    if gen :
        age_min =(now_ms -gen )/60_000.0 
        if age_min >P ["dom_max_age_min"]:
            return False ,s ,(f"عکس‌فوریِ دامیننس {age_min:.0f} دقیقه کهنه "
            f"(سقف {P['dom_max_age_min']}) — حدس ممنوع")
    if s in DOM_VETO_SHORT :
        return False ,s ,(f"بسترِ دامیننس «{s}» است — پول از استیبل بیرون "
        "آمده و به آلت رفته؛ شورت خلافِ اولویتِ اولِ حمید")
    if s in DOM_FAVORS_SHORT :
        return True ,s ,f"بسترِ دامیننس «{s}» — هم‌جهت با شورت"
    return True ,s ,f"بسترِ دامیننس «{s}» — جهت نمی‌دهد، دروازه‌های بعدی تصمیم می‌گیرند"

def _f (x ):
    try :
        return float (x )
    except (TypeError ,ValueError ):
        return None 

def _ohlc (c ):
    ""
    if isinstance (c ,dict ):
        vals =[c .get (k )for k in ("o","h","l","c","v")]
        if vals [0 ]is None :
            vals =[c .get (k )for k in ("open","high","low","close","volume")]
        return tuple (_f (v )for v in vals )
    if isinstance (c ,(list ,tuple ))and len (c )>=6 :
        return (_f (c [1 ]),_f (c [2 ]),_f (c [3 ]),_f (c [4 ]),_f (c [5 ]))
    return (None ,)*5 

def _ts (c ):
    if isinstance (c ,dict ):
        return _f (c .get ("t")or c .get ("openTime")or c .get ("time"))
    if isinstance (c ,(list ,tuple ))and c :
        return _f (c [0 ])
    return None 

def atr (cd ,n =14 ):
    if len (cd )<n +1 :
        return None 
    tr =[]
    for i in range (len (cd )-n ,len (cd )):
        _ ,h ,lo ,_ ,_ =_ohlc (cd [i ])
        pc =_ohlc (cd [i -1 ])[3 ]
        if None in (h ,lo ,pc ):
            return None 
        tr .append (max (h -lo ,abs (h -pc ),abs (lo -pc )))
    return sum (tr )/len (tr )if tr else None 

def _dicts (cd ):
    ""
    out =[]
    for c in cd :
        if isinstance (c ,dict )and "c"in c :
            out .append (c )
            continue 
        o ,h ,lo ,cl ,v =_ohlc (c )
        if None in (o ,h ,lo ,cl ):
            continue 
        out .append ({"t":_ts (c ),"o":o ,"h":h ,"l":lo ,"c":cl ,
        "v":v or 0.0 })
    return out 

def channel_pos (cd ):
    ""
    try :
        from hamid .structure import channel 
        ch =channel (_dicts (cd ))
        return round (ch .position ,2 )if ch else None 
    except Exception :
        return None 

def trend (cd ):
    ""
    try :
        from hamid .structure import trend as _t 
        d =_dicts (cd )
        return _t (d )if len (d )>=5 else None 
    except Exception :
        return None 

def bearish_ob (cd ,tf ="15m"):
    ""
    try :
        from hamid .orderblocks import near 
    except Exception :
        return None 
    d =_dicts (cd )
    if len (d )<30 :
        return None 
    try :
        b_in ,b_near =near (d ,tf =tf )
    except Exception :
        return None 
    box =b_in or b_near 
    if not box or box .get ("broken"):
        return None 

    if box .get ("move")not in (None ,"down"):
        return None 
    hi ,lo =box .get ("high"),box .get ("low")
    if hi is None or lo is None :
        return None 
    return {"top":hi ,"bottom":lo ,"height":max (hi -lo ,1e-12 ),
    "where":"داخل"if b_in else "نزدیک",
    "fresh":bool (box .get ("fresh")),
    "reactions":box .get ("reactions"),
    "hunts":box .get ("hunts"),
    "age_bars":box .get ("age"),"tf":box .get ("tf")}

def swept_high (cd ,look =40 ):
    ""
    seg =cd [-look :]if len (cd )>look else cd 
    if len (seg )<12 :
        return False 
    highs =[_ohlc (c )[1 ]for c in seg [:-3 ]]
    if not highs or any (h is None for h in highs ):
        return False 
    prior =max (highs )
    tail =seg [-3 :]
    pierced =any ((_ohlc (c )[1 ]or 0 )>prior for c in tail )
    closed_back =(_ohlc (tail [-1 ])[3 ]or 0 )<prior 
    return bool (pierced and closed_back )

def leverage_for (stop_pct ):
    ""
    if not stop_pct or stop_pct <=0 :
        return None 
    return max (1 ,min (P ["max_leverage"],int (P ["liq_guard"]/stop_pct )))

def size_for (equity ,stop_pct ,lev ):
    ""
    if not equity or not stop_pct or not lev :
        return None 
    risk_usd =equity *P ["risk_pct"]/100.0 
    notional =risk_usd /(stop_pct /100.0 )
    return {"risk_usd":round (risk_usd ,2 ),
    "notional_usd":round (notional ,2 ),
    "margin_usd":round (notional /lev ,2 )}

def _no (symbol ,tf ,why ,**extra ):
    return {"action":"NO_SIGNAL","symbol":symbol ,"tf":tf ,"why":why ,
    "strategy":STRATEGY_ID ,"version":STRATEGY_VERSION ,
    "validation_status":VALIDATION_STATUS ,
    "production_approved":PRODUCTION_APPROVED ,
    "panel":PANEL_NAME ,"t":int (time .time ()*1000 ),**extra }

def decide (symbol ,cd ,tf ="15m",cd_4h =None ,btc_4h =None ,btc_1h =None ,
equity =None ,now_ms =None ,alt_stance =None ,dom_generated =None ):
    ""
    now =now_ms or int (time .time ()*1000 )
    funnel =[]

    def step (name ,ok ,detail =""):
        funnel .append ({"gate":name ,"pass":bool (ok ),"detail":detail })
        return bool (ok )

    if not cd or len (cd )<P ["min_bars"]:
        return _no (symbol ,tf ,f"کندل کم: {len(cd or [])} < {P['min_bars']}",
        funnel =funnel )
    last_t =_ts (cd [-1 ])
    if last_t is None :
        return _no (symbol ,tf ,"مهرِ زمانِ کندل خوانده نشد",funnel =funnel )
    age_s =(now -last_t )/1000.0 
    if age_s >P ["stale_max_s"]*4 :

        return _no (symbol ,tf ,f"کندل کهنه: {age_s:.0f} ثانیه",funnel =funnel )
    step ("داده",True ,f"{len(cd)} کندل · سن {age_s:.0f}s")

    price =_ohlc (cd [-1 ])[3 ]
    if not price :
        return _no (symbol ,tf ,"قیمتِ کلوز خوانده نشد",funnel =funnel )

    is_btc =symbol .upper ().startswith ("BTC")

    dom_ok ,dom_stance ,dom_why =dominance_gate (
    symbol ,now ,stance =alt_stance ,generated =dom_generated )
    if not is_btc :
        if not step ("دامیننس (اولویت ۱)",dom_ok ,dom_why ):
            return _no (symbol ,tf ,dom_why ,funnel =funnel ,
            alt_stance =dom_stance )
    else :
        step ("دامیننس (شاهد — خودِ بیت‌کوین)",True ,dom_why )

    if not is_btc :
        if btc_4h is None or btc_1h is None :
            return _no (symbol ,tf ,"بسترِ بیت‌کوین در دسترس نیست (قانون ۳)",
            funnel =funnel )
        if btc_4h =="up"and btc_1h =="up":
            step ("بسترِ BTC",False ,"هر دو تایمِ BTC صعودی — وتوی مطلق")
            return _no (symbol ,tf ,"هر دو تایمِ بیت‌کوین صعودی — شورت وتو",
            funnel =funnel )
        step ("بسترِ BTC",True ,f"۴س={btc_4h} · ۱س={btc_1h}")

    t_own =trend (cd )
    if t_own is None :
        return _no (symbol ,tf ,"روندِ ساختاری محاسبه نشد",funnel =funnel )
    if t_own !="down":
        step ("ساختار",False ,f"روندِ ساختاری «{t_own}» است، نه down")
        return _no (symbol ,tf ,
        f"ساختارِ {tf} نزولی نیست ({t_own}) — شورت خلافِ ساختار",
        funnel =funnel )
    step ("ساختار",True ,f"{tf}: down")

    t4 =trend (cd_4h )if cd_4h else None 
    if t4 =="up":
        step ("تایم بالا (۴س)",False ,"۴س صعودی")
        return _no (symbol ,tf ,"ساختار ۴س صعودی — شورت خلاف روند بالادست",
        funnel =funnel )
    step ("تایم بالا (۴س)",True ,t4 or "بدون کندل ۴س — وتو نمی‌کند")

    cp =channel_pos (cd )
    if cp is None :
        return _no (symbol ,tf ,"مکانِ کانال محاسبه نشد",funnel =funnel )
    if cp <=P ["min_chan_pos"]:
        step ("مکان",False ,f"chan_pos={cp:.2f} ≤ {P['min_chan_pos']}")
        return _no (symbol ,tf ,
        f"قیمت در {cp:.0%} کانال — شورت از وسط/کف، تعقیبِ ریزش",
        funnel =funnel )
    step ("مکان",True ,f"chan_pos={cp:.2f}")

    ob =bearish_ob (cd ,tf =tf )
    if not ob :
        step ("اردر بلاک",False ,"باکسِ معتبرِ هم‌جهت پیدا نشد")
        return _no (symbol ,tf ,"اردر بلاک معتبرِ هم‌جهت نیست",funnel =funnel )
    _ob_tag ="تازه"if ob ["fresh"]else f"{ob.get('reactions')} واکنش"
    step ("اردر بلاک",True ,
    f"{ob['where']} باکس {ob['tf']} · سقف {ob['top']:.8g} · {_ob_tag}")

    sweep =swept_high (cd )
    step ("نقدینگی",True ,"سوییپِ سقف دیده شد"if sweep else "بدون سوییپ")

    entry =price 
    sl =ob ["top"]+P ["ob_buffer"]*max (ob ["height"],entry *1e-4 )
    if sl <=entry :
        return _no (symbol ,tf ,"استاپ زیر ورود — هندسهٔ نامعتبر",funnel =funnel )
    stop_pct =(sl -entry )/entry *100.0 
    if stop_pct <P ["min_stop_pct"]:
        step ("هندسه",False ,f"استاپ {stop_pct:.2f}٪ < {P['min_stop_pct']}٪")
        return _no (symbol ,tf ,
        f"استاپ {stop_pct:.2f}٪ تنگ‌تر از کف — دامِ کارمزد "
        f"(اندازه‌گیری: استاپِ تنگ ۰.۱۹R بدتر است)",
        stop_pct =round (stop_pct ,3 ),funnel =funnel )
    if stop_pct >P ["max_stop_pct"]:
        step ("هندسه",False ,f"استاپ {stop_pct:.2f}٪ > {P['max_stop_pct']}٪")
        return _no (symbol ,tf ,
        f"استاپ {stop_pct:.2f}٪ گشادتر از سقف — محافظ لیکویید",
        stop_pct =round (stop_pct ,3 ),funnel =funnel )
    step ("هندسه",True ,f"استاپ {stop_pct:.2f}٪")

    risk =sl -entry 
    tp1 =entry -P ["rr_target"]*risk 
    if tp1 <=0 :
        return _no (symbol ,tf ,"تارگت زیر صفر — هندسهٔ نامعتبر",funnel =funnel )
    tp2 =entry -2 *P ["rr_target"]*risk 

    try :
        from hamid import fees 
        fee_r =fees .cost_in_r (entry ,sl ,symbol =symbol )
    except Exception :

        fee_r =(0.15 /100.0 )*entry /risk 
    net_rr =P ["rr_target"]-fee_r 
    if net_rr <P ["min_net_rr"]:
        step ("کارمزد",False ,f"RR خالص {net_rr:.2f}")
        return _no (symbol ,tf ,
        f"RR خالص {net_rr:.2f} زیر کف {P['min_net_rr']}",
        fee_r =round (fee_r ,3 ),funnel =funnel )
    step ("کارمزد",True ,f"RR خالص {net_rr:.2f} · fee_r {fee_r:.3f}")

    lev =leverage_for (stop_pct )
    if not lev :
        return _no (symbol ,tf ,"اهرم محاسبه نشد",funnel =funnel )
    step ("اهرم",True ,f"×{lev} (محافظ لیکویید)")

    out ={
    "action":"SHORT","symbol":symbol ,"tf":tf ,
    "strategy":STRATEGY_ID ,"version":STRATEGY_VERSION ,

    "product":"futures","margin_mode":"isolated",
    "sl_tp_mandatory":True ,
    "entry":round (entry ,8 ),"sl":round (sl ,8 ),
    "tp1":round (tp1 ,8 ),"tp2":round (tp2 ,8 ),
    "stop_pct":round (stop_pct ,3 ),
    "rr_target":P ["rr_target"],"rr_net":round (net_rr ,2 ),
    "fee_r":round (fee_r ,3 ),"leverage":lev ,
    "chan_pos":round (cp ,3 ),"trend_4h":t4 ,
    "btc_4h":btc_4h ,"btc_1h":btc_1h ,

    "alt_stance":dom_stance ,"dom_why":dom_why ,
    "ob":ob ,"sweep":sweep ,
    "max_hold_bars":P ["max_hold_bars"],
    "trail":{"arm_at":round (entry -fee_r *risk ,8 ),
    "frac":0.80 ,
    "rule":"🪜 تا سود از کارمزد نگذشته استاپ دست نمی‌خورد؛ "
    "بعد از آن روی ۸۰٪ بهترین سود و فقط پایین‌تر "
    "(قانون تریل نسخهٔ سه)"},

    "validation_status":VALIDATION_STATUS ,
    "production_approved":PRODUCTION_APPROVED ,
    "boundary":("PAPER_ONLY — چهار فیلترِ این موتور ضررِ شورت را از "
    "−۰.۳۱R به ~صفر می‌آورند (n=۵۹۴، دو نیمهٔ هم‌خوان)، "
    "ولی CI هنوز شاملِ صفر است. سودِ اثبات‌شده نیست."),
    "panel":PANEL_NAME ,"t":now ,"funnel":funnel ,
    }
    out ["stop_loss"],out ["take_profit"]=out ["sl"],out ["tp1"]
    if equity :
        s =size_for (equity ,stop_pct ,lev )
        if s :
            out .update ({"size_usd":s ["notional_usd"],
            "margin_usd":s ["margin_usd"],
            "risk_usd":s ["risk_usd"]})
    return out 

def signal (symbol ,tf ="15m",equity =None ,fetch =None ,dom =None ):
    ""
    if dom is not None :
        load_dominance (dom )
    elif not DOM .get ("stance"):
        local =ROOT /"signals"/"dominance.json"
        try :
            load_dominance (json .loads (local .read_text (encoding ="utf-8")))
        except Exception :
            sync_dominance ()
    if fetch is None :
        import sources 
        fetch =lambda s ,t ,n :sources .klines (s ,t ,n )
    try :
        cd =fetch (symbol ,tf ,200 )
        cd4 =fetch (symbol ,"4h",200 )
    except Exception as e :
        return _no (symbol ,tf ,f"کندل گرفته نشد: {type(e).__name__}")
    b4 =b1 =None 
    if not symbol .upper ().startswith ("BTC"):
        try :
            b4 =trend (fetch ("BTCUSDT","4h",200 ))
            b1 =trend (fetch ("BTCUSDT","1h",200 ))
        except Exception :
            b4 =b1 =None 
    return decide (symbol ,cd ,tf =tf ,cd_4h =cd4 ,btc_4h =b4 ,btc_1h =b1 ,
    equity =equity )

def _zig (legs =8 ,down =12 ,up =6 ,step =0.010 ,retr =0.5 ,base =100.0 ,
tf_ms =900_000 ,end =0 ,direction ="down",end_pull =0 ):
    ""
    sgn =-1 if direction =="down"else 1 
    px ,rows =base ,[]
    for _ in range (legs ):
        for _ in range (down ):
            o =px 
            c =o *(1 +sgn *step )
            rows .append ((o ,max (o ,c )*1.001 ,min (o ,c )*0.999 ,c ))
            px =c 
        for _ in range (up ):
            o =px 
            c =o *(1 -sgn *step *retr )
            rows .append ((o ,max (o ,c )*1.001 ,min (o ,c )*0.999 ,c ))
            px =c 
    for _ in range (end_pull ):
        o =px 
        c =o *(1 -sgn *step *0.9 )
        rows .append ((o ,max (o ,c )*1.001 ,min (o ,c )*0.999 ,c ))
        px =c 
    n =len (rows )
    return [[end -(n -1 -i )*tf_ms ,o ,h ,lo ,c ,1000.0 ]
    for i ,(o ,h ,lo ,c )in enumerate (rows )]

REF =dict (legs =8 ,down =12 ,up =6 ,step =0.010 ,retr =0.5 ,end_pull =8 )

def _mk (path ,t0 =0 ,tf_ms =900_000 ,base =100.0 ,end =None ):
    ""
    if end is not None :
        t0 =end -(len (path )-1 )*tf_ms 
    out ,p =[],base 
    for i ,m in enumerate (path ):
        o =p 
        c =o *m 
        h ,lo =max (o ,c )*1.001 ,min (o ,c )*0.999 
        out .append ([t0 +i *tf_ms ,o ,h ,lo ,c ,1000.0 ])
        p =c 
    return out 

def _selftest ():
    ok ,fail =0 ,[]

    def chk (name ,cond ,extra =""):
        nonlocal ok 
        if cond :
            ok +=1 
        else :
            fail .append (name )
            print (f"  ✗ {name}"+(f"  ↳ {extra}"if extra else ""))

    now =1788800000000 
    tf_ms =900_000 

    cd =_zig (end =now ,tf_ms =tf_ms ,**REF )
    cd4 =_zig (legs =6 ,down =10 ,up =5 ,end =now ,tf_ms =14_400_000 )

    d =decide ("AAAUSDT",cd ,cd_4h =cd4 ,btc_4h ="down",btc_1h ="down",
    equity =1000 ,now_ms =now ,alt_stance ="SHORT_ALT")
    chk ("خروجی dict معتبر است",isinstance (d ,dict )and "action"in d ,str (d )[:120 ])
    chk ("هرگز LONG نمی‌دهد",d ["action"]in ("SHORT","NO_SIGNAL"),d ["action"])
    chk ("قیفِ دروازه‌ها روی خروجی هست",isinstance (d .get ("funnel"),list ))
    chk ("وضعیت اعتبارسنجی روی خروجی هست",
    d .get ("validation_status")==VALIDATION_STATUS )
    chk ("تولید تأیید نشده است",d .get ("production_approved")is False )

    v =decide ("AAAUSDT",cd ,cd_4h =cd4 ,btc_4h ="up",btc_1h ="up",now_ms =now ,alt_stance ="SHORT_ALT")
    chk ("هر دو تایمِ BTC صعودی = وتو",v ["action"]=="NO_SIGNAL",v .get ("why"))
    m =decide ("AAAUSDT",cd ,cd_4h =cd4 ,now_ms =now ,alt_stance ="SHORT_ALT")
    chk ("بسترِ BTC ناموجود = NO_SIGNAL نه عبورِ کور",
    m ["action"]=="NO_SIGNAL"and "بیت‌کوین"in m ["why"],m .get ("why"))
    b =decide ("BTCUSDT",cd ,cd_4h =cd4 ,now_ms =now )
    chk ("ولی خودِ BTC از دروازهٔ بستر رد نمی‌شود",
    not any (g ["gate"]=="بسترِ BTC"for g in b .get ("funnel",[])))

    u4 =_zig (legs =6 ,down =10 ,up =5 ,direction ="up",end =now ,
    tf_ms =14_400_000 )
    r =decide ("AAAUSDT",cd ,cd_4h =u4 ,btc_4h ="down",btc_1h ="down",
    now_ms =now ,alt_stance ="SHORT_ALT")
    chk ("۴س صعودی = رد",r ["action"]=="NO_SIGNAL"and "۴س"in r ["why"],
    f"{r['action']} · {r.get('why')} · t4={trend(u4)}")

    up =_zig (direction ="up",end =now ,tf_ms =tf_ms ,**REF )
    r =decide ("AAAUSDT",up ,cd_4h =cd4 ,btc_4h ="down",btc_1h ="down",
    now_ms =now ,alt_stance ="SHORT_ALT")
    chk ("ساختارِ صعودیِ تایمِ ورود = رد",
    r ["action"]=="NO_SIGNAL",r .get ("why"))

    chk ("کندل کم = NO_SIGNAL",
    decide ("AAAUSDT",cd [:10 ],now_ms =now ,alt_stance ="SHORT_ALT")["action"]=="NO_SIGNAL")
    stale =_zig (end =now -10 *86400_000 ,tf_ms =tf_ms ,**REF )
    chk ("کندل کهنه = NO_SIGNAL",
    decide ("AAAUSDT",stale ,cd_4h =cd4 ,btc_4h ="down",btc_1h ="down",
    now_ms =now ,alt_stance ="SHORT_ALT")["action"]=="NO_SIGNAL")

    chk ("روندِ نزولی down است",trend (_zig ())=="down",str (trend (_zig ())))
    chk ("روندِ صعودی up است",trend (_zig (direction ="up"))=="up",
    str (trend (_zig (direction ="up"))))

    flat =_zig (legs =8 ,down =6 ,up =6 ,retr =1.0 ,end =now ,tf_ms =tf_ms )
    chk ("بازارِ بی‌جهت شورت نمی‌سازد",
    decide ("BTCUSDT",flat ,now_ms =now )["action"]=="NO_SIGNAL",
    f"{trend(flat)}")

    dom_args =dict (cd_4h =cd4 ,btc_4h ="down",btc_1h ="down",
    equity =1000 ,now_ms =now )
    chk ("بدونِ بسترِ دامیننس، آلت سیگنال نمی‌گیرد (قانون ۰۱ بند ۳)",
    decide ("AAAUSDT",cd ,**dom_args )["action"]=="NO_SIGNAL")
    veto =decide ("AAAUSDT",cd ,alt_stance ="LONG_ALT_STRONG",**dom_args )
    chk ("بسترِ LONG_ALT_STRONG شورتِ آلت را وتو می‌کند",
    veto ["action"]=="NO_SIGNAL"and "دامیننس"in veto ["why"],
    veto .get ("why"))
    chk ("و همان ستاپ با بسترِ SHORT_ALT سیگنال می‌دهد (اثباتِ منفی)",
    d ["action"]=="SHORT",d .get ("why"))
    neu =decide ("AAAUSDT",cd ,alt_stance ="NEUTRAL",**dom_args )
    chk ("بسترِ خنثی وتو نمی‌کند — دروازه‌های بعدی تصمیم می‌گیرند",
    neu ["action"]=="SHORT",neu .get ("why"))
    lbo =decide ("AAAUSDT",cd ,alt_stance ="LONG_BTC_ONLY",**dom_args )
    chk ("LONG_BTC_ONLY وتو نیست (ادعای بیش از داده ممنوع)",
    lbo ["action"]=="SHORT",lbo .get ("why"))
    old =decide ("AAAUSDT",cd ,alt_stance ="SHORT_ALT",
    dom_generated =now -3 *3600_000 ,**dom_args )
    chk ("عکس‌فوریِ کهنهٔ دامیننس = NO_SIGNAL، نه عبورِ کور",
    old ["action"]=="NO_SIGNAL"and "کهنه"in old ["why"],old .get ("why"))
    chk ("دروازهٔ دامیننس **اولِ** قیف است، پیش از بسترِ BTC",
    [g ["gate"]for g in d ["funnel"]][:2 ]==["داده","دامیننس (اولویت ۱)"],
    str ([g ["gate"]for g in d ["funnel"]][:3 ]))
    chk ("ردپای بستر روی خروجی می‌نشیند (سنجشِ شبانه)",
    d .get ("alt_stance")=="SHORT_ALT")

    btc_lb =decide ("BTCUSDT",cd ,cd_4h =cd4 ,now_ms =now ,
    alt_stance ="LONG_ALT_STRONG")
    chk ("برای خودِ BTC، دامیننس شاهد است نه وتو",
    btc_lb ["action"]=="SHORT",btc_lb .get ("why"))

    if d ["action"]=="SHORT":
        chk ("مارجین ایزوله",d ["margin_mode"]=="isolated")
        chk ("استاپ و تارگت روی خروجی",
        d .get ("stop_loss")and d .get ("take_profit"))
        chk ("تارگت زیر ورود (شورت)",d ["tp1"]<d ["entry"])
        chk ("استاپ بالای ورود (شورت)",d ["sl"]>d ["entry"])
        chk ("اهرم از محافظ لیکویید رد نمی‌شود",
        d ["leverage"]<=min (P ["max_leverage"],
        int (P ["liq_guard"]/d ["stop_pct"])),
        f"lev={d['leverage']} stop={d['stop_pct']}")
        chk ("استاپ از کفِ هندسه گشادتر است",
        d ["stop_pct"]>=P ["min_stop_pct"],str (d ["stop_pct"]))
        chk ("RR خالص از کف بالاتر است",d ["rr_net"]>=P ["min_net_rr"])
        chk ("ضررِ استاپ ۲٪ سرمایه می‌ماند",
        abs (d ["risk_usd"]-20.0 )<0.01 ,str (d .get ("risk_usd")))
        chk ("مرزِ صادقانه روی خروجی هست","PAPER_ONLY"in d ["boundary"])
        chk ("امضای پنل هست",d ["panel"]==PANEL_NAME )
        chk ("شناسه و نسخهٔ استراتژی هست",
        d ["strategy"]==STRATEGY_ID and d ["version"]==STRATEGY_VERSION )
    else :
        fail .append ("مسیرِ سیگنال‌دار اصلاً فعال نشد")
        print (f"  ✗ سناریوی شورت به SHORT نرسید: {d.get('why')}")

    chk ("محافظ لیکویید: استاپ ۵٪ → اهرم ۱۰",leverage_for (5.0 )==10 )
    chk ("سقف اهرم ۲۰ رعایت می‌شود",leverage_for (0.1 )==P ["max_leverage"])
    s =size_for (1000 ,2.0 ,10 )
    chk ("سایز از ریسکِ ۲٪ می‌آید، نه از اهرم",
    abs (s ["risk_usd"]-20 )<1e-6 and abs (s ["notional_usd"]-1000 )<1e-6 ,
    str (s ))

    print (f"{ok} بررسی گذشت"+(f"، {len(fail)} افتاد: {fail}"if fail else ""))
    return not fail 

def main (argv ):
    if "--selftest"in argv :
        return 0 if _selftest ()else 1 
    sym =next ((a for a in argv [1 :]if not a .startswith ("-")),"BTCUSDT")
    tf ="15m"
    if "--tf"in argv :
        tf =argv [argv .index ("--tf")+1 ]
    print (json .dumps (signal (sym ,tf =tf ),ensure_ascii =False ,indent =1 ))
    return 0 

if __name__ =="__main__":
    sys .exit (main (sys .argv ))

