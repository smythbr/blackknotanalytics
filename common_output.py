"""
common_output.py
----------------
Shared OUTPUT framework for every Black Knot model. One presentation-neutral
view-model (an ordered set of BLOCKS) feeds multiple RENDERERS (terminal now;
JSON/website in Stage 2). Renderers project blocks onto a surface — they select
and format, they never compute. So terminal and website draw from the same data
and cannot disagree.

Design goals (in priority order):
  1. MODULAR BLOCKS. A block is an independent unit (an id + a list of
     presentation PRIMITIVES + a visibility flag). The gateway holds an ordered
     list of blocks; renderers iterate them generically and never hardcode which
     blocks exist. Adding / consolidating blocks later touches only the block
     builders, never the renderers.
  2. FORMAT IS COMMON, ONE HOME PER SURFACE. The look/feel (widths, colours,
     number formats, the "—" for missing) lives in the renderer, so every block
     and every app share one consistent appearance. Blocks describe *what* to
     show (a comparison table, a header, a status banner); the renderer owns
     *how it looks*.
  3. DISCLOSURE IS CONFIG, NOT CODE. Apps decide, per surface, what to reveal:
     block VISIBILITY (skip a block on a surface), and label MASKING (project a
     label through a substitution map — e.g. Hedra's A/B/C/D — applied at render
     time). IP enforcement lives in the APP, never here; this layer is
     IP-agnostic and just renders what it is handed.

Primitives (the small shared vocabulary — extend as real needs arise):
  Rule        — a horizontal divider
  Header      — titled banner between rules, with an OK tick
  KV          — a label : value line (value may be toned)
  Banner      — a status line (e.g. action / no-action)
  Table       — a comparison table: optional column header + labelled rows of
                cells; each cell is (value, kind) and the renderer formats by
                kind (scalar / weight / ret), including sign-based colour
  Blank       — a blank line

Copyright (c) 2026 Black Knot Analytics. All rights reserved.
Author: Brendan P. Smyth
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Any, Callable


# ── Presentation primitives (the shared vocabulary) ───────────────────────────

@dataclass
class Rule:
    pass


@dataclass
class Blank:
    pass


@dataclass
class Header:
    title: str
    ok: bool = True


@dataclass
class KV:
    label: str
    value: str
    tone: Optional[str] = None      # 'risk_on' | 'risk_off' | None
    width: int = 14                 # label field width (app may override)


@dataclass
class Banner:
    text: str
    tone: Optional[str] = None      # 'action' | 'noaction' | None


# A cell is (value, kind). kind ∈ {'scalar','weight','ret'}; value may be None.
Cell = Tuple[Any, str]
Row  = Tuple[str, List[Cell]]       # (label, cells)


@dataclass
class Table:
    rows: List[Row]
    header: Optional[Tuple[str, ...]] = None   # e.g. ("Scalar","Today","Prior")


Primitive = Any   # one of the above


@dataclass
class Block:
    """A modular, independent presentation unit."""
    id: str
    elements: List[Primitive] = field(default_factory=list)
    visible: bool = True


# ── Terminal renderer (owns the terminal look/feel — one home) ────────────────

class TerminalRenderer:
    """Projects blocks onto the terminal. All terminal format constants and
    colour logic live here, so every block/app shares one appearance."""

    LBL_W = 14
    COL_W = 9
    BLK_W = 60

    def __init__(self, colour: Optional[bool] = None,
                 mask: Optional[Callable[[str], str]] = None):
        self._colour = self._supports_colour() if colour is None else colour
        self._mask = mask or (lambda s: s)
        c = self._c
        self.G, self.Y, self.R = c("\033[32m"), c("\033[33m"), c("\033[31m")
        self.B, self.D, self.W = c("\033[1m"),  c("\033[2m"),  c("\033[0m")

    # -- colour gating -------------------------------------------------------
    @staticmethod
    def _supports_colour() -> bool:
        import sys, os
        if os.environ.get("NO_COLOR"):
            return False
        return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

    def _c(self, code: str) -> str:
        return code if self._colour else ""

    # -- cell formatting (by kind) ------------------------------------------
    def _fmt_cell(self, cell: Cell) -> Tuple[str, str]:
        value, kind = cell
        if kind == "scalar":
            return ("—" if value is None else f"{value:.1f}x", "")
        if kind == "weight":
            return ("—" if value is None else f"{value:.0f} %", "")
        if kind == "ret":
            if value is None:
                return ("—", self.D)
            return (f"{value:+.2f} %", self.G if value >= 0 else self.R)
        return ("—" if value is None else str(value), "")

    def _cell_str(self, cell: Cell) -> str:
        plain, col = self._fmt_cell(cell)
        s = plain.rjust(self.COL_W)
        return f"{col}{s}{self.W}" if col else s

    def _row(self, label: str, cells: List[Cell]) -> str:
        body = " ".join(self._cell_str(c) for c in cells)
        return f"  {self._mask(label):<{self.LBL_W}}{body}"

    # -- primitive printers --------------------------------------------------
    def _render_primitive(self, p: Primitive, out: List[str]) -> None:
        if isinstance(p, Blank):
            out.append("")
        elif isinstance(p, Rule):
            out.append(f"  {self.B}{'=' * self.BLK_W}{self.W}")
        elif isinstance(p, Header):
            head = p.title
            pad = max(0, self.BLK_W - len(head) - 1)
            tick = f"{self.G}✓{self.W}" if p.ok else ""
            out.append(f"  {self.B}{'=' * self.BLK_W}{self.W}")
            out.append(f"  {self.B}{head}{self.W}{'':>{pad}}{tick}")
            out.append(f"  {self.B}{'=' * self.BLK_W}{self.W}")
        elif isinstance(p, KV):
            tone = {"risk_on": self.G, "risk_off": self.R}.get(p.tone, "")
            val = f"{tone}{self.B}{p.value}{self.W}" if tone else p.value
            out.append(f"  {self._mask(p.label):<{p.width}}{val}")
        elif isinstance(p, Banner):
            if p.tone == "action":
                out.append(f"  {self.Y}{self.B}{p.text}{self.W}")
            elif p.tone == "noaction":
                out.append(f"  {self.G}{self.B}{p.text}{self.W}")
            else:
                out.append(f"  {p.text}")
        elif isinstance(p, Table):
            if p.header is not None:
                h = p.header
                # first header cell left-justified to LBL_W, rest right-justified
                head = f"  {h[0]:<{self.LBL_W}}" + " ".join(
                    f"{c:>{self.COL_W}}" for c in h[1:])
                out.append(head)
            for label, cells in p.rows:
                out.append(self._row(label, cells))

    def render(self, blocks: List[Block]) -> str:
        out: List[str] = []
        for blk in blocks:
            if not blk.visible:
                continue
            for p in blk.elements:
                self._render_primitive(p, out)
        return "\n".join(out)

    def print(self, blocks: List[Block]) -> None:
        print(self.render(blocks))


# ── Gateway ───────────────────────────────────────────────────────────────────

@dataclass
class ViewModel:
    """The presentation-neutral output of a model: an ordered list of blocks.
    Built by the app; consumed by any renderer."""
    blocks: List[Block] = field(default_factory=list)

    def add(self, block: Block) -> "ViewModel":
        self.blocks.append(block)
        return self

    def render_terminal(self, mask: Optional[Callable[[str], str]] = None,
                        colour: Optional[bool] = None) -> str:
        return TerminalRenderer(colour=colour, mask=mask).render(self.blocks)


# ══════════════════════════════════════════════════════════════════════════════
# JSON / WEBSITE PROJECTION — contract "blackknot.v3"
# ══════════════════════════════════════════════════════════════════════════════
# The website is block-driven and the JSON is SELF-DESCRIBING: the renderer reads
# structure and semantics from the contract, never inferring from key names or
# value ranges. One generator (here) produces the contract; one consumer per
# surface reads it. Data flows one way: compute → blocks → JSON → renderer → DOM.
#
# Division of labour (the constitution):
#   • Back end COMPUTES + DECIDES. Every calculated value is finished here and
#     travels as a value. The front end never derives financial numbers.
#   • JSON carries semantic STATE + cell KIND, never display copy or colour.
#     Wording ("NO ACTION REQUIRED") and colour live in the renderer, so a copy
#     change never regenerates JSON.
#   • Masking / anonymisation is an APP (IP) decision applied here at generation
#     (Hedra → A/B/C/D); the common layer stays IP-agnostic.
#   • No forking: a value appears once and is referenced; a table's shape is
#     declared once (its columns) and rendered generically.
#
# Envelope:
#   { schema, model:{id,name,state,as_of}, meta, card, blocks:[ … ] }
# every block: { type, visible, … type-specific … }; order = array order.

SCHEMA = "blackknot.v3"

# ── Enums (semantic, model-agnostic) ──────────────────────────────────────────
# Model / signal state. The renderer maps state → wording + colour.
STATE_HOLD    = "hold"
STATE_ACTION  = "action"
STATE_PENDING = "pending"

# Cell kinds. The renderer has exactly one formatter per kind.
KIND_PCT        = "pct"          # 8.81%                 (no sign, sign-coloured)
KIND_PCT_SIGNED = "pct_signed"   # +8.81%  /  -11.80%   (sign always shown)
KIND_PCT_WHOLE  = "pct_whole"    # 60%                   (rounded, no sign)
KIND_RATIO      = "ratio"        # 1.11                  (2 dp, unsigned)
KIND_INT        = "int"          # 200
KIND_NUM        = "num"          # 23.7    (1 dp)
KIND_TEXT       = "text"         # passthrough

# Column emphasis — how the renderer weights a column visually.
EMPH_MODEL = "model"   # the subject model's column (sign-coloured / highlighted)
EMPH_BENCH = "bench"   # the benchmark column (muted)


# ── Low-level builders ────────────────────────────────────────────────────────

def cell(value, kind: str) -> dict:
    """A single table cell: a finished value + how to format it."""
    return {"value": value, "kind": kind}


def column(key: str, label: str, align: str = "right",
           emphasis: Optional[str] = None) -> dict:
    """A table column descriptor. `key` indexes into each row dict."""
    col = {"key": key, "label": label, "align": align}
    if emphasis:
        col["emphasis"] = emphasis
    return col


def table(table_id: str, title: Optional[str], columns: list, rows: list) -> dict:
    """A self-describing table: columns (descriptors) + rows (dicts keyed by
    column key, each value either a scalar label or a cell())."""
    return {"id": table_id, "title": title, "columns": columns, "rows": rows}


# ── Comparison table (the model-vs-benchmark spine) ───────────────────────────
# The performance comparison tables are IDENTICAL in shape across every model —
# this is the comparability guarantee. Their row specs live here, once.

def comparison_table(table_id: str, title: str, axis_label: str,
                     model_label: str, bench_label: str,
                     model_dict: dict, bench_dict: dict,
                     specs: list) -> dict:
    """Build a {axis | model | benchmark} table from two value dicts and a list
    of (row_label, key, kind) specs. Used for cumulative / risk tables."""
    cols = [
        column("label", axis_label, align="left"),
        column("model", model_label, emphasis=EMPH_MODEL),
        column("bench", bench_label, emphasis=EMPH_BENCH),
    ]
    rows = []
    for row_label, key, kind in specs:
        rows.append({
            "label": row_label,
            "model": cell((model_dict or {}).get(key), kind),
            "bench": cell((bench_dict or {}).get(key), kind),
        })
    return table(table_id, title, cols, rows)


def annual_table(model_label: str, bench_label: str,
                 model_annual: dict, bench_annual: dict) -> dict:
    """Year-by-year comparison; rows derived from the data's own years + YTD."""
    cols = [
        column("label", "Year", align="left"),
        column("model", model_label, emphasis=EMPH_MODEL),
        column("bench", bench_label, emphasis=EMPH_BENCH),
    ]
    years = sorted((k for k in (model_annual or {}) if str(k).isdigit()), reverse=True)
    keys = (["ytd"] if (model_annual or {}).get("ytd") is not None else []) + years
    rows = []
    for k in keys:
        rows.append({
            "label": "YTD" if k == "ytd" else str(k),
            "ytd": k == "ytd",
            "model": cell((model_annual or {}).get(k), KIND_PCT_SIGNED),
            "bench": cell((bench_annual or {}).get(k), KIND_PCT_SIGNED),
        })
    return table("annual", "Annual Return", cols, rows)


# Canonical performance row specs — the shared comparability spine.
CUMULATIVE_SPECS = [
    ("YTD", "ytd", KIND_PCT_SIGNED),
    ("1 Year", "1yr", KIND_PCT_SIGNED),
    ("3 Year", "3yr", KIND_PCT_SIGNED),
    ("5 Year", "5yr", KIND_PCT_SIGNED),
    ("Inception", "itd", KIND_PCT_SIGNED),
    ("CAGR (ITD)", "cagr_itd", KIND_PCT_SIGNED),
]
RISK_SPECS = [
    ("CAGR", "cagr", KIND_PCT_SIGNED),
    ("Volatility", "volatility", KIND_PCT_SIGNED),
    ("Sharpe", "sharpe", KIND_RATIO),
    ("Sortino", "sortino", KIND_RATIO),
    ("Calmar", "calmar", KIND_RATIO),
    ("MAR", "mar", KIND_RATIO),
    ("Max Drawdown", "maxdd", KIND_PCT_SIGNED),
    ("Avg Drawdown", "avg_drawdown", KIND_PCT_SIGNED),
    ("Beta", "beta", KIND_RATIO),
    ("Omega", "omega", KIND_RATIO),
    ("Upside Capture", "upside_capture", KIND_PCT_SIGNED),
    ("Downside Capture", "downside_capture", KIND_PCT_SIGNED),
]


# ── Blocks ────────────────────────────────────────────────────────────────────

def signal_block(visible: bool, weights: Optional[list] = None,
                 note: Optional[str] = None) -> dict:
    """Model state block. `weights` is a strip of {label,value,kind} (live);
    `note` is the pending explanation. State itself is read from model.state."""
    blk = {"type": "signal", "visible": visible}
    if weights is not None:
        blk["weights"] = weights
    if note is not None:
        blk["note"] = note
    return blk


def performance_block(visible: bool, tables: Optional[list] = None,
                      note: Optional[str] = None) -> dict:
    """Common comparability block: a list of self-describing tables, or a
    pending `note` when there is no track record yet."""
    blk = {"type": "performance", "visible": visible, "tables": tables or []}
    if note is not None:
        blk["note"] = note
    return blk


def allocation_block(visible: bool, table_obj: Optional[dict] = None,
                     note: Optional[str] = None) -> dict:
    """Class-level allocation / rebalance-event table (present-if-needed)."""
    blk = {"type": "allocation", "visible": visible}
    if table_obj is not None:
        blk["table"] = table_obj
    if note is not None:
        blk["note"] = note
    return blk


def rebalancing_block(visible: bool, table_obj: Optional[dict] = None) -> dict:
    """Rebalance counts as a small self-describing table."""
    return {"type": "rebalancing", "visible": visible, "table": table_obj}


def weight_strip(pairs: list) -> list:
    """Signal weight strip: list of {label, value, kind}. `pairs` is
    [(label, pct_value)] — labels already masked by the app if needed."""
    return [{"label": lbl, "value": val, "kind": KIND_PCT_WHOLE} for lbl, val in pairs]


def card(kpis: list, weights: list) -> dict:
    """Home-grid summary. kpis: [{label,value,kind}]; weights: [{label,value,kind}].
    Name + state are read from the model envelope (not duplicated here)."""
    return {"kpis": kpis, "weights": weights}


def model_json(model_id: str, name: str, state: str, as_of: Optional[str],
               meta: dict, card_obj: dict, blocks: list) -> dict:
    """Assemble a model's full self-describing JSON. Identical envelope for
    every model so the website renders them uniformly."""
    return {
        "schema": SCHEMA,
        "model": {"id": model_id, "name": name, "state": state, "as_of": as_of},
        "meta": meta,
        "card": card_obj,
        "blocks": blocks,
    }


def pending_model_json(model_id: str, name: str, class_labels: list,
                       note: str) -> dict:
    """Valid self-describing JSON for a model whose signal isn't built yet. KPIs
    blank, signal note set, performance + allocation visible but empty (the model
    WILL publish them), rebalancing hidden. Real class names (no mask)."""
    card_obj = card(
        kpis=[{"label": "YTD", "value": None, "kind": KIND_PCT},
              {"label": "ITD CAGR", "value": None, "kind": KIND_PCT}],
        weights=[{"label": l, "value": None, "kind": KIND_PCT_WHOLE} for l in class_labels],
    )
    blocks = [
        signal_block(True, note=note),
        performance_block(True, tables=[], note="Performance is published once the signal is live."),
        allocation_block(True, table_obj=None, note="Allocation detail is published once the signal is live."),
        rebalancing_block(False, None),
    ]
    meta = {"inception": None, "benchmark": "SPY total return (buy & hold)", "note": note}
    return model_json(model_id, name, STATE_PENDING, None, meta, card_obj, blocks)
