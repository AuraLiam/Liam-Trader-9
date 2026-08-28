---
name: signal-work
description: Working rules for Hamid's trading panel. Load before changing the engine, reporting a number, tuning a threshold, reviewing paper-trading results, or answering "why is there no signal". Covers what to measure, what to refuse, and how to raise signal accuracy toward the 90% target without fooling ourselves.
---

# Working on the signal engine

The goal is signals that land above 90%. Nothing below is a style preference —
each rule exists because breaking it already cost days.

## Every closed trade changes who decides the next one (Hamid, 23 Aug)

Hamid: *"With every single trade, and finding its cause, and drawing the
conclusion — you are different from the person you were. One more thing
was added to your experience. And you must make a better impact on the
next analysis and the next signal. After each round of learning, you are
an agent with more experience making the final decision."*

Treat that as architecture, not encouragement. Three obligations follow:

1. **A trade that closes without a cause is wasted.** Every close gets
   digested in the same cycle — a case file, and where it generalizes, a
   lesson. Not tomorrow, not "when there's time".
2. **The next decision must actually read that record.** Before a signal
   the engine asks what this coin, this direction, this shape has already
   done, and the learning room holds back a setup whose record is bad on
   a real sample. If a change cannot alter a future decision, it is not
   learning — it is note-taking.
3. **Never claim the improvement — measure it.** Accumulated experience
   is not a guarantee of profit, and this is where the principle would
   quietly turn into self-flattery. A single good day proves nothing.

   The live example that keeps this honest (23 Aug): on the multi-day
   book, "issued with experience" measured **+0.443R, CI [+0.037,
   +0.839]** — real and significant. On that *single day's* sample (57
   with experience vs 80 without) the same comparison gave **−0.070R, CI
   [−0.374, +0.251]** — an interval straddling zero, indistinguishable
   from noise. Both numbers are correct; the difference is sample size.
   So: report the day's outcome as an outcome, and report the *effect of
   learning* only from a sample large enough to carry a confidence
   interval.

The honest form of the principle: each trade adds a case, the ledger
changes the next decision, and how much that helped is a measured
quantity that can come out flat — or negative — on any given day.

## Read every instruction three times (Hamid, 23 Aug)

Hamid's messages are dense lists, and skipping an item once already cost a
full apology cycle. So: read the message once to understand, once to extract
every single ask into a checklist, and a **third time at the end of the work
to verify each item is actually done** — done in the repo, not promised in
the reply. An item that cannot be done gets said out loud with its reason,
never silently dropped. The final reply mirrors the checklist.

## Measure first, and measure the right thing

Never change a threshold on intuition. The tools are in `tests/`:

```bash
node tests/evaluate.js          # walk-forward over simulated markets
node tests/diagnose.js          # where setups die, gate by gate
node tests/cycle.js             # one full cycle, sharded across cores
node tests/search.js            # parameter sweep, fitted and judged separately
python3 claude-liam-signal/python/screener.py   # which symbols deserve attention now
```

Report expectancy, not win rate. A 98% win rate at 0.74R average is worse than
44% at 1.89R, and the first version of this engine had exactly that profile
because targets were the nearest prior swing.

Always bootstrap a confidence interval. **A finding is only acted on once its
interval clears zero.** This rule has caught two of my own wrong conclusions.

## Sample size is not optional

557 trades gave +0.25R. The same engine over 15,290 trades gave 0.00R. The
first number was noise and I reported it as a result. Before claiming anything,
check the sample is in the thousands, and shard across cores:

```bash
for i in 0 1 2 3; do node tests/worker.js $((1+i*150)) $((1+(i+1)*150)) > /tmp/w$i.json & done; wait
```

## Overfitting has a specific smell

A configuration that wins in-sample and loses out-of-sample is fitting noise.
`tests/search.js` fits on one set of markets and judges on another, ranks only
on the held-out set, and refuses anything whose out-of-sample interval spans
zero. Adopt a candidate only when:

- the out-of-sample interval is entirely above zero,
- the gain over what is shipped is worth taking (> 0.02R, not a rounding),
- and neighbouring cells agree — a lone winning cell in a grid is luck.

I once widened the freshness window to 200 bars on the strength of a trending
tape I had written minutes earlier. The rigorous simulator put it at −0.16R
with the whole interval below zero.

## The simulator is a null test, not a market

It has volatility clustering, fat tails and regime switching, and no order
flow. A strategy that finds edge in it is reading its own noise. Zero there is
the *correct* result for an honest engine. Say plainly which source a number
comes from — simulated or live candles — every single time.

## Two desks, different jobs

**The practice desk** trades the live tape at real prices with no money and no
signal. Its gates are loose on purpose: any structure with a real entry, stop
and target. A strict desk yields a handful of outcomes a day and teaches the
learning room nothing. Everything it settles feeds the confidence model and the
case memory.

**The signal desk** is strict, and before anything goes out the supervisor asks
the learning room about *that coin, that direction, situations like this one*.
Enough negative history vetoes it. Below a dozen trades, say the history is too
thin rather than pretending.

Raising accuracy means growing the practice sample, not tightening the signal
gate until nothing fires. Zero signals is not 100%.

## One change per cycle

Applying several at once makes the next result unreadable — an improvement
names no cause, a regression names nothing to undo. Each review grades the
previous change against trades that closed since, keeps or reverts it, then
makes at most one new change. A reverted change is quarantined; leaving it
eligible produced an oscillation rather than a search.

## What "no signal" actually means

Check in this order, because I wasted days assuming the engine:

1. Is data arriving? Binance geo-blocks some regions and an unreachable host
   looks exactly like a quiet market. The panel says so in a red box.
2. Is the panel deployed and open?
3. Run `node tests/diagnose.js` — it counts where setups die. Last time nothing
   in the decision layer was blocking anything; the engine signalled on 3.6% of
   checks and the problem was that most of those signals should not have been
   taken.

## Reporting

Every number needs a script that reproduces it. Corrections come first and
plainly, with the measurement that overturned the old claim. Never soften a bad
result — Hamid trades this himself and a flattering number is worse than none.

## Standing tools

Per `CLAUDE.md`: Actions carries all heavy compute, Notion the comparable
record, Drive the archive, Gmail drafts only, Telegram live delivery, n8n
orchestration. Use them without being asked. Never put the replay work on the
laptop.

## قوانین اصلی یادگیری و حافظه — از خود حمید، ۱۰ اوت ۲۰۲۶ (عیناً)

۱. **Memory Persistence:** هر تحلیل، نتیجه‌گیری‌ها، الگوها، اشتباهات و
درس‌هایش را ذخیره می‌کند و تحلیل‌های بعدی از آن استفاده می‌کنند.
۲. **Continuous Learning Loop:** بعد از هر تحلیل از نتیجه‌اش یاد بگیر —
سیگنال درست: دلیل موفقیت ثبت؛ اشتباه: علت خطا تحلیل و به دانش اضافه شود.
۳. **Progressive Improvement:** هر تحلیل باید از قبلی هوشمندتر باشد.
هرگز مثل مدل ثابت رفتار نکن.

**رفتار در پنل:** با ظهور هر سیگنال، خودکار تاریخچهٔ همان ارز و مشابه‌ها
(شباهت چارت، ساختار، BOS/CHoCH/FVG/OB/نقدینگی، حجم، احساسات، خبر) بررسی و
بر پایهٔ دانش انباشته تأیید/رد شود؛ شباهت قوی با گذشته **صریح ذکر** شود.

**چرخهٔ همیشگی:** تحلیل → یادگیری → ذخیره در حافظه → استفاده در تحلیل
بعدی → بهبود عملکرد.

پیاده‌سازی: `hamid/memory.py` (دفتر درس‌ها + مشورت قبل از صدور)،
`brain.learn/recall` (حافظهٔ آماری)، هضم بسته‌شده‌ها در هر چرخه، خط 🧠
در پیام تلگرام، جعبهٔ «حافظه و درس‌ها» در تب ایجنت. قید صداقت پابرجاست:
زیر ۸ مورد مشابه فقط ذکر، بدون اثر رتبه؛ وتو با ۱۲+ (ناظر تجربه).

## نقشهٔ نقدینگی (لیکوییدیتی هیت‌مپ) — درس ثابت ایجنت

هیت‌مپ جایی را نشان می‌دهد که استاپ‌ها و لیکوییدها جمع‌اند: بالای سقف‌های
برابر (استاپ شورت‌ها) و زیر کف‌های برابر (استاپ لانگ‌ها). قیمت مثل آهن‌ربا
سمت استخر بزرگ‌تر کشیده می‌شود و بعد از برداشتن نقدینگی اغلب برمی‌گردد
(همان سوییپ ایندوسمنت). تخمین ما از کندل است، نه سرویس پولی:
`hamid/liquidity.py` — خوشهٔ اکسترمم‌های سوینگ در ±۰.۱۵٪ با ۲+ برخورد.
هر چرخه قبل از سیگنال چک می‌شود، جهتش («هم‌جهت/خلاف آهن‌ربا») روی هر
معامله ثبت و در پیام تلگرام (💧) ذکر می‌شود. قانونِ عمل نیست تا وقتی شرط
«نقدینگی هم‌جهت بود» در بک‌تست شبانه بازهٔ اطمینانش را از صفر رد کند.

## چارت اجباری روی هر سیگنال — درس ۱۰ اوت

قانون حمید: سیگنال بی‌چارت نرود. یک بار شکست: ورک‌فلوی چرخه matplotlib
نصب نمی‌کرد، `_tg_chart` بی‌صدا except می‌خورد و fallback متنی می‌رفت —
سیگنال‌ها بدون چارت رسیدند و حمید دید. درس ماندگار: **fallback ساکت،
خطا را از چشم پنهان می‌کند؛ هر مسیر ارسال جدید باید (۱) وابستگی چارت را
در ورک‌فلو نصب کند و (۲) شکست چارت را در لاگ بلند بگوید.** مسیرهای
ارسال و چارتشان: چرخه (`_tg_chart` ۵د + واترمارک)، اسکن (`chart.render`)،
رادار پامپ (`_pick_chart` انتخاب اول)، هشدار ریزش (چارت BTC). سقف کپشن
تلگرام ۱۰۲۴ کاراکتر است — پیام بلندتر: متن جدا + عکس جدا.

## نقشهٔ لیکوییدیشن (سبک kCEX) — liqmap.py

اپ kCEX نقشهٔ لیکوییدیشن دارد ولی API عمومی ندارد؛ معادل بازتولیدپذیرش
از کندل واقعی ساخته شد: حجم هر ساعت × اهرم‌های رایج (۱۰/۲۵/۵۰/۱۰۰×) →
خوشه‌های لیکویید بالا/پایین قیمت + آهن‌ربا. روی کپشن (🗺) و دلایل پیک
رادار. همیشه با برچسب «تخمین از کندل واقعی — دادهٔ مستقیم صرافی نیست».

## تمرین تاریخی — «هزار بار استفاده کن و یاد بگیر»

بک‌تست شبانهٔ backtest.py (کندل واقعی) آمار هر ارز×جهت را به
`brain/history-stats.json` می‌نویسد؛ `memory.history()` قبل از هر سیگنال
آن را کنار تجربهٔ زنده می‌گذارد. کف ۳۰ ریپلی برای ذکر؛ اثر روی رتبه فقط
وقتی CI از صفر رد شود. ریپلی روی تاریخ، ادعای سود زنده نیست — فقط تجربه.

## بازجویی پیش از صدور — قانون حمید (۱۰ اوت)

«قبل از صدور سیگنال نهایی، در ۱۵ دقیقه ببین چه چیزهایی می‌تواند استاپش
کند؛ فقط وقتی دلایل تارگت بیشتر از دلایل استاپ بود صادرش کن.»
پیاده‌سازی: `hamid/premortem.py` در گلوگاه `telegram.send_signals` — همهٔ
مسیرها (چرخه، اسکن، آلارم) از زیرش رد می‌شوند. دلایل شمرده‌شده: استاپ در
برابر ATR ۱۵د، روند ۱۵د، RSI، آهن‌ربای نقدینگی، خوشهٔ لیکویید، تمرین
تاریخی (CI)، دامیننس تتر و رویداد کلانِ ≤۲ساعت، تارگتِ دورتر از ۶×ATR.
حکم سخت: pro > con. ردشده‌ها به دفتر vetoed می‌روند تا خود دروازه نمره
بگیرد — اگر ردشده‌ها بیشترشان تارگت خوردند، دروازه باید شل شود. خطای
زیرساخت (شبکه) جلوی ارسال را نمی‌گیرد: دروازه تحلیل است نه بهانهٔ سکوت.

## لگ-کورولیشن — معنی واقعی «همبستگی» از زبان حمید (۱۰ اوت)

«همبستگی ارزهای پامپ‌شده» یعنی lag correlation سری بازده‌ها، نه شمارش
رخداد: r بین بازدهٔ سردسته در t و بازدهٔ کاندیدا در t+k، برای kهای
مختلف، در ۱h (تا ۱۲ کندل) و ۱۵m (تا ۱۶ کندل). دنباله‌روی واقعی = بهترین
r در تأخیر مثبت + برتری روشن بر جهت معکوس. آستانهٔ سخت: r≥۰.۲ با n≥۲۰۰
(جستجوی چند-تأخیره روی نویز همیشه عدد قشنگ می‌سازد — زیر آستانه ادعا
ممنوع). پیاده‌سازی: `hamid/lagcorr.py`؛ در رادار، راه دومِ اثباتِ رابطهٔ
خوشه‌ای است (کنار ۲+ سابقهٔ رخدادی) و پنجرهٔ نامزدش ۲×lag با کف ۳ ساعت.

## هم‌زمانی سیگنال با نقطهٔ ورود + ضدسیل (۱۰ اوت)

شکایت حمید: سیگنال تکراری، بیش از حد، و ناهم‌زمان (قیمت از ورود رد شده
یا خیلی دور). سه دروازه در گلوگاه ارسال:
· **هم‌زمانی**: لحظهٔ ارسال، آخرین کندل ۵ دقیقه خوانده می‌شود؛ اگر قیمت
  بیش از نصفِ فاصلهٔ استاپ از ورود رد شده یا بیش از ۲.۵٪ دور است — ارسال
  نمی‌شود، بی‌استثنا. قیمت لحظه و فاصله روی خود پیام (⏱) چاپ می‌شود.
· **ضدتکرار بین‌استراتژی**: کلید بدون نام استراتژی (sym|tf|dir) با پنجرهٔ
  ۳ ساعته — همان ستاپ با دو برچسب، دو بار نمی‌رود.
· **سقف مطلق ۱۶ در ۱۲ ساعت** برای همه، حتی الیت/آلارم.
یادآوری آدرس: 127.0.0.1 هر پورتی، پنل نیست — کپی محلی مرده است.

## واکنش-بازار و کالبدشکافی استاپ (۱۱ اوت)

قانون حمید: «وقتی بیت می‌ریزد و ال‌تی‌سی استاپ می‌خورد، ایجنت وارد شود؛
لگ-کورولیشنی بررسی کند و به آخرین ریزش قبلی BTC برگردد ببیند آن موقع هم
ریخته بود یا نه — بعد تصمیم بگیرد.» پیاده‌سازی، دو سر:
· **پیش از سیگنال** (premortem بند ۸): اگر BTC همین حالا ≥۱٪/۱س حرکت
  دارد، لگ-کورولیشن BTC→ارز + رفتارش در حرکت بزرگ قبلی BTC حساب می‌شود؛
  خلاف جهت = دلیل استاپ، هم‌جهت = دلیل تارگت.
· **پس از استاپ** (settle_books): برای هر استاپ، حکم سه‌حالته با عدد:
  «سیستمی بود» (BTC خلاف + رابطهٔ لگ-کورولیشنی + سابقهٔ ریزش قبلی) /
  «BTC خلاف بود ولی رابطه قانع‌کننده نیست» / «ربطی به BTC نداشت — ضعف
  ستاپ». حکم روی پیام نتیجهٔ تلگرام (🔎) و در حافظه (kind بررسی) می‌نشیند
  تا استاپ سیستمی با ضعف ستاپ در یادگیری قاطی نشود.
هستهٔ مشترک: `lagcorr.market_reaction` + `reaction_fa` — خالص و تست‌شده.

## منشور LIAM — قانون اساسی (۱۱ اوت)

Master Prompt کامل حمید در `claude-liam-signal/LIAM-CHARTER.md` کلمه به
کلمه ثبت است — قوانین تغییرناپذیر؛ هیچ تغییری بدون دستور صریح او. نگاشت
صادقانهٔ وضعیت اجرا بند به بند در `LIAM-STATUS.md` (✅/🟡/❌) و با هر
پیشرفت به‌روز می‌شود. سه شکاف بعدی به ترتیب ارزش: ماشین وضعیت ۷حالتهٔ
سیگنال (بند ۱۸)، ردگیری وضعیت OB/FVG با آمار هر کلاس (بند ۹/۲۴)، ساختار
خود USDT.D + TOTAL2/3 (بند ۱۰–۱۱). از همین امروز اضافه شد: MFE/MAE و
مدت نگهداری روی هر معاملهٔ بسته (بند ۲۲) و خط «⛔ باطل‌کننده» روی هر
سیگنال (بند ۱۹).

## Before any claim about system state, run the bus (Hamid, 28 Aug — rule 13)

Hamid: *"Why should this disorder exist? … nothing should operate
separately … connect the main agent to that same reason-and-proof part so
this problem doesn't happen again."*

The measured root cause: 54 state files in `signals/` aged 31 minutes to
18 days, none of them declaring how stale it was allowed to be. Absence
of a contract, not broken parts, produced the mess — and the same class
had kept the Telegram ledger invisible for months.

The contract now exists: `config/state_registry.json` (layer, owner
engine, producer, consumer, kind, max age, critical) and
`hamid/state_bus.py` judges it into `signals/system-state.json`.

Three obligations, non-negotiable:

1. **Never claim system health from memory.** Run
   `python3 -m hamid.state_bus --packet` and quote its evidence packet.
   "Everything looks fine" without the verdict is an unsourced claim.
2. **Never cite a data layer without its age and its cap.** "Dominance is
   fresh" means nothing; "dominance 12 min, cap 45" is a fact.
3. **A new module that writes a state file is unfinished until it has a
   registry row.** No "we'll register it later" — the guard
   (`hamid/test_state_bus.py`) turns the cycle red on any orphan file,
   which is exactly the point.

Set a cap from the producer's *measured* cadence plus margin, never from
what you wish it were. A cap that is always violated becomes noise, and
noise gets ignored — worse than no cap at all.
