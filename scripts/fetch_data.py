#!/usr/bin/env python3
"""
東証全銘柄の財務データを取得して jpdata.js を生成する。
  1) JPX「東証上場銘柄一覧」(xlsx) から内国株の一覧を取得
  2) Yahoo Finance の quote API でまとめて株価・PER・PBR・配当などを取得
  3) quoteSummary で ROE・ROA・営業利益率・有利子負債・FCF を1銘柄ずつ取得
  4) chart API の1年分の日次終値から年率ボラティリティを計算
使い方:  python3 scripts/fetch_data.py       （LIMIT=40 を付けると40銘柄だけで動作確認）
出力  :  jpdata.js
"""
import json, math, time, os, queue, threading, datetime, urllib.request, http.cookiejar, io, re

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36"
JPX_PAGE = "https://www.jpx.co.jp/markets/statistics-equities/misc/01.html"
KEEP = {'プライム（内国株式）', 'スタンダード（内国株式）', 'グロース（内国株式）'}
MK = {'プライム': 0, 'スタンダード': 1, 'グロース': 2}

opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
opener.addheaders = [('User-Agent', UA)]

def get(url, timeout=30):
    return opener.open(url, timeout=timeout).read()

def crumb():
    try: get("https://fc.yahoo.com/", 15)
    except Exception: pass
    return get("https://query2.finance.yahoo.com/v1/test/getcrumb", 15).decode()

def universe():
    html = get(JPX_PAGE).decode('utf-8', 'replace')
    m = re.search(r'href="([^"]*data_j\.xlsx?)"', html)
    url = "https://www.jpx.co.jp" + m.group(1) if m.group(1).startswith('/') else m.group(1)
    raw_xlsx = get(url, 90)
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(raw_xlsx), read_only=True)
    rows = list(wb.active.iter_rows(values_only=True))[1:]
    return [{"code": str(r[1]), "name": r[2], "mkt": r[3].replace('（内国株式）', ''),
             "sector": r[5]} for r in rows if r[3] in KEEP]

def N(v):
    try:
        f = float(v)
        return f if f == f and abs(f) != float('inf') else None
    except Exception:
        return None

def pull(codes, make_url, parse, workers=8, label=""):
    out, lock, q = {}, threading.Lock(), queue.Queue()
    for c in codes: q.put(c)
    def work():
        while True:
            try: c = q.get_nowait()
            except queue.Empty: return
            for a in range(3):
                try:
                    rec = parse(json.loads(get(make_url(c)).decode()))
                    with lock: out[c] = rec
                    break
                except Exception:
                    time.sleep(1 + a * 2)
    ts = [threading.Thread(target=work) for _ in range(workers)]
    [t.start() for t in ts]; [t.join() for t in ts]
    miss = [c for c in codes if c not in out]
    print("  %s: %d/%d 取得（失敗 %d）" % (label, len(out), len(codes), len(miss)), flush=True)
    if miss:
        for c in miss: q.put(c)
        ts = [threading.Thread(target=work) for _ in range(3)]
        [t.start() for t in ts]; [t.join() for t in ts]
        print("  %s: 再試行後 %d/%d" % (label, len(out), len(codes)), flush=True)
    return out

def raw(d, k):
    v = d.get(k)
    return v.get("raw") if isinstance(v, dict) else None

def main():
    cr = crumb()
    uni = universe()
    lim = os.environ.get("LIMIT")
    if lim: uni = uni[:int(lim)]
    codes = [u["code"] for u in uni]
    print("対象 %d 銘柄" % len(codes), flush=True)

    quotes = {}
    fields = ("regularMarketPrice,marketCap,trailingPE,priceToBook,trailingAnnualDividendYield,"
              "epsTrailingTwelveMonths,bookValue")
    for i in range(0, len(codes), 100):
        ch = [c + ".T" for c in codes[i:i + 100]]
        url = ("https://query2.finance.yahoo.com/v7/finance/quote?symbols=" + ",".join(ch)
               + "&crumb=" + cr + "&fields=" + fields)
        for a in range(3):
            try:
                j = json.loads(get(url).decode())
                for qr in j["quoteResponse"]["result"]:
                    quotes[qr["symbol"][:-2]] = qr
                break
            except Exception:
                time.sleep(2)
    print("  株価: %d/%d 取得" % (len(quotes), len(codes)), flush=True)

    MODS = "financialData,defaultKeyStatistics,summaryDetail"
    def fnd_url(c):
        return "https://query2.finance.yahoo.com/v10/finance/quoteSummary/%s.T?modules=%s&crumb=%s" % (c, MODS, cr)
    def fnd_parse(j):
        r = j["quoteSummary"]["result"][0]
        fd, dk, sd = r.get("financialData", {}), r.get("defaultKeyStatistics", {}), r.get("summaryDetail", {})
        d = {}
        for k in ["returnOnEquity","returnOnAssets","operatingMargins","totalDebt","freeCashflow"]: d[k] = raw(fd, k)
        for k in ["bookValue","trailingEps","priceToBook"]: d[k] = raw(dk, k)
        for k in ["payoutRatio","dividendYield","dividendRate","trailingPE"]: d[k] = raw(sd, k)
        return d
    fund = pull(codes, fnd_url, fnd_parse, 8, "財務指標")

    def hst_url(c):
        return "https://query2.finance.yahoo.com/v10/finance/quoteSummary/%s.T?modules=incomeStatementHistory&crumb=%s" % (c, cr)
    def hst_parse(j):
        inc = j["quoteSummary"]["result"][0].get("incomeStatementHistory", {}).get("incomeStatementHistory", [])
        return [raw(x, "netIncome") for x in inc]
    hist = pull(codes, hst_url, hst_parse, 8, "純利益推移")

    def vol_url(c):
        return "https://query1.finance.yahoo.com/v8/finance/chart/%s.T?range=1y&interval=1d" % c
    def vol_parse(j):
        cl = [x for x in j["chart"]["result"][0]["indicators"]["quote"][0]["close"] if x]
        if len(cl) < 30: return {}
        rs = [math.log(cl[i] / cl[i - 1]) for i in range(1, len(cl)) if cl[i - 1] > 0]
        m = sum(rs) / len(rs)
        sd = (sum((x - m) ** 2 for x in rs) / (len(rs) - 1)) ** .5
        return {"vol": round(sd * math.sqrt(252) * 100, 1), "ret1y": round((cl[-1] / cl[0] - 1) * 100, 1)}
    vol = pull(codes, vol_url, vol_parse, 8, "ボラティリティ")

    sectors = sorted({u["sector"] for u in uni})
    SI = {s: i for i, s in enumerate(sectors)}
    def R(v, n=1):
        v = N(v)
        return None if v is None else round(v, n)
    rows = []
    for u in uni:
        c = u["code"]; qq = quotes.get(c, {}); fd = fund.get(c, {}); vv = vol.get(c, {})
        price, mcap = N(qq.get("regularMarketPrice")), N(qq.get("marketCap"))
        if not price or not mcap: continue
        eps = N(qq.get("epsTrailingTwelveMonths")) or N(fd.get("trailingEps"))
        bps = N(qq.get("bookValue")) or N(fd.get("bookValue"))
        per = N(qq.get("trailingPE")) or N(fd.get("trailingPE")) or (price / eps if eps and eps > 0 else None)
        pbr = N(qq.get("priceToBook")) or N(fd.get("priceToBook")) or (price / bps if bps and bps > 0 else None)
        div = N(qq.get("trailingAnnualDividendYield")) or N(fd.get("dividendYield"))
        if div is None and N(fd.get("dividendRate")): div = N(fd["dividendRate"]) / price
        if div is not None and div > 1: div = div / 100.0
        roe = N(fd.get("returnOnEquity"))
        if roe is None and eps and bps and bps > 0: roe = eps / bps
        roa, opm = N(fd.get("returnOnAssets")), N(fd.get("operatingMargins"))
        eq = roa / roe * 100 if (roe and roa and roe > 0 and roa > 0 and roa <= roe) else None
        ni = [N(x) for x in (hist.get(c) or []) if N(x) is not None]
        nittm = mcap / per if (per and per > 0) else (ni[0] if ni else None)
        debt = N(fd.get("totalDebt"))
        dy = debt / nittm if (debt is not None and nittm and nittm > 0) else None
        upR = upD = None
        if len(ni) >= 2:
            upD = len(ni) - 1
            upR = round(sum(1 for i in range(upD) if ni[i] > ni[i + 1]) / upD * 100)
        fcf = N(fd.get("freeCashflow"))
        payout = N(fd.get("payoutRatio"))
        rows.append([c, u["name"], MK.get(u["mkt"], 0), SI[u["sector"]], R(price, 1), R(mcap / 1e8, 0),
                     R(per, 2), R(pbr, 2), R(div * 100 if div is not None else None, 2),
                     R(roe * 100 if roe is not None else None, 2), R(roa * 100 if roa is not None else None, 2),
                     R(opm * 100 if opm is not None else None, 2), R(eq, 1), R(dy, 1), upR, upD,
                     None if fcf is None else (1 if fcf > 0 else 0),
                     R(fcf / mcap * 100, 1) if fcf is not None else None,
                     R(payout * 100 if payout is not None else None, 1),
                     vv.get("vol"), R(eps, 2), R(bps, 2), vv.get("ret1y"), None, None])
    asof = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d")
    js = "window.JPDATA=" + json.dumps({"asof": asof, "sectors": sectors, "rows": rows},
                                       ensure_ascii=False, separators=(',', ':')) + ";"
    with open("jpdata.js", "w", encoding="utf-8") as f:
        f.write(js)
    print("jpdata.js を書き出しました: %d 銘柄 / %d bytes / asof %s" % (len(rows), len(js), asof))

if __name__ == "__main__":
    main()
