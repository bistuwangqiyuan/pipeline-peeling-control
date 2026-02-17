const PipeVisual = {
    canvas: null,
    ctx: null,
    stripCount: 30,
    stripData: [],
    animFrame: null,
    progress: 0,
    glowPhase: 0,

    init(canvasId, stripCount = 30) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.stripCount = stripCount;
        this.stripData = new Array(stripCount).fill(null).map((_, i) => ({
            number: i + 1,
            status: 'pending',
            force: 0,
            angle: 0
        }));
        this.resize();
        window.addEventListener('resize', () => this.resize());
        this.animate();
    },

    resize() {
        if (!this.canvas) return;
        const container = this.canvas.parentElement;
        const size = Math.min(container.clientWidth, container.clientHeight, 400);
        this.canvas.width = size;
        this.canvas.height = size;
        this.draw();
    },

    updateData(latestData, progress) {
        this.progress = progress || 0;
        if (latestData && latestData.length > 0) {
            latestData.forEach(d => {
                const idx = d.strip_number - 1;
                if (idx >= 0 && idx < this.stripCount) {
                    this.stripData[idx] = {
                        number: d.strip_number,
                        status: parseFloat(d.force_value) > 0 ? 'active' : 'pending',
                        force: parseFloat(d.force_value),
                        angle: parseFloat(d.position_angle)
                    };
                }
            });
        }
        if (this.progress >= 100) {
            this.stripData.forEach(s => {
                if (s.status === 'active') s.status = 'completed';
            });
        }
    },

    draw() {
        if (!this.ctx) return;
        const ctx = this.ctx;
        const w = this.canvas.width;
        const h = this.canvas.height;
        const cx = w / 2;
        const cy = h / 2;
        const outerR = Math.min(w, h) * 0.42;
        const innerR = outerR * 0.65;
        const stripAngle = (2 * Math.PI) / this.stripCount;

        ctx.clearRect(0, 0, w, h);

        // Outer glow ring
        const glowGrad = ctx.createRadialGradient(cx, cy, outerR * 0.9, cx, cy, outerR * 1.15);
        glowGrad.addColorStop(0, 'rgba(0, 212, 255, 0.05)');
        glowGrad.addColorStop(0.5, 'rgba(0, 102, 255, 0.02)');
        glowGrad.addColorStop(1, 'transparent');
        ctx.fillStyle = glowGrad;
        ctx.fillRect(0, 0, w, h);

        // Pipe body (gray ring)
        ctx.beginPath();
        ctx.arc(cx, cy, outerR, 0, 2 * Math.PI);
        ctx.arc(cx, cy, innerR, 0, 2 * Math.PI, true);
        ctx.fillStyle = '#1a1f3a';
        ctx.fill();
        ctx.strokeStyle = '#2a3060';
        ctx.lineWidth = 1;
        ctx.stroke();

        // Draw strips
        for (let i = 0; i < this.stripCount; i++) {
            const startAngle = -Math.PI / 2 + i * stripAngle;
            const endAngle = startAngle + stripAngle - 0.01;
            const strip = this.stripData[i];

            let fillColor;
            let glowColor = null;

            if (strip.status === 'active') {
                const intensity = Math.min(1, strip.force / 1200);
                const glow = 0.3 + 0.3 * Math.sin(this.glowPhase + i * 0.2);
                fillColor = `rgba(0, 212, 255, ${0.3 + intensity * 0.5})`;
                glowColor = `rgba(0, 212, 255, ${glow * intensity})`;
            } else if (strip.status === 'completed') {
                fillColor = 'rgba(0, 255, 136, 0.4)';
            } else if (strip.status === 'failed') {
                fillColor = 'rgba(255, 51, 102, 0.4)';
            } else {
                fillColor = 'rgba(74, 82, 128, 0.2)';
            }

            // Strip sector
            ctx.beginPath();
            ctx.arc(cx, cy, outerR - 2, startAngle, endAngle);
            ctx.arc(cx, cy, innerR + 2, endAngle, startAngle, true);
            ctx.closePath();
            ctx.fillStyle = fillColor;
            ctx.fill();

            if (glowColor) {
                ctx.shadowColor = glowColor;
                ctx.shadowBlur = 10;
                ctx.fill();
                ctx.shadowBlur = 0;
            }

            // Strip border
            ctx.strokeStyle = 'rgba(26, 34, 85, 0.8)';
            ctx.lineWidth = 0.5;
            ctx.stroke();

            // Strip number
            const midAngle = (startAngle + endAngle) / 2;
            const labelR = (outerR + innerR) / 2;
            const lx = cx + Math.cos(midAngle) * labelR;
            const ly = cy + Math.sin(midAngle) * labelR;
            ctx.fillStyle = strip.status === 'active' ? '#ffffff' : '#8892b0';
            ctx.font = '9px JetBrains Mono, monospace';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(strip.number, lx, ly);
        }

        // Center info
        ctx.fillStyle = '#0d1331';
        ctx.beginPath();
        ctx.arc(cx, cy, innerR - 5, 0, 2 * Math.PI);
        ctx.fill();

        ctx.strokeStyle = '#1a2255';
        ctx.lineWidth = 1;
        ctx.stroke();

        // Center text
        ctx.fillStyle = '#e0e8ff';
        ctx.font = 'bold 14px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(`${this.progress.toFixed(1)}%`, cx, cy - 8);

        ctx.fillStyle = '#8892b0';
        ctx.font = '10px Inter, sans-serif';
        ctx.fillText('剥离进度', cx, cy + 10);

        // Progress arc
        if (this.progress > 0) {
            const progressAngle = (this.progress / 100) * 2 * Math.PI;
            ctx.beginPath();
            ctx.arc(cx, cy, outerR + 4, -Math.PI / 2, -Math.PI / 2 + progressAngle);
            ctx.strokeStyle = '#00d4ff';
            ctx.lineWidth = 3;
            ctx.lineCap = 'round';
            ctx.shadowColor = 'rgba(0, 212, 255, 0.5)';
            ctx.shadowBlur = 8;
            ctx.stroke();
            ctx.shadowBlur = 0;
        }
    },

    animate() {
        this.glowPhase += 0.05;
        this.draw();
        this.animFrame = requestAnimationFrame(() => this.animate());
    },

    destroy() {
        if (this.animFrame) {
            cancelAnimationFrame(this.animFrame);
        }
    }
};
