/* miniplot — mini bibliothèque de graphiques embarquée, zéro dépendance, 100% offline.
   F(t) en ligne ou X(Y) en nuage de points, rendu canvas style phospho. */
class MiniPlot {
  constructor(canvas, opts = {}) {
    this.c = canvas;
    this.ctx = canvas.getContext('2d');
    this.opts = Object.assign({
      pad: 40, color: '#39ff6e', bg: '#050a06',
      axis: '#1d8f43', text: '#1d8f43', scatter: false, fill: false
    }, opts);
    this.series = [];
  }
  setData(series) { this.series = series; this.draw(); }
  draw() {
    const { ctx, c, opts } = this;
    const W = c.width, H = c.height, pad = opts.pad;
    const pw = W - pad - 10, ph = H - pad - 8;
    ctx.fillStyle = opts.bg;
    ctx.fillRect(0, 0, W, H);
    let xmin = Infinity, xmax = -Infinity, ymin = Infinity, ymax = -Infinity;
    for (const s of this.series) {
      for (let i = 0; i < s.x.length; i++) {
        if (s.x[i] < xmin) xmin = s.x[i];
        if (s.x[i] > xmax) xmax = s.x[i];
        if (s.y[i] < ymin) ymin = s.y[i];
        if (s.y[i] > ymax) ymax = s.y[i];
      }
    }
    if (!isFinite(xmin)) { xmin = 0; xmax = 1; ymin = 0; ymax = 1; }
    if (xmin === xmax) xmax = xmin + 1;
    if (ymin === ymax) ymax = ymin + 1;
    const X = v => pad + (v - xmin) / (xmax - xmin) * pw;
    const Y = v => H - 8 - (v - ymin) / (ymax - ymin) * ph;
    // grille
    ctx.strokeStyle = opts.axis; ctx.globalAlpha = .45; ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const gx = pad + pw * i / 4, gy = 8 + ph * i / 4;
      ctx.beginPath(); ctx.moveTo(gx, 8); ctx.lineTo(gx, H - 8); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(pad, gy); ctx.lineTo(pad + pw, gy); ctx.stroke();
    }
    ctx.globalAlpha = 1;
    ctx.fillStyle = opts.text; ctx.font = '11px monospace';
    ctx.fillText(ymax.toFixed(1), 2, 12);
    ctx.fillText(ymin.toFixed(1), 2, H - 10);
    const t0 = new Date(xmin * 1000), t1 = new Date(xmax * 1000);
    ctx.fillText(t0.toLocaleTimeString(), pad, H - 1);
    ctx.fillText(t1.toLocaleTimeString(), pad + pw - 70, H - 1);
    // séries
    for (const s of this.series) {
      const col = s.color || opts.color;
      ctx.strokeStyle = col; ctx.fillStyle = col;
      if (opts.scatter) {
        for (let i = 0; i < s.x.length; i++) ctx.fillRect(X(s.x[i]) - 1.5, Y(s.y[i]) - 1.5, 3, 3);
      } else {
        if (opts.fill && s.x.length > 1) {
          ctx.globalAlpha = .18;
          ctx.beginPath(); ctx.moveTo(X(s.x[0]), H - 8);
          for (let i = 0; i < s.x.length; i++) ctx.lineTo(X(s.x[i]), Y(s.y[i]));
          ctx.lineTo(X(s.x[s.x.length - 1]), H - 8); ctx.closePath(); ctx.fill();
          ctx.globalAlpha = 1;
        }
        ctx.lineWidth = 2; ctx.beginPath();
        for (let i = 0; i < s.x.length; i++) {
          const px = X(s.x[i]), py = Y(s.y[i]);
          i ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
        }
        ctx.stroke();
      }
    }
    ctx.strokeStyle = opts.axis; ctx.lineWidth = 1;
    ctx.strokeRect(pad, 8, pw, ph);
  }
}
window.MiniPlot = MiniPlot;
