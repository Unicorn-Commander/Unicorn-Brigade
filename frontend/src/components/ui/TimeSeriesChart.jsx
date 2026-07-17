import { useCallback, useLayoutEffect, useMemo, useRef, useState } from 'react';

/**
 * Dependency-free SVG time-series chart (line + area) for real, observed data.
 *
 * Built per the dataviz method: recessive gridlines, thin 2px marks, a legend
 * for ≥2 series, selective direct labels (latest value only), and a
 * crosshair+tooltip hover layer. Series colors come from the themeable
 * `--chart-*` CSS variables (validated CVD-safe blue+magenta pair) so the chart
 * re-themes with the app. No Math.random, no fake data — callers pass observed
 * samples.
 *
 * @param {{key:string,label:string,color:string,data:number[]}[]} series
 * @param {string[]} labels  x-axis labels, aligned by index to each series.data
 * @param {number}   [yMax]  fixed y ceiling (e.g. 100 for %). Auto if omitted.
 * @param {string}   [unit]  value suffix in labels/tooltip (e.g. '%').
 * @param {number}   [height]
 */
export default function TimeSeriesChart({
  series = [],
  labels = [],
  yMax,
  unit = '',
  height = 220,
  emptyLabel = 'Collecting data…',
}) {
  const wrapRef = useRef(null);
  const [width, setWidth] = useState(640);
  const [hover, setHover] = useState(null); // index into labels

  useLayoutEffect(() => {
    const el = wrapRef.current;
    if (!el || typeof ResizeObserver === 'undefined') return undefined;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect?.width;
      if (w) setWidth(Math.max(240, Math.round(w)));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const n = labels.length;
  const activeSeries = series.filter((s) => Array.isArray(s.data) && s.data.length > 0);
  const hasData = n >= 2 && activeSeries.length > 0;

  // Layout box.
  const padL = 40;
  const padR = 14;
  const padT = 14;
  const padB = 26;
  const plotW = Math.max(1, width - padL - padR);
  const plotH = Math.max(1, height - padT - padB);

  const ceiling = useMemo(() => {
    if (yMax != null) return yMax;
    const peak = Math.max(1, ...activeSeries.flatMap((s) => s.data.filter((v) => Number.isFinite(v))));
    // Round up to a tidy step.
    const step = peak <= 10 ? 2 : peak <= 50 ? 10 : peak <= 100 ? 25 : 100;
    return Math.ceil(peak / step) * step;
  }, [yMax, activeSeries]);

  const xAt = useCallback((i) => padL + (n <= 1 ? 0 : (i / (n - 1)) * plotW), [n, plotW]);
  const yAt = useCallback((v) => padT + (1 - Math.min(v, ceiling) / ceiling) * plotH, [ceiling, plotH]);

  // Horizontal gridlines at tidy fractions.
  const gridTicks = useMemo(() => {
    const divs = 4;
    return Array.from({ length: divs + 1 }, (_, i) => (ceiling / divs) * i);
  }, [ceiling]);

  const handleMove = useCallback(
    (e) => {
      if (!hasData) return;
      const rect = e.currentTarget.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const rel = (x - padL) / plotW;
      const idx = Math.round(rel * (n - 1));
      setHover(Math.max(0, Math.min(n - 1, idx)));
    },
    [hasData, n, plotW]
  );

  if (!hasData) {
    return (
      <div
        ref={wrapRef}
        className="flex items-center justify-center rounded-lg border border-border/40 bg-slate-800/30 text-sm text-muted"
        style={{ height }}
      >
        {emptyLabel}
      </div>
    );
  }

  const latestSummary = activeSeries
    .map((s) => `${s.label} ${Math.round(s.data[s.data.length - 1])}${unit}`)
    .join(', ');

  return (
    <div ref={wrapRef} className="relative w-full select-none">
      <svg
        width={width}
        height={height}
        role="img"
        aria-label={`Time series. Latest: ${latestSummary}.`}
        onMouseMove={handleMove}
        onMouseLeave={() => setHover(null)}
        style={{ display: 'block' }}
      >
        <defs>
          {activeSeries.map((s, si) => (
            <linearGradient key={s.key} id={`ts-fill-${si}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={s.color} stopOpacity="0.28" />
              <stop offset="100%" stopColor={s.color} stopOpacity="0" />
            </linearGradient>
          ))}
        </defs>

        {/* Gridlines + y ticks (recessive) */}
        {gridTicks.map((t, i) => {
          const y = yAt(t);
          return (
            <g key={i}>
              <line x1={padL} y1={y} x2={width - padR} y2={y} stroke="var(--chart-grid)" strokeWidth="1" />
              <text
                x={padL - 8}
                y={y}
                textAnchor="end"
                dominantBaseline="middle"
                fontSize="10"
                fill="var(--chart-axis)"
                style={{ fontVariantNumeric: 'tabular-nums' }}
              >
                {Math.round(t)}
                {unit}
              </text>
            </g>
          );
        })}

        {/* Areas + lines */}
        {activeSeries.map((s, si) => {
          const pts = s.data.map((v, i) => `${xAt(i)},${yAt(v)}`);
          const linePath = `M ${pts.join(' L ')}`;
          const areaPath = `${linePath} L ${xAt(s.data.length - 1)},${padT + plotH} L ${xAt(0)},${padT + plotH} Z`;
          const lastX = xAt(s.data.length - 1);
          const lastY = yAt(s.data[s.data.length - 1]);
          return (
            <g key={s.key}>
              <path d={areaPath} fill={`url(#ts-fill-${si})`} />
              <path
                d={linePath}
                fill="none"
                stroke={s.color}
                strokeWidth="2"
                strokeLinejoin="round"
                strokeLinecap="round"
              />
              {/* Direct label: latest value only */}
              <circle cx={lastX} cy={lastY} r="3.5" fill={s.color} stroke="var(--chart-1)" strokeWidth="0" />
            </g>
          );
        })}

        {/* x-axis end labels (first + last only, to avoid clutter) */}
        <text x={padL} y={height - 8} textAnchor="start" fontSize="10" fill="var(--chart-axis)">
          {labels[0]}
        </text>
        <text x={width - padR} y={height - 8} textAnchor="end" fontSize="10" fill="var(--chart-axis)">
          {labels[n - 1]}
        </text>

        {/* Crosshair + hover markers */}
        {hover != null && (
          <g pointerEvents="none">
            <line
              x1={xAt(hover)}
              y1={padT}
              x2={xAt(hover)}
              y2={padT + plotH}
              stroke="var(--chart-axis)"
              strokeWidth="1"
              strokeDasharray="3 3"
              opacity="0.6"
            />
            {activeSeries.map((s) => (
              <circle
                key={s.key}
                cx={xAt(hover)}
                cy={yAt(s.data[hover] ?? 0)}
                r="4"
                fill={s.color}
                stroke="#0f172a"
                strokeWidth="1.5"
              />
            ))}
          </g>
        )}
      </svg>

      {/* Tooltip */}
      {hover != null && (
        <div
          className="pointer-events-none absolute z-10 rounded-lg border border-border/60 bg-slate-900/95 px-3 py-2 text-xs shadow-xl backdrop-blur-sm"
          style={{
            left: Math.min(Math.max(xAt(hover) - 60, 4), width - 124),
            top: 6,
            minWidth: 120,
          }}
        >
          <p className="mb-1 font-medium text-slate-300">{labels[hover]}</p>
          {activeSeries.map((s) => (
            <div key={s.key} className="flex items-center justify-between gap-3">
              <span className="flex items-center gap-1.5 text-muted">
                <span className="inline-block h-2 w-2 rounded-full" style={{ background: s.color }} />
                {s.label}
              </span>
              <span className="font-semibold text-white" style={{ fontVariantNumeric: 'tabular-nums' }}>
                {Math.round(s.data[hover] ?? 0)}
                {unit}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Legend (identity is never color-alone) */}
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1">
        {activeSeries.map((s) => (
          <span key={s.key} className="flex items-center gap-1.5 text-xs text-muted">
            <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: s.color }} />
            {s.label}
          </span>
        ))}
      </div>
    </div>
  );
}
