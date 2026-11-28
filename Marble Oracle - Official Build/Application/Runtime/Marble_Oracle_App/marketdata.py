"""marketdata.py -- optional AUD markets layer for Marble_Oracle (stdlib only).

MarketData(allow_net).snapshot() -> {sym: {"price", "pct", "series", "sim"}}
for BTC, USD (AUD per 1 USD), XAU (AUD / oz), XAG (AUD / oz).

* Polls in ONE background thread; the UI only ever reads snapshot().
* Every symbol degrades on its own: a failed fetch falls back to a clearly
  flagged simulation ("sim": True -> the panel header shows SIM).  A real
  series older than 30 minutes is reported the same way, so a dropped feed
  cannot stay LIVE.  Nothing here
  is investment information; the simulated numbers are decoration.
* The endpoints below are public, key-less APIs.  If the host cannot reach them
  (offline, firewall, --no-network) the module just simulates.
"""
import json
import random
import threading
import time
import urllib.request

SYMS = ("BTC", "USD", "XAU", "XAG")
BASE = {"BTC": 114029.0, "USD": 1.4042, "XAU": 6148.99, "XAG": 93.21}
VOL = {"BTC": 0.004, "USD": 0.0008, "XAU": 0.0015, "XAG": 0.003}
COINGECKO = {"BTC": "bitcoin", "XAU": "pax-gold", "XAG": "kinesis-silver"}
N = 28
STALE_S = 30 * 60          # a real series older than this is reported as sim: the header must not keep saying LIVE
UA = {"User-Agent": "Marble_Oracle (desktop toy; stdlib urllib)"}
MAX_BYTES = 2 * 1024 * 1024


def _get(url, timeout=8):
    if not url.lower().startswith("https://"):
        raise ValueError("only https market sources are allowed")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read(MAX_BYTES + 1)                 # a misbehaving server cannot fill memory
    if len(raw) > MAX_BYTES:
        raise ValueError("market response too large")
    return json.loads(raw.decode("utf-8", "replace"))


def _thin(series, n=N):
    if len(series) <= n:
        return list(series)
    step = (len(series) - 1) / float(n - 1)
    return [series[int(round(i * step))] for i in range(n)]


def fetch_coingecko(sym):
    d = _get("https://api.coingecko.com/api/v3/coins/%s/market_chart?vs_currency=aud&days=1"
             % COINGECKO[sym])
    s = [float(p[1]) for p in d["prices"]]
    if len(s) < 4:
        raise ValueError("short series")
    return _thin(s)


def fetch_usd():
    end = time.strftime("%Y-%m-%d")
    start = time.strftime("%Y-%m-%d", time.gmtime(time.time() - 10 * 86400))
    d = _get("https://api.frankfurter.app/%s..%s?from=USD&to=AUD" % (start, end))
    s = [float(v["AUD"]) for _, v in sorted(d["rates"].items())]
    if len(s) < 2:
        raise ValueError("short series")
    return s


class MarketData:
    def __init__(self, allow_net=True, seed=None):
        self.allow_net = allow_net
        self.lock = threading.Lock()
        self.rng = random.Random(seed)
        self.data = {}
        for s in SYMS:
            self.data[s] = self._sim_series(s, None)
        self._stop = False
        self._th = None
        self.last_ok = {}

    # -- simulation ----------------------------------------------------------
    def _sim_series(self, sym, start):
        v = start or BASE[sym] * (1 + self.rng.uniform(-0.01, 0.01))
        out = []
        for _ in range(N):
            v *= 1 + self.rng.gauss(0, VOL[sym])
            out.append(v)
        return {"series": out, "sim": True}

    def _tick_sim(self, sym):
        d = self.data[sym]
        if not d["sim"]:
            return
        v = d["series"][-1] * (1 + self.rng.gauss(0, VOL[sym]))
        d["series"] = d["series"][1:] + [v]

    # -- public --------------------------------------------------------------
    def start(self):
        if self._th is None:
            self._th = threading.Thread(target=self._loop, daemon=True)
            self._th.start()

    def stop(self):
        self._stop = True

    def _fresh(self, sym, now):
        ok = self.last_ok.get(sym)
        return ok is not None and (now - ok) <= STALE_S

    def snapshot(self):
        now = time.time()
        with self.lock:
            out = {}
            for s in SYMS:
                d = self.data[s]
                ser = list(d["series"])
                pct = (ser[-1] / ser[0] - 1.0) * 100.0 if ser[0] else 0.0
                sim = bool(d["sim"]) or not self._fresh(s, now)
                out[s] = {"price": ser[-1], "pct": pct, "series": ser, "sim": sim}
            return out

    def any_sim(self):
        now = time.time()
        with self.lock:
            return any(d["sim"] or not self._fresh(s, now) for s, d in self.data.items())

    # -- thread --------------------------------------------------------------
    def _loop(self):
        nxt = 0.0
        while not self._stop:
            now = time.time()
            if self.allow_net and now >= nxt:
                nxt = now + 120.0
                self._poll()
            with self.lock:
                for s in SYMS:
                    self._tick_sim(s)
            time.sleep(3.0)

    def _poll(self):
        for s in SYMS:
            try:
                ser = fetch_usd() if s == "USD" else fetch_coingecko(s)
                with self.lock:
                    self.data[s] = {"series": ser, "sim": False}
                    self.last_ok[s] = time.time()
            except Exception:
                with self.lock:
                    if not self.data[s]["sim"]:
                        continue            # keep the last real series
            time.sleep(1.5)                 # be polite to free APIs


def fmt_price(sym, v):
    if sym == "USD":
        return "%.4f" % v
    if v >= 10000:
        return "%s" % format(int(round(v)), ",")
    if v >= 1000:
        return "%s" % format(round(v, 2), ",.2f")
    return "%.2f" % v


def fmt_pct(p):
    return "%+.2f%%" % p


if __name__ == "__main__":
    m = MarketData(allow_net=False, seed=1)
    for k, v in m.snapshot().items():
        print(k, fmt_price(k, v["price"]), fmt_pct(v["pct"]), "SIM" if v["sim"] else "LIVE")
