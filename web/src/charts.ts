import * as echarts from "echarts/core";
import { LineChart, BarChart, ScatterChart, CustomChart } from "echarts/charts";
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, MarkAreaComponent, MarkPointComponent,
  DataZoomComponent, ToolboxComponent, GraphicComponent, TitleComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([LineChart, BarChart, ScatterChart, CustomChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent,
  MarkAreaComponent, MarkPointComponent, DataZoomComponent, ToolboxComponent, GraphicComponent, TitleComponent, CanvasRenderer]);

const light = () => document.documentElement.dataset.theme === "light";
export const C = {
  tx: () => (light() ? "#0B1220" : "#F5F5F7"), tx2: () => (light() ? "#44505F" : "#9AA6B6"),
  grid: () => (light() ? "#D5DCE6" : "#1C2A3E"), axis: () => (light() ? "#B8C4D3" : "#2B4763"),
};

const charts = new Set<echarts.ECharts>();
export function base(): any {
  return {
    backgroundColor: "transparent",
    textStyle: { fontFamily: "Inter, system-ui, sans-serif", color: C.tx2(), fontSize: document.documentElement.classList.contains("pres") ? 16 : 14 },
    animationDuration: document.documentElement.classList.contains("pres") ? 350 : 800, animationEasing: "cubicOut", animationDurationUpdate: 300,
    grid: { left: 64, right: 26, top: 62, bottom: 48, containLabel: false },
    tooltip: { trigger: "axis", backgroundColor: "rgba(5,7,10,.96)", borderColor: "#2B4763", borderWidth: 1, padding: [8, 12], extraCssText: "border-radius:10px;box-shadow:0 12px 32px rgba(0,0,0,.45)", textStyle: { color: "#F5F5F7", fontFamily: "JetBrains Mono", fontSize: 13 },
      axisPointer: { lineStyle: { color: "#4FD1E0", type: "dashed" }, crossStyle: { color: "#4FD1E0" } } },
    legend: { top: 4, left: "center", textStyle: { color: C.tx(), fontFamily: "JetBrains Mono", fontSize: 12 }, icon: "roundRect", itemWidth: 12, itemHeight: 8 },
    toolbox: { right: 0, top: 0, iconStyle: { borderColor: C.tx2() }, feature: { saveAsImage: { title: "PNG", backgroundColor: light() ? "#fff" : "#05070A", pixelRatio: 2 } } },
  };
}
export const axis = (o: any = {}) => ({
  axisLine: { lineStyle: { color: C.axis() } }, axisTick: { show: false },
  axisLabel: { color: C.tx2(), fontFamily: "JetBrains Mono", fontSize: 13 },
  splitLine: { lineStyle: { color: C.grid(), type: "dashed" } }, nameTextStyle: { color: C.tx2(), fontFamily: "JetBrains Mono", fontSize: 12 }, ...o,
});

export function mount(el: HTMLElement, opt: any, lazy = true): echarts.ECharts {
  const ch = echarts.getInstanceByDom(el) || echarts.init(el, undefined, { renderer: "canvas" });
  charts.add(ch);
  const go = () => ch.setOption({ ...base(), ...opt }, true);
  if (lazy && "IntersectionObserver" in window && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
    const io = new IntersectionObserver((es) => { if (es[0].isIntersecting) { go(); io.disconnect(); } }, { threshold: 0.2 });
    io.observe(el);
  } else go();
  return ch;
}
export function update(el: HTMLElement, opt: any, notMerge = false) {
  const ch = echarts.getInstanceByDom(el) || mount(el, opt, false);
  ch.setOption(notMerge ? { ...base(), ...opt } : opt, notMerge);
  return ch;
}
addEventListener("resize", () => charts.forEach((c) => c.resize()));
export function resizeAll() { charts.forEach((c) => c.resize()); }

/** Download rows as CSV (aggregates only). */
export function csv(name: string, rows: Record<string, any>[]) {
  if (!rows.length) return;
  const keys = Object.keys(rows[0]);
  const body = [keys.join(","), ...rows.map((r) => keys.map((k) => JSON.stringify(r[k] ?? "")).join(","))].join("\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([body], { type: "text/csv" }));
  a.download = name;
  a.click();
}
export { echarts };
