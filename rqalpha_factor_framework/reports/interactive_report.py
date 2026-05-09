import argparse
import json
import pickle
from collections.abc import Mapping
from numbers import Real
from pathlib import Path

import pandas as pd


def _default_output_path(result_path):
    return result_path.with_name("{}_report.html".format(result_path.stem))


def _load_result(path):
    with Path(path).open("rb") as result_file:
        result = pickle.load(result_file)
    if not isinstance(result, Mapping):
        raise ValueError("result pickle must contain a mapping")
    if "portfolio" not in result or not hasattr(result["portfolio"], "copy"):
        raise ValueError("result pickle must contain portfolio data")
    return result


def _date_index(frame):
    index = pd.to_datetime(frame.index)
    return index.strftime("%Y-%m-%d")


def _return_series(frame):
    values = pd.to_numeric(frame["unit_net_value"], errors="coerce") - 1
    return [
        {"date": date, "return": None if pd.isna(value) else float(value)}
        for date, value in zip(_date_index(frame), values)
    ]


def _money(value):
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _format_summary_value(value):
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, Real) and not pd.isna(value):
        return "{:.2f}".format(float(value))
    return str(value)


def _trade_datetime_column(trades):
    for column in ("trading_datetime", "datetime"):
        if column in trades.columns:
            return column
    return None


def _trade_rows(group):
    rows = []
    for _, trade in group.iterrows():
        quantity = _money(trade.get("last_quantity", 0.0))
        price = _money(trade.get("last_price", 0.0))
        rows.append(
            {
                "order_book_id": str(trade.get("order_book_id", "")),
                "symbol": str(trade.get("symbol", "")),
                "side": str(trade.get("side", "")),
                "position_effect": str(trade.get("position_effect", "")),
                "quantity": quantity,
                "price": price,
                "value": quantity * price,
                "transaction_cost": _money(trade.get("transaction_cost", 0.0)),
            }
        )
    return rows


def _enriched_trades(trades):
    trades = trades.copy()
    trades["_quantity"] = pd.to_numeric(
        trades.get("last_quantity", 0.0), errors="coerce"
    ).fillna(0.0)
    trades["_price"] = pd.to_numeric(
        trades.get("last_price", 0.0), errors="coerce"
    ).fillna(0.0)
    trades["_value"] = trades["_quantity"] * trades["_price"]
    trades["_cost"] = pd.to_numeric(
        trades.get("transaction_cost", 0.0), errors="coerce"
    ).fillna(0.0)
    trades["_side"] = trades.get("side", "").astype(str).str.upper()
    return trades


def _aggregate_rebalance_events(trades, strategy_by_date, benchmark_by_date):
    if not hasattr(trades, "empty") or trades.empty:
        return []

    trades = _enriched_trades(trades)
    datetime_column = _trade_datetime_column(trades)
    if datetime_column is None:
        trade_dates = pd.to_datetime(trades.index, errors="coerce")
    else:
        trade_dates = pd.to_datetime(trades[datetime_column], errors="coerce")
    trades["_event_date"] = trade_dates.dt.strftime("%Y-%m-%d")
    trades = trades.dropna(subset=["_event_date"])
    if trades.empty:
        return []

    events = []
    for date, group in trades.groupby("_event_date", sort=True):
        rows = _trade_rows(group)
        buys = [row for row in rows if row["side"].upper() == "BUY"]
        sells = [row for row in rows if row["side"].upper() == "SELL"]
        events.append(
            {
                "date": date,
                "strategy_return": strategy_by_date.get(date),
                "benchmark_return": benchmark_by_date.get(date),
                "excess_return": (
                    None
                    if benchmark_by_date.get(date) is None
                    else strategy_by_date.get(date, 0.0) - benchmark_by_date[date]
                ),
                "buy_count": len(buys),
                "sell_count": len(sells),
                "buy_value": sum(row["value"] for row in buys),
                "sell_value": sum(row["value"] for row in sells),
                "transaction_cost": sum(row["transaction_cost"] for row in rows),
                "transaction_cost_label": "{:.2f}".format(
                    sum(row["transaction_cost"] for row in rows)
                ),
                "buys": buys,
                "sells": sells,
            }
        )
    return events


def _summary_rows(summary):
    fields = [
        ("策略", "strategy_name"),
        ("起始日期", "start_date"),
        ("结束日期", "end_date"),
        ("总收益", "total_returns"),
        ("年化收益", "annualized_returns"),
        ("最大回撤", "max_drawdown"),
        ("Sharpe", "sharpe"),
        ("换手率", "turnover"),
    ]
    rows = []
    for label, key in fields:
        if key in summary:
            rows.append({"label": label, "value": _format_summary_value(summary[key])})
    return rows


def _latest_position_values(positions):
    if not hasattr(positions, "empty") or positions.empty:
        return {}

    positions = positions.copy()
    positions.index = pd.to_datetime(positions.index)
    latest = positions.loc[positions.index.max()]
    if isinstance(latest, pd.Series):
        latest = latest.to_frame().T
    else:
        latest = latest.copy()
    if "order_book_id" not in latest or "market_value" not in latest:
        return {}

    latest["market_value"] = pd.to_numeric(latest["market_value"], errors="coerce")
    return (
        latest.dropna(subset=["order_book_id"])
        .groupby("order_book_id")["market_value"]
        .sum()
        .fillna(0.0)
        .to_dict()
    )


def _traded_symbol_returns(trades, positions):
    if not hasattr(trades, "empty") or trades.empty:
        return []

    trades = _enriched_trades(trades)
    if "order_book_id" not in trades:
        return []

    latest_values = _latest_position_values(positions)
    rows = []
    for order_book_id, group in trades.groupby("order_book_id", sort=True):
        symbol_values = [
            str(value)
            for value in group.get("symbol", pd.Series(dtype=object)).dropna()
            if str(value)
        ]
        buys = group[group["_side"] == "BUY"]
        sells = group[group["_side"] == "SELL"]
        buy_value = float(buys["_value"].sum())
        sell_value = float(sells["_value"].sum())
        final_market_value = float(latest_values.get(order_book_id, 0.0))
        transaction_cost = float(group["_cost"].sum())
        pnl = sell_value + final_market_value - buy_value - transaction_cost
        return_rate = pnl / buy_value if buy_value > 0 else None
        rows.append(
            {
                "order_book_id": str(order_book_id),
                "symbol": symbol_values[0] if symbol_values else "",
                "buy_value": buy_value,
                "sell_value": sell_value,
                "final_market_value": final_market_value,
                "transaction_cost": transaction_cost,
                "pnl": pnl,
                "return_rate": return_rate,
                "return_label": "-" if return_rate is None else "{:.2%}".format(return_rate),
            }
        )

    return sorted(
        rows,
        key=lambda row: (
            row["return_rate"] is None,
            0.0 if row["return_rate"] is None else -row["return_rate"],
        ),
    )


def _build_payload(result):
    portfolio = result["portfolio"].copy()
    strategy_data = _return_series(portfolio)
    benchmark_frame = result.get("benchmark_portfolio")
    benchmark_data = (
        _return_series(benchmark_frame)
        if benchmark_frame is not None and hasattr(benchmark_frame, "copy")
        else []
    )
    strategy_by_date = {item["date"]: item["return"] for item in strategy_data}
    benchmark_by_date = {item["date"]: item["return"] for item in benchmark_data}
    events = _aggregate_rebalance_events(
        result.get("trades", pd.DataFrame()),
        strategy_by_date,
        benchmark_by_date,
    )
    return {
        "strategyData": strategy_data,
        "benchmarkData": benchmark_data,
        "rebalanceEvents": events,
        "summaryRows": _summary_rows(result.get("summary", {})),
        "tradedSymbolReturns": _traded_symbol_returns(
            result.get("trades", pd.DataFrame()),
            result.get("stock_positions", pd.DataFrame()),
        ),
    }


def _json_script(name, value):
    content = json.dumps(value, ensure_ascii=False).replace("</", "<\\/")
    return "const {} = {};".format(name, content)


def _render_html(payload):
    scripts = "\n".join(
        [
            _json_script("strategyData", payload["strategyData"]),
            _json_script("benchmarkData", payload["benchmarkData"]),
            _json_script("rebalanceEvents", payload["rebalanceEvents"]),
            _json_script("summaryRows", payload["summaryRows"]),
            _json_script("tradedSymbolReturns", payload["tradedSymbolReturns"]),
        ]
    )
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>回测结果交互报告</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f7f8fa;
      --panel: #ffffff;
      --text: #172033;
      --muted: #667085;
      --line: #d8dee9;
      --strategy: #1f77b4;
      --benchmark: #f28e2b;
      --event: #d62728;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
      color: var(--text);
      background: var(--bg);
    }
    main {
      max-width: 1180px;
      margin: 0 auto;
      padding: 28px 24px 36px;
    }
    h1 {
      margin: 0 0 18px;
      font-size: 26px;
      font-weight: 700;
      letter-spacing: 0;
    }
    .summary {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 10px;
      margin-bottom: 18px;
    }
    .summary-item, .chart-wrap, .detail-panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
    }
    .summary-item { padding: 12px 14px; }
    .summary-label { color: var(--muted); font-size: 12px; }
    .summary-value { margin-top: 4px; font-size: 15px; font-weight: 650; overflow-wrap: anywhere; }
    .chart-wrap {
      position: relative;
      padding: 16px;
      min-height: 500px;
    }
    .chart-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 12px;
    }
    .chart-title h2 { margin: 0; font-size: 18px; }
    .legend { display: flex; gap: 14px; color: var(--muted); font-size: 13px; }
    .legend span::before {
      content: "";
      display: inline-block;
      width: 22px;
      height: 3px;
      margin-right: 6px;
      vertical-align: middle;
      border-radius: 99px;
      background: currentColor;
    }
    .legend .strategy { color: var(--strategy); }
    .legend .benchmark { color: var(--benchmark); }
    .legend .event { color: var(--event); }
    svg {
      width: 100%;
      height: 420px;
      display: block;
      overflow: visible;
    }
    .axis text { fill: var(--muted); font-size: 11px; }
    .axis line, .grid line { stroke: var(--line); }
    .line-path { fill: none; stroke-width: 2.5; }
    .event-marker {
      fill: var(--event);
      stroke: #fff;
      stroke-width: 2;
      cursor: pointer;
    }
    .tooltip {
      position: absolute;
      pointer-events: none;
      display: none;
      max-width: 360px;
      padding: 10px 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.97);
      box-shadow: 0 10px 28px rgba(16, 24, 40, 0.16);
      font-size: 12px;
      color: var(--text);
      z-index: 2;
    }
    .tooltip strong { display: block; margin-bottom: 6px; }
    .empty {
      color: var(--muted);
      margin-top: 10px;
      font-size: 13px;
    }
    .detail-panel {
      margin-top: 16px;
      padding: 16px;
    }
    .detail-panel h2 { margin: 0 0 10px; font-size: 18px; }
    .detail-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 8px;
      margin-bottom: 14px;
      color: var(--muted);
      font-size: 13px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
      margin-top: 8px;
    }
    th, td {
      padding: 8px 10px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      white-space: nowrap;
    }
    th { color: var(--muted); font-weight: 600; }
    .tables {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
      gap: 18px;
    }
    @media (max-width: 720px) {
      main { padding: 18px 12px 28px; }
      .chart-wrap { padding: 12px; }
      .chart-title { align-items: flex-start; flex-direction: column; }
      th, td { padding: 7px 6px; }
      .tables { grid-template-columns: 1fr; overflow-x: auto; }
    }
  </style>
</head>
<body>
  <main>
    <h1>回测结果交互报告</h1>
    <section class="summary" id="summary"></section>
    <section class="chart-wrap">
      <div class="chart-title">
        <h2>收益曲线</h2>
        <div class="legend">
          <span class="strategy">strategy</span>
          <span class="benchmark">benchmark</span>
          <span class="event">rebalance</span>
        </div>
      </div>
      <svg id="chart" role="img" aria-label="收益曲线和调仓记录"></svg>
      <div class="tooltip" id="tooltip"></div>
      <p class="empty" id="empty-events"></p>
    </section>
    <section class="detail-panel">
      <h2>调仓记录</h2>
      <div id="event-detail" class="empty">点击收益曲线上的调仓点查看明细。</div>
    </section>
    <section class="detail-panel">
      <h2>交易股票收益率</h2>
      <div id="symbol-returns"></div>
    </section>
  </main>
  <script>
{scripts}

const fmtPct = value => value === null || value === undefined ? "-" : `${(value * 100).toFixed(2)}%`;
const fmtMoney = value => Number(value || 0).toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const svg = document.getElementById("chart");
const tooltip = document.getElementById("tooltip");
const detail = document.getElementById("event-detail");

function renderSummary() {
  const target = document.getElementById("summary");
  target.innerHTML = summaryRows.map(row => `
    <div class="summary-item">
      <div class="summary-label">${row.label}</div>
      <div class="summary-value">${row.value}</div>
    </div>
  `).join("");
}

function eventHtml(event, compact=false) {
  const buyRows = event.buys.map(rowHtml).join("") || `<tr><td colspan="6">无买入</td></tr>`;
  const sellRows = event.sells.map(rowHtml).join("") || `<tr><td colspan="6">无卖出</td></tr>`;
  const header = `
    <div class="detail-grid">
      <div>日期：<strong>${event.date}</strong></div>
      <div>策略收益：<strong>${fmtPct(event.strategy_return)}</strong></div>
      <div>基准收益：<strong>${fmtPct(event.benchmark_return)}</strong></div>
      <div>超额收益：<strong>${fmtPct(event.excess_return)}</strong></div>
      <div>买入：<strong>${event.buy_count}</strong> 笔 / ${fmtMoney(event.buy_value)}</div>
      <div>卖出：<strong>${event.sell_count}</strong> 笔 / ${fmtMoney(event.sell_value)}</div>
      <div>交易成本：<strong>${fmtMoney(event.transaction_cost)}</strong></div>
    </div>`;
  if (compact) return `<strong>${event.date}</strong>${header}`;
  return `${header}
    <div class="tables">
      <div><h3>买入</h3><table><thead>${tableHead()}</thead><tbody>${buyRows}</tbody></table></div>
      <div><h3>卖出</h3><table><thead>${tableHead()}</thead><tbody>${sellRows}</tbody></table></div>
    </div>`;
}

function tableHead() {
  return "<tr><th>代码</th><th>名称</th><th>方向</th><th>数量</th><th>价格</th><th>成交额</th></tr>";
}

function rowHtml(row) {
  return `<tr>
    <td>${row.order_book_id}</td>
    <td>${row.symbol}</td>
    <td>${row.side}</td>
    <td>${Number(row.quantity || 0).toLocaleString("zh-CN")}</td>
    <td>${Number(row.price || 0).toFixed(2)}</td>
    <td>${fmtMoney(row.value)}</td>
  </tr>`;
}

function renderSymbolReturns() {
  const target = document.getElementById("symbol-returns");
  if (!tradedSymbolReturns.length) {
    target.className = "empty";
    target.textContent = "无交易股票收益率";
    return;
  }
  target.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>代码</th><th>名称</th><th>收益率</th><th>盈亏</th>
          <th>买入额</th><th>卖出额</th><th>期末市值</th><th>交易成本</th>
        </tr>
      </thead>
      <tbody>
        ${tradedSymbolReturns.map(row => `
          <tr>
            <td>${row.order_book_id}</td>
            <td>${row.symbol}</td>
            <td>${row.return_label}</td>
            <td>${fmtMoney(row.pnl)}</td>
            <td>${fmtMoney(row.buy_value)}</td>
            <td>${fmtMoney(row.sell_value)}</td>
            <td>${fmtMoney(row.final_market_value)}</td>
            <td>${fmtMoney(row.transaction_cost)}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>`;
}

function renderChart() {
  const width = svg.clientWidth || 1000;
  const height = 420;
  const margin = { top: 18, right: 28, bottom: 42, left: 58 };
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.innerHTML = "";
  if (!strategyData.length) return;

  const dates = strategyData.map(d => d.date);
  const dateIndex = new Map(dates.map((date, index) => [date, index]));
  const allValues = strategyData.concat(benchmarkData).map(d => d.return).filter(v => v !== null && Number.isFinite(v));
  const minY = Math.min(...allValues, 0);
  const maxY = Math.max(...allValues, 0);
  const yPad = Math.max((maxY - minY) * 0.08, 0.02);
  const domainMin = minY - yPad;
  const domainMax = maxY + yPad;
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;
  const x = index => margin.left + (dates.length <= 1 ? 0 : index / (dates.length - 1) * innerW);
  const y = value => margin.top + (domainMax - value) / (domainMax - domainMin) * innerH;
  const pathFor = data => data.map((d, i) => `${i === 0 ? "M" : "L"}${x(dateIndex.get(d.date))},${y(d.return || 0)}`).join(" ");

  for (let i = 0; i <= 4; i += 1) {
    const value = domainMin + (domainMax - domainMin) * i / 4;
    const yy = y(value);
    svg.insertAdjacentHTML("beforeend", `<g class="grid"><line x1="${margin.left}" y1="${yy}" x2="${width - margin.right}" y2="${yy}"></line></g>`);
    svg.insertAdjacentHTML("beforeend", `<g class="axis"><text x="${margin.left - 8}" y="${yy + 4}" text-anchor="end">${fmtPct(value)}</text></g>`);
  }
  const tickIndexes = [0, Math.floor((dates.length - 1) / 2), dates.length - 1];
  tickIndexes.forEach(i => {
    svg.insertAdjacentHTML("beforeend", `<g class="axis"><text x="${x(i)}" y="${height - 12}" text-anchor="middle">${dates[i]}</text></g>`);
  });

  svg.insertAdjacentHTML("beforeend", `<path class="line-path" stroke="var(--strategy)" d="${pathFor(strategyData)}"></path>`);
  if (benchmarkData.length) {
    svg.insertAdjacentHTML("beforeend", `<path class="line-path" stroke="var(--benchmark)" d="${pathFor(benchmarkData)}"></path>`);
  }

  if (!rebalanceEvents.length) {
    document.getElementById("empty-events").textContent = "无调仓记录";
    detail.textContent = "无调仓记录";
    return;
  }
  document.getElementById("empty-events").textContent = "";
  rebalanceEvents.forEach((event, eventIndex) => {
    const i = dateIndex.get(event.date);
    if (i === undefined || event.strategy_return === null || event.strategy_return === undefined) return;
    const cx = x(i);
    const cy = y(event.strategy_return);
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("class", "event-marker");
    circle.setAttribute("cx", cx);
    circle.setAttribute("cy", cy);
    circle.setAttribute("r", 5);
    circle.dataset.eventIndex = String(eventIndex);
    circle.addEventListener("mousemove", evt => showTooltip(evt, event));
    circle.addEventListener("mouseleave", hideTooltip);
    circle.addEventListener("click", () => showDetail(event));
    svg.appendChild(circle);
  });
  showDetail(rebalanceEvents[0]);
}

function showTooltip(evt, event) {
  tooltip.innerHTML = eventHtml(event, true);
  tooltip.style.display = "block";
  const bounds = document.querySelector(".chart-wrap").getBoundingClientRect();
  tooltip.style.left = `${evt.clientX - bounds.left + 12}px`;
  tooltip.style.top = `${evt.clientY - bounds.top + 12}px`;
}

function hideTooltip() {
  tooltip.style.display = "none";
}

function showDetail(event) {
  detail.className = "";
  detail.innerHTML = eventHtml(event);
}

renderSummary();
renderSymbolReturns();
renderChart();
window.addEventListener("resize", renderChart);
  </script>
</body>
</html>
""".replace("{scripts}", scripts)


def generate_interactive_report(result_path, output_path=None):
    result_path = Path(result_path)
    output_path = Path(output_path) if output_path is not None else _default_output_path(result_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    result = _load_result(result_path)
    html = _render_html(_build_payload(result))
    output_path.write_text(html, encoding="utf-8")
    return output_path


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate an interactive HTML report from an RQAlpha result pickle."
    )
    parser.add_argument("result_path")
    parser.add_argument("-o", "--output", dest="output_path")
    return parser.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv)
    output_path = generate_interactive_report(args.result_path, args.output_path)
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
