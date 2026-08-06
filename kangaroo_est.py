#!/usr/bin/env python3
"""Runtime / cost / DP-storage estimator for Pollard-kangaroo attacks on the
Bitcoin puzzle addresses that have an exposed public key (every 5th puzzle,
75..160).

Work model
----------
Puzzle n has its private key uniformly in [2^(n-1), 2^n), so the interval
width is W = 2^(n-1) and the expected number of secp256k1 group operations is

    ops = K * sqrt(W) = K * 2^((n-1)/2)

K = 1.15 for the SOTA 3-kangaroo-with-symmetry method (RCKangaroo,
PSCKangaroo, collider). Classic JeanLucPons Kangaroo is K ~= 1.6-2.1 AND is
capped at a 125-bit interval, so it cannot run puzzle 130 and up at all.

sqrt(W) is the generic-group lower bound (Shoup). There is no known sub-sqrt
attack on secp256k1 ECDLP, so the op count is a floor, not an estimate. The
only lever is operations per dollar.
"""

import argparse
import math

K_SOTA = 1.15   # RCKangaroo SOTA (3 kangaroo types + symmetry + loop handling)
K_3WAY = 1.6    # RCKangaroo 3-way
K_JLP = 2.08    # JeanLucPons Kangaroo, per its own README ("2.08*sqrt(k2-k1)")

SECONDS_PER_YEAR = 365.25 * 24 * 3600
HOURS_PER_YEAR = 365.25 * 24

# (GKeys/s, watts). 4090/5090 are RCKangaroo's own published figures; the rest
# are scaled estimates and are NOT measured.
# CALIBRATE. RCKangaroo prints real GKeys/s on startup -- clocks, driver,
# cooling and the chosen -dp move it 20%+. Paper numbers lie.
GPUS = {
    "rtx3090": (6.0, 350),    # estimated
    "rtx4080": (9.0, 320),    # estimated
    "rtx4090": (14.5, 450),   # measured, RCKangaroo README
    "rtx5090": (19.3, 575),   # measured, RCKangaroo README (turbo kernels)
    "a100": (8.0, 400),       # estimated
    "h100": (15.0, 700),      # estimated
}

# JeanLucPons measured the DP overhead against r = nbKangaroo * 2^dp / sqrt(N):
# r=4.0 -> 71% wasted, r=0.125 -> 4% wasted. overhead ~= 0.18*r fits that.
# Using the measured curve, not a hand-waved fraction of total work.
DP_OVERHEAD_SLOPE = 0.18


def expected_ops(n, k=K_SOTA):
    """Expected group operations to solve puzzle n."""
    return k * 2.0 ** ((n - 1) / 2.0)


# Already swept: 1..70 plus every 5th from 75 to 130. Their coins are gone, so
# the prize column is the schedule value, not money you can win.
SOLVED = set(range(1, 71)) | set(range(75, 131, 5))


def prize_btc(n):
    """Reward held by puzzle n after the 2023 top-up (0.1 * n BTC for 51..160)."""
    return round(0.1 * n, 1)


def dp_overhead(n, kangaroos, d):
    """Fraction of work wasted on DP tails, per JeanLucPons' measured curve."""
    r = kangaroos * 2.0 ** d / 2.0 ** ((n - 1) / 2.0)
    return DP_OVERHEAD_SLOPE * r


def dp_window(n, kangaroos, ram_bytes, dp_entry_bytes=16, overhead_frac=0.05,
              k=K_SOTA):
    """Feasible range of DP bits d.

    Lower bound from RAM: stored distinguished points ~= ops / 2^d, so a small
    d means a huge table. Upper bound from overhead: each kangaroo walks an
    extra ~2^d steps to reach a DP, and JLP's measured curve puts the waste at
    ~0.18 * kangaroos * 2^d / sqrt(W).

    Returns (d_min, d_max). d_min > d_max means infeasible as configured --
    more RAM, or a smaller herd.
    """
    ops = expected_ops(n, k)
    d_min = max(0.0, math.log2(ops * dp_entry_bytes / ram_bytes))
    sqrt_w = 2.0 ** ((n - 1) / 2.0)
    d_max = math.log2(overhead_frac * sqrt_w / (DP_OVERHEAD_SLOPE * kangaroos))
    return d_min, d_max


def estimate(n, gpu="rtx4090", count=1, gpu_speed=None, watts=None,
             usd_per_gpu_hour=0.35, usd_per_kwh=0.10, btc_usd=100_000.0,
             ram_gb=64.0, kangaroos_per_gpu=2 ** 21, dp_entry_bytes=16,
             k=K_SOTA):
    default_speed, default_watts = GPUS.get(gpu, (None, None))
    speed = gpu_speed if gpu_speed is not None else default_speed
    w = watts if watts is not None else default_watts
    if speed is None or w is None:
        missing = " and ".join(x for x, v in (("--speed", speed), ("--watts", w))
                               if v is None)
        raise SystemExit("gpu %r has no built-in profile -- pass %s" % (gpu, missing))

    ops = expected_ops(n, k)
    rate = speed * 1e9 * count            # ops/sec for the whole fleet
    seconds = ops / rate
    gpu_hours = (ops / (speed * 1e9)) / 3600.0

    rental = gpu_hours * usd_per_gpu_hour
    kwh = gpu_hours * (w / 1000.0)
    power = kwh * usd_per_kwh

    prize = prize_btc(n)
    value = prize * btc_usd

    d_min, d_max = dp_window(n, kangaroos_per_gpu * count,
                             ram_gb * 1024 ** 3, dp_entry_bytes, k=k)

    return {
        "puzzle": n,
        "interval_bits": n - 1,
        "ops": ops,
        "ops_log2": math.log2(ops),
        "fleet_rate": rate,
        "seconds": seconds,
        "years": seconds / SECONDS_PER_YEAR,
        "days": seconds / 86400.0,
        "gpu_years": gpu_hours / HOURS_PER_YEAR,
        "gpu_hours": gpu_hours,
        "rental_usd": rental,
        "kwh": kwh,
        "power_usd": power,
        "prize_btc": prize,
        "prize_usd": value,
        "roi_rental": value / rental if rental else float("inf"),
        "roi_power": value / power if power else float("inf"),
        "breakeven_btc_rental": rental / prize,
        "breakeven_btc_power": power / prize,
        "dp_min": d_min,
        "dp_max": d_max,
        "dp_feasible": d_min <= d_max,
        "dp_entries_at_min": ops / 2 ** d_min,
    }


def human_time(seconds):
    y = seconds / SECONDS_PER_YEAR
    if y >= 1:
        return "%.4g years" % y
    d = seconds / 86400.0
    if d >= 1:
        return "%.4g days" % d
    return "%.4g hours" % (seconds / 3600.0)


def report(r, gpu, count):
    solved = r["puzzle"] in SOLVED
    print("puzzle #%d   interval 2^%d   prize %.1f BTC%s"
          % (r["puzzle"], r["interval_bits"], r["prize_btc"],
             "   *** ALREADY SOLVED -- address swept, prize is $0 ***" if solved else ""))
    print("  expected ops        %.3g  (2^%.1f)" % (r["ops"], r["ops_log2"]))
    print("  fleet               %d x %s  =  %.4g ops/s"
          % (count, gpu, r["fleet_rate"]))
    print("  wall clock          %s" % human_time(r["seconds"]))
    print("  total GPU-years     %.4g" % r["gpu_years"])
    print("  rental cost         $%s" % f"{r['rental_usd']:,.0f}")
    print("  power only          $%s   (%.3g kWh)"
          % (f"{r['power_usd']:,.0f}", r["kwh"]))
    print("  prize value         $%s   at $%s/BTC"
          % (f"{r['prize_usd']:,.0f}", f"{r['prize_usd']/r['prize_btc']:,.0f}"))
    print("  ROI vs rental       %.3gx %s"
          % (r["roi_rental"], "PROFIT" if r["roi_rental"] > 1 else "LOSS"))
    print("  ROI vs power only   %.3gx %s"
          % (r["roi_power"], "PROFIT" if r["roi_power"] > 1 else "LOSS"))
    print("  break-even BTC      $%s rental / $%s power-only"
          % (f"{r['breakeven_btc_rental']:,.0f}",
             f"{r['breakeven_btc_power']:,.0f}"))
    if solved:
        print("  NOTE                every ROI line above is fiction: this puzzle is")
        print("                      solved and the coins are already spent.")
    if r["dp_feasible"]:
        print("  usable -dp          %d .. %d  (%.3g DP entries at dp=%d)"
              % (math.ceil(r["dp_min"]), math.floor(r["dp_max"]),
                 r["dp_entries_at_min"], math.ceil(r["dp_min"])))
    else:
        print("  usable -dp          NONE: RAM floor dp>=%.1f exceeds overhead "
              "ceiling dp<=%.1f -- add RAM or shrink the herd"
              % (r["dp_min"], r["dp_max"]))
    # ponytail: point estimate only. Kangaroo runtime has real variance -- a run
    # can finish well under or over expected ops. Not modelled; treat as a mean.


def compare(puzzles, **kw):
    print("%-8s %-10s %-12s %-12s %-14s %-10s" %
          ("puzzle", "ops log2", "GPU-years", "rental $", "prize BTC", "ROI"))
    for n in puzzles:
        r = estimate(n, **kw)
        print("%-8d %-10.1f %-12.4g %-12s %-14.1f %-10.3g"
              % (n, r["ops_log2"], r["gpu_years"],
                 f"{r['rental_usd']:,.0f}", r["prize_btc"], r["roi_rental"]))


def demo():
    # Published figure for #135: ~1.15 * sqrt(2^134) ~= 1.7e20 ops (2^67.2).
    o135 = expected_ops(135)
    assert 1.6e20 < o135 < 1.8e20, o135
    assert abs(math.log2(o135) - 67.2) < 0.1

    # Each +1 on the puzzle number is sqrt(2) more work; +5 is 2^2.5 = 5.657x.
    assert abs(expected_ops(140) / expected_ops(135) - 2 ** 2.5) < 1e-9
    assert abs(expected_ops(140) / expected_ops(130) - 2 ** 5) < 1e-9

    # Prize schedule after the 2023 top-up.
    assert prize_btc(66) == 6.6 and prize_btc(140) == 14.0
    # Solved set must cover the swept ranges and exclude the live targets.
    assert 66 in SOLVED and 120 in SOLVED and 130 in SOLVED
    assert 135 not in SOLVED and 140 not in SOLVED and 71 not in SOLVED

    # #130 on a single 4090 (14.5 GH/s) is ~65 GPU-years; #140 is 32x that.
    r130 = estimate(130)
    r140 = estimate(140)
    assert 55 < r130["gpu_years"] < 80, r130["gpu_years"]
    assert abs(r140["gpu_years"] / r130["gpu_years"] - 32) < 1e-6

    # JLP's K=2.08 costs 1.81x more work than SOTA's K=1.15 -- matches
    # RCKangaroo's "1.8 times less required operations" claim.
    assert abs(expected_ops(140, K_JLP) / expected_ops(140, K_SOTA) - 1.809) < 0.01

    # JLP's own measured DP overhead: r=4.0 -> ~71% wasted.
    sqrt_w = 2.0 ** ((140 - 1) / 2.0)
    kang = 4.0 * sqrt_w / 2.0 ** 30
    assert abs(dp_overhead(140, kang, 30) - 0.72) < 0.02

    # Fleet size divides wall clock but never total GPU-hours.
    solo = estimate(140, count=1)
    fleet = estimate(140, count=1000)
    assert abs(solo["gpu_hours"] - fleet["gpu_hours"]) < 1e-3
    assert abs(solo["seconds"] / fleet["seconds"] - 1000) < 1e-6

    # DP window: more RAM lowers the floor, a bigger herd lowers the ceiling.
    lo, hi = dp_window(140, 2 ** 21, 64 * 1024 ** 3)
    lo_more_ram, _ = dp_window(140, 2 ** 21, 512 * 1024 ** 3)
    _, hi_big_herd = dp_window(140, 2 ** 30, 64 * 1024 ** 3)
    assert lo_more_ram < lo and hi_big_herd < hi
    assert lo <= hi, "expected 64GB/2^21 to be feasible at #140"

    print("self-check OK")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("puzzle", nargs="?", type=int, default=140)
    p.add_argument("--gpu", default="rtx4090", choices=sorted(GPUS) + ["custom"])
    p.add_argument("--count", type=int, default=1, help="number of GPUs")
    p.add_argument("--speed", type=float, help="GKeys/s per GPU (overrides preset)")
    p.add_argument("--watts", type=float, help="watts per GPU (overrides preset)")
    p.add_argument("--rate", type=float, default=0.35, help="USD per GPU-hour")
    p.add_argument("--kwh", type=float, default=0.10, help="USD per kWh")
    p.add_argument("--btc", type=float, default=100_000.0, help="assumed BTC price")
    p.add_argument("--ram", type=float, default=64.0, help="host RAM in GB for DPs")
    p.add_argument("--kangaroos", type=int, default=2 ** 21,
                   help="concurrent kangaroos per GPU (see solver output)")
    p.add_argument("--dp-bytes", type=int, default=16,
                   help="bytes per stored DP (16 = PSCKangaroo compact, 32 = RCKangaroo)")
    p.add_argument("--k", type=float, default=K_SOTA,
                   help="method constant: 1.15 SOTA, 1.6 3-way, 2.08 JeanLucPons")
    p.add_argument("--compare", action="store_true",
                   help="table across 130/135/140/145/150")
    p.add_argument("--self-check", action="store_true")
    a = p.parse_args()

    if a.self_check:
        demo()
        raise SystemExit(0)

    kw = dict(gpu=a.gpu, count=a.count, gpu_speed=a.speed, watts=a.watts,
              usd_per_gpu_hour=a.rate, usd_per_kwh=a.kwh, btc_usd=a.btc,
              ram_gb=a.ram, kangaroos_per_gpu=a.kangaroos, dp_entry_bytes=a.dp_bytes,
              k=a.k)

    if a.compare:
        compare([130, 135, 140, 145, 150], **kw)
    else:
        report(estimate(a.puzzle, **kw), a.gpu, a.count)
