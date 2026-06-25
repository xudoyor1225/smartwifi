import { useEffect, useRef, memo } from 'react';
import type { TrafficPoint } from '../context/NetworkContext';

interface TrafficChartProps {
  data: TrafficPoint[];
  height?: number;
  windowMs?: number; // Time window to display (default 60 seconds)
}

/**
 * Smooth real-time traffic chart using HTML5 Canvas.
 *
 * Features:
 * - Time-based smooth scrolling (right-to-left)
 * - Beautiful smooth area chart with cubic bezier curves
 * - Pulsating tip dot at the latest data point
 * - Dynamic Y-axis with smooth max value transitions
 * - High DPI support
 * - 60 FPS animation
 */
function TrafficChart({ data, height = 280, windowMs = 60000 }: TrafficChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const animationRef = useRef<number | null>(null);
  const dataRef = useRef<TrafficPoint[]>(data);
  const smoothMaxRef = useRef<number>(0.1);

  useEffect(() => {
    dataRef.current = data;
  }, [data]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let dpr = window.devicePixelRatio || 1;

    const setupCanvas = () => {
      dpr = window.devicePixelRatio || 1;
      const rect = container.getBoundingClientRect();
      canvas.width = rect.width * dpr;
      canvas.height = height * dpr;
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${height}px`;
    };
    setupCanvas();

    const resizeObserver = new ResizeObserver(() => setupCanvas());
    resizeObserver.observe(container);

    // Catmull-Rom spline interpolation for ultra smooth curves
    const drawSmoothLine = (
      points: { x: number; y: number }[],
      strokeColor: string,
      lineWidth: number
    ) => {
      if (points.length < 2) return;
      ctx.strokeStyle = strokeColor;
      ctx.lineWidth = lineWidth;
      ctx.lineJoin = 'round';
      ctx.lineCap = 'round';

      ctx.beginPath();
      ctx.moveTo(points[0].x, points[0].y);

      for (let i = 0; i < points.length - 1; i++) {
        const p0 = points[Math.max(0, i - 1)];
        const p1 = points[i];
        const p2 = points[i + 1];
        const p3 = points[Math.min(points.length - 1, i + 2)];

        const tension = 0.5;
        const cp1x = p1.x + ((p2.x - p0.x) / 6) * tension;
        const cp1y = p1.y + ((p2.y - p0.y) / 6) * tension;
        const cp2x = p2.x - ((p3.x - p1.x) / 6) * tension;
        const cp2y = p2.y - ((p3.y - p1.y) / 6) * tension;

        ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, p2.x, p2.y);
      }
      ctx.stroke();
    };

    const drawSmoothArea = (
      points: { x: number; y: number }[],
      bottomY: number,
      gradientTop: string,
      gradientBottom: string
    ) => {
      if (points.length < 2) return;

      ctx.beginPath();
      ctx.moveTo(points[0].x, bottomY);
      ctx.lineTo(points[0].x, points[0].y);

      for (let i = 0; i < points.length - 1; i++) {
        const p0 = points[Math.max(0, i - 1)];
        const p1 = points[i];
        const p2 = points[i + 1];
        const p3 = points[Math.min(points.length - 1, i + 2)];

        const tension = 0.5;
        const cp1x = p1.x + ((p2.x - p0.x) / 6) * tension;
        const cp1y = p1.y + ((p2.y - p0.y) / 6) * tension;
        const cp2x = p2.x - ((p3.x - p1.x) / 6) * tension;
        const cp2y = p2.y - ((p3.y - p1.y) / 6) * tension;

        ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, p2.x, p2.y);
      }

      ctx.lineTo(points[points.length - 1].x, bottomY);
      ctx.closePath();

      const gradient = ctx.createLinearGradient(0, points[0].y, 0, bottomY);
      gradient.addColorStop(0, gradientTop);
      gradient.addColorStop(1, gradientBottom);
      ctx.fillStyle = gradient;
      ctx.fill();
    };

    const draw = (timestamp: number) => {
      const points = dataRef.current;
      const rect = container.getBoundingClientRect();
      const W = rect.width;
      const H = height;

      // Reset transform and clear
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, W, H);

      if (points.length < 2) {
        animationRef.current = requestAnimationFrame(draw);
        return;
      }

      // Layout
      const padTop = 20;
      const padBottom = 30;
      const padLeft = 60;
      const padRight = 20;
      const chartW = W - padLeft - padRight;
      const chartH = H - padTop - padBottom;

      // Time-based X positioning
      // Always anchor the latest point to the right edge
      // Window width is min(windowMs, time span of available data)
      const now = Date.now();
      const oldestTimestamp = points[0].timestamp;
      const dataSpan = now - oldestTimestamp;
      const effectiveWindow = Math.min(windowMs, Math.max(5000, dataSpan + 1000));
      const timeStart = now - effectiveWindow;

      // Smooth max calculation (eases towards target instead of jumping)
      const visiblePoints = points.filter((p) => p.timestamp >= timeStart);
      if (visiblePoints.length > 0) {
        const maxVal = Math.max(
          ...visiblePoints.flatMap((p) => [p.download, p.upload]),
          0.1
        );
        const targetMax = Math.max(0.1, maxVal * 1.3);
        // Ease towards target (smooth Y-axis)
        smoothMaxRef.current += (targetMax - smoothMaxRef.current) * 0.1;
      }
      const yMax = smoothMaxRef.current;

      const xAt = (timestamp: number): number => {
        const fraction = (timestamp - timeStart) / effectiveWindow;
        return padLeft + fraction * chartW;
      };
      const yAt = (val: number): number =>
        padTop + chartH - (val / yMax) * chartH;

      // === Draw Grid ===
      ctx.strokeStyle = '#1F2937';
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 3]);
      const gridLines = 4;
      for (let i = 0; i <= gridLines; i++) {
        const y = padTop + (chartH / gridLines) * i;
        ctx.beginPath();
        ctx.moveTo(padLeft, y);
        ctx.lineTo(W - padRight, y);
        ctx.stroke();
      }
      ctx.setLineDash([]);

      // === Y-axis labels ===
      ctx.fillStyle = '#64748B';
      ctx.font = '10px Inter, sans-serif';
      ctx.textAlign = 'right';
      ctx.textBaseline = 'middle';
      for (let i = 0; i <= gridLines; i++) {
        const y = padTop + (chartH / gridLines) * i;
        const value = yMax * (1 - i / gridLines);
        ctx.fillText(`${value.toFixed(2)} Mbps`, padLeft - 8, y);
      }

      // === X-axis labels (time markers) ===
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      const xLabels = 6;
      for (let i = 0; i <= xLabels; i++) {
        const t = timeStart + (effectiveWindow / xLabels) * i;
        const x = padLeft + (chartW / xLabels) * i;
        const label = new Date(t).toLocaleTimeString('uz-UZ', {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        });
        ctx.fillText(label, x, H - padBottom + 6);
      }

      // === Build screen-space points (with clipping) ===
      const downloadPoints: { x: number; y: number }[] = [];
      const uploadPoints: { x: number; y: number }[] = [];

      for (const p of points) {
        if (p.timestamp < timeStart - 2000) continue; // skip very old
        const x = xAt(p.timestamp);
        downloadPoints.push({ x, y: yAt(p.download) });
        uploadPoints.push({ x, y: yAt(p.upload) });
      }

      // Clip drawing area to chart bounds
      ctx.save();
      ctx.beginPath();
      ctx.rect(padLeft, padTop, chartW, chartH);
      ctx.clip();

      // === Draw Download (blue, behind) ===
      drawSmoothArea(
        downloadPoints,
        padTop + chartH,
        'rgba(59, 130, 246, 0.4)',
        'rgba(59, 130, 246, 0)'
      );
      drawSmoothLine(downloadPoints, 'rgb(59, 130, 246)', 2.5);

      // === Draw Upload (green, in front) ===
      drawSmoothArea(
        uploadPoints,
        padTop + chartH,
        'rgba(16, 185, 129, 0.35)',
        'rgba(16, 185, 129, 0)'
      );
      drawSmoothLine(uploadPoints, 'rgb(16, 185, 129)', 2.5);

      ctx.restore();

      // === Draw pulsating tip dots ===
      const drawTipDot = (
        screenPoints: { x: number; y: number }[],
        color: string
      ) => {
        if (screenPoints.length === 0) return;
        const last = screenPoints[screenPoints.length - 1];
        if (last.x < padLeft || last.x > W - padRight) return;

        // Outer pulse
        const pulsePhase = (timestamp / 1000) % 1.5;
        const pulseRadius = 4 + pulsePhase * 12;
        const pulseAlpha = Math.max(0, 0.5 - pulsePhase * 0.33);

        ctx.beginPath();
        ctx.arc(last.x, last.y, pulseRadius, 0, Math.PI * 2);
        ctx.fillStyle = color.replace('rgb', 'rgba').replace(')', `, ${pulseAlpha})`);
        ctx.fill();

        // Glowing center dot
        ctx.shadowBlur = 14;
        ctx.shadowColor = color;
        ctx.beginPath();
        ctx.arc(last.x, last.y, 4, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
        ctx.shadowBlur = 0;

        // Inner ring (border)
        ctx.beginPath();
        ctx.arc(last.x, last.y, 4, 0, Math.PI * 2);
        ctx.strokeStyle = '#0F1623';
        ctx.lineWidth = 2;
        ctx.stroke();
      };

      drawTipDot(downloadPoints, 'rgb(59, 130, 246)');
      drawTipDot(uploadPoints, 'rgb(16, 185, 129)');

      animationRef.current = requestAnimationFrame(draw);
    };

    animationRef.current = requestAnimationFrame(draw);

    return () => {
      if (animationRef.current !== null) {
        cancelAnimationFrame(animationRef.current);
      }
      resizeObserver.disconnect();
    };
  }, [height, windowMs]);

  return (
    <div ref={containerRef} className="relative w-full" style={{ height }}>
      <canvas ref={canvasRef} className="block" />
    </div>
  );
}

export default memo(TrafficChart);
