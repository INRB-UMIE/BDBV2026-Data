"""National map of significant Flowminder relocation flows (Mar–Apr 2026).

Uses ``processed/flowminder__relocations__static.matrix.csv``. Health zones are
shown in light grey; pairwise flows above the display threshold are drawn as
offset directed arrows: red (outgoing from origin) and blue (incoming to
destination), both anchored at zone centroids with curved paths; width and
colour scaled by log10(relocations). No case counts.

Run from repo root:
    python data/flowminder/plot_relocations_map.py
"""

from __future__ import annotations

import csv
import math
import os
import sys
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import matplotlib.pyplot as plt  # noqa: E402
import shapefile  # pyshp  # noqa: E402
from matplotlib.cm import ScalarMappable  # noqa: E402
from matplotlib.colors import Normalize  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import FancyArrowPatch  # noqa: E402
from matplotlib.patches import Polygon as MplPolygon  # noqa: E402
from shapely.geometry import shape as shapely_shape  # noqa: E402

from tools.lib.schema import SHAPEFILE, load_zones  # noqa: E402

HERE = Path(__file__).resolve().parent
MATRIX = HERE / "processed" / "flowminder__relocations__static.matrix.csv"
OUT_PNG = HERE / "relocations_flow_map.png"

MIN_FLOW = 100
ZONE_FILL = "#f0f0f0"
ZONE_EDGE = "#bdbdbd"
ARC_RAD_OUT = 0.28
ARC_RAD_IN = -0.28


def _plot_polygon(ax, sh: shapefile.Shape, **kwargs) -> None:
    parts = list(sh.parts) + [len(sh.points)]
    for i in range(len(parts) - 1):
        ring = sh.points[parts[i]: parts[i + 1]]
        if len(ring) >= 3:
            ax.add_patch(MplPolygon(ring, closed=True, **kwargs))


def _load_zone_geometries() -> tuple[dict[str, shapefile.Shape], dict[str, tuple[float, float]]]:
    zones = load_zones()
    reader = shapefile.Reader(str(SHAPEFILE))
    shapes: dict[str, shapefile.Shape] = {}
    centroids: dict[str, tuple[float, float]] = {}
    for zone, shp in zip(zones, reader.shapes()):
        geom = shapely_shape(shp.__geo_interface__)
        if not geom.is_valid:
            geom = geom.buffer(0)
        c = geom.centroid
        shapes[zone.canonical_nom] = shp
        centroids[zone.canonical_nom] = (c.x, c.y)
    return shapes, centroids


def _load_flow_segments() -> list[tuple[str, str, float]]:
    segments: list[tuple[str, str, float]] = []
    with MATRIX.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        dest_cols = header[1:]
        for row in reader:
            origin = row[0]
            for dest, value in zip(dest_cols, row[1:]):
                try:
                    flow = float(value)
                except ValueError:
                    continue
                if flow >= MIN_FLOW and origin != dest:
                    segments.append((origin, dest, flow))
    return segments


def _map_bounds(shapes: dict[str, shapefile.Shape]) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []
    for sh in shapes.values():
        xs.extend(p[0] for p in sh.points)
        ys.extend(p[1] for p in sh.points)
    pad = 0.4
    return min(xs) - pad, max(xs) + pad, min(ys) - pad, max(ys) + pad


def _line_width(flow: float, vmin: float, vmax: float) -> float:
    return 0.25 + 2.0 * (math.log10(flow) - math.log10(vmin)) / (
        math.log10(vmax) - math.log10(vmin)
    )


def _flow_arrow(
    ax,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    color: str,
    width: float,
    rad: float,
    zorder: int,
) -> None:
    mutation_scale = max(4.0, width * 5.0)
    patch = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=mutation_scale,
        linewidth=width,
        color=color,
        alpha=0.72,
        zorder=zorder,
        connectionstyle=f"arc3,rad={rad}",
        shrinkA=0,
        shrinkB=0,
    )
    ax.add_patch(patch)


def main() -> int:
    if not MATRIX.exists():
        raise FileNotFoundError(f"Run process.py first; missing {MATRIX}")

    zone_shapes, centroids = _load_zone_geometries()
    segments = _load_flow_segments()
    if not segments:
        raise ValueError(f"No flows >= {MIN_FLOW} in {MATRIX.name}")

    flows = [flow for _, _, flow in segments]
    vmax = max(flows)
    vmin = MIN_FLOW
    norm = Normalize(vmin=math.log10(vmin), vmax=math.log10(vmax))
    cmap_out = plt.get_cmap("Reds")
    cmap_in = plt.get_cmap("Blues")

    fig, ax = plt.subplots(figsize=(11, 11), layout="constrained")
    bounds = _map_bounds(zone_shapes)

    for sh in zone_shapes.values():
        _plot_polygon(
            ax,
            sh,
            facecolor=ZONE_FILL,
            edgecolor=ZONE_EDGE,
            linewidth=0.25,
            zorder=1,
        )

    for origin, dest, flow in segments:
        if origin not in centroids or dest not in centroids:
            continue
        x0, y0 = centroids[origin]
        x1, y1 = centroids[dest]
        width = _line_width(flow, vmin, vmax)
        log_flow = math.log10(flow)
        out_color = cmap_out(norm(log_flow))
        in_color = cmap_in(norm(log_flow))

        _flow_arrow(
            ax,
            (x0, y0),
            (x1, y1),
            color=out_color,
            width=width,
            rad=ARC_RAD_OUT,
            zorder=3,
        )
        _flow_arrow(
            ax,
            (x0, y0),
            (x1, y1),
            color=in_color,
            width=width,
            rad=ARC_RAD_IN,
            zorder=2,
        )

    xmin, xmax, ymin, ymax = bounds
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(
        "Flowminder estimated relocations between health zones\n"
        "March–April 2026 (flows ≥ 100 persons)",
        fontsize=12,
    )

    sm_out = ScalarMappable(cmap=cmap_out, norm=norm)
    sm_out.set_array([])
    sm_in = ScalarMappable(cmap=cmap_in, norm=norm)
    sm_in.set_array([])

    cbar_out = fig.colorbar(sm_out, ax=ax, fraction=0.025, pad=0.01, location="right")
    cbar_out.set_label("Outgoing flow (log10 relocations)", color="#8b0000")
    cbar_out.ax.yaxis.set_tick_params(color="#8b0000")
    cbar_out.outline.set_edgecolor("#8b0000")

    cbar_in = fig.colorbar(sm_in, ax=ax, fraction=0.025, pad=0.06, location="right")
    cbar_in.set_label("Incoming flow (log10 relocations)", color="#003366")
    cbar_in.ax.yaxis.set_tick_params(color="#003366")
    cbar_in.outline.set_edgecolor("#003366")

    legend_handles = [
        Line2D(
            [0],
            [0],
            color=cmap_out(0.85),
            linewidth=2.0,
            marker=">",
            markersize=8,
            label="Outgoing (origin → destination)",
        ),
        Line2D(
            [0],
            [0],
            color=cmap_in(0.85),
            linewidth=2.0,
            marker=">",
            markersize=8,
            label="Incoming (origin → destination)",
        ),
        Line2D(
            [0],
            [0],
            color="none",
            label=f"{len(segments):,} origin–destination pairs shown (≥ {MIN_FLOW})",
        ),
    ]
    ax.legend(handles=legend_handles, loc="lower left", frameon=True, fontsize=9)

    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PNG, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(
        f"wrote {OUT_PNG.relative_to(REPO_ROOT)} "
        f"({len(segments)} flows, {len(zone_shapes)} health zones)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
