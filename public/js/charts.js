const CHART_THEME = {
    color: ['#00d4ff', '#0066ff', '#00ff88', '#ffaa00', '#ff3366',
            '#7c3aed', '#06b6d4', '#10b981', '#f59e0b', '#ef4444',
            '#8b5cf6', '#14b8a6', '#84cc16', '#f97316', '#ec4899',
            '#3b82f6', '#22c55e', '#eab308', '#e11d48', '#6366f1',
            '#0ea5e9', '#34d399', '#fbbf24', '#f43f5e', '#a78bfa',
            '#2dd4bf', '#a3e635', '#fb923c', '#f472b6', '#818cf8'],
    backgroundColor: 'transparent',
    textStyle: {
        color: '#8892b0',
        fontFamily: 'Inter, sans-serif'
    },
    title: {
        textStyle: { color: '#e0e8ff', fontSize: 14, fontWeight: 600 },
        subtextStyle: { color: '#8892b0' }
    },
    legend: {
        textStyle: { color: '#8892b0', fontSize: 11 },
        pageTextStyle: { color: '#8892b0' },
        pageIconColor: '#00d4ff',
        pageIconInactiveColor: '#4a5280'
    },
    tooltip: {
        backgroundColor: 'rgba(13, 19, 49, 0.95)',
        borderColor: '#1a2255',
        textStyle: { color: '#e0e8ff', fontSize: 12 },
        extraCssText: 'box-shadow: 0 4px 20px rgba(0,0,0,0.5); border-radius: 8px;'
    },
    xAxis: {
        axisLine: { lineStyle: { color: '#1a2255' } },
        axisTick: { lineStyle: { color: '#1a2255' } },
        axisLabel: { color: '#8892b0', fontSize: 11 },
        splitLine: { lineStyle: { color: 'rgba(26, 34, 85, 0.5)', type: 'dashed' } }
    },
    yAxis: {
        axisLine: { lineStyle: { color: '#1a2255' } },
        axisTick: { lineStyle: { color: '#1a2255' } },
        axisLabel: { color: '#8892b0', fontSize: 11 },
        splitLine: { lineStyle: { color: 'rgba(26, 34, 85, 0.5)', type: 'dashed' } }
    },
    grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        top: '15%',
        containLabel: true
    }
};

const Charts = {
    instances: {},

    init(id, option) {
        const dom = document.getElementById(id);
        if (!dom) return null;

        if (this.instances[id]) {
            this.instances[id].dispose();
        }

        const chart = echarts.init(dom, null, { renderer: 'canvas' });
        echarts.registerTheme('industrial', CHART_THEME);

        const baseOpt = {
            backgroundColor: 'transparent',
            textStyle: CHART_THEME.textStyle,
            tooltip: CHART_THEME.tooltip,
            grid: CHART_THEME.grid,
            animation: true,
            animationDuration: 500,
            animationEasing: 'cubicOut'
        };

        chart.setOption({ ...baseOpt, ...option });
        this.instances[id] = chart;

        window.addEventListener('resize', () => chart.resize());
        return chart;
    },

    update(id, option) {
        const chart = this.instances[id];
        if (chart) {
            chart.setOption(option, { notMerge: false });
        }
    },

    dispose(id) {
        const chart = this.instances[id];
        if (chart) {
            chart.dispose();
            delete this.instances[id];
        }
    },

    resizeAll() {
        Object.values(this.instances).forEach(c => c.resize());
    },

    realtimeForceChart(id, stripCount = 30) {
        const series = [];
        for (let i = 0; i < stripCount; i++) {
            series.push({
                name: `条带${i + 1}`,
                type: 'line',
                smooth: true,
                symbol: 'none',
                lineStyle: { width: 1.5 },
                data: [],
                animationDuration: 300
            });
        }

        return this.init(id, {
            color: CHART_THEME.color,
            title: { text: '实时剥离力曲线', left: 'center', textStyle: { fontSize: 13, color: '#e0e8ff' } },
            legend: { show: false },
            xAxis: {
                type: 'category',
                data: [],
                ...CHART_THEME.xAxis,
                name: '位置 (mm)',
                nameTextStyle: { color: '#8892b0' }
            },
            yAxis: {
                type: 'value',
                ...CHART_THEME.yAxis,
                name: '力 (N)',
                max: 110,
                nameTextStyle: { color: '#8892b0' }
            },
            series: series,
            dataZoom: [{ type: 'inside', xAxisIndex: 0 }]
        });
    },

    forceBarChart(id, labels, values) {
        return this.init(id, {
            color: CHART_THEME.color,
            title: { text: '30条剥离力对比', left: 'center', textStyle: { fontSize: 13, color: '#e0e8ff' } },
            xAxis: {
                type: 'category',
                data: labels,
                ...CHART_THEME.xAxis,
                axisLabel: { ...CHART_THEME.xAxis.axisLabel, rotate: 45 }
            },
            yAxis: {
                type: 'value',
                ...CHART_THEME.yAxis,
                name: '力 (N)'
            },
            series: [{
                type: 'bar',
                data: values.map((v, i) => ({
                    value: v,
                    itemStyle: {
                        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                            { offset: 0, color: CHART_THEME.color[i % CHART_THEME.color.length] },
                            { offset: 1, color: 'rgba(0,0,0,0.3)' }
                        ])
                    }
                })),
                barWidth: '60%',
                animationDelay: (idx) => idx * 30
            }]
        });
    },

    forceDistributionChart(id, data) {
        return this.init(id, {
            title: { text: '剥离力分布', left: 'center', textStyle: { fontSize: 13, color: '#e0e8ff' } },
            xAxis: {
                type: 'category',
                data: data.map(d => `${d.range_min}-${d.range_max}`),
                ...CHART_THEME.xAxis,
                name: '力 (N)',
                axisLabel: { ...CHART_THEME.xAxis.axisLabel, rotate: 30 }
            },
            yAxis: {
                type: 'value',
                ...CHART_THEME.yAxis,
                name: '频次'
            },
            series: [{
                type: 'bar',
                data: data.map(d => d.count),
                itemStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: '#00d4ff' },
                        { offset: 1, color: 'rgba(0, 102, 255, 0.3)' }
                    ]),
                    borderRadius: [4, 4, 0, 0]
                },
                barWidth: '70%'
            }]
        });
    },

    passfailPieChart(id, pass, fail) {
        return this.init(id, {
            title: { text: '合格率', left: 'center', textStyle: { fontSize: 13, color: '#e0e8ff' } },
            series: [{
                type: 'pie',
                radius: ['40%', '70%'],
                center: ['50%', '55%'],
                avoidLabelOverlap: true,
                itemStyle: { borderRadius: 6, borderColor: '#0d1331', borderWidth: 2 },
                label: { color: '#e0e8ff', fontSize: 12 },
                data: [
                    { value: pass, name: '合格', itemStyle: { color: '#00ff88' } },
                    { value: fail, name: '不合格', itemStyle: { color: '#ff3366' } }
                ]
            }]
        });
    },

    forceVsAngleChart(id, seriesData) {
        const series = [];
        const angles = new Set();

        const grouped = {};
        seriesData.forEach(d => {
            const sn = d.strip_number;
            if (!grouped[sn]) grouped[sn] = [];
            grouped[sn].push([parseFloat(d.angle), parseFloat(d.avg_force)]);
            angles.add(parseFloat(d.angle));
        });

        const sortedAngles = [...angles].sort((a, b) => a - b);

        Object.keys(grouped).sort((a, b) => a - b).forEach(sn => {
            series.push({
                name: `条带${sn}`,
                type: 'line',
                smooth: true,
                symbol: 'none',
                lineStyle: { width: 1.5 },
                data: grouped[sn]
            });
        });

        return this.init(id, {
            color: CHART_THEME.color,
            title: { text: '剥离力-角度曲线', left: 'center', textStyle: { fontSize: 13, color: '#e0e8ff' } },
            legend: {
                type: 'scroll',
                bottom: 0,
                ...CHART_THEME.legend
            },
            xAxis: {
                type: 'value',
                ...CHART_THEME.xAxis,
                name: '角度 (°)',
                min: 0,
                max: 360
            },
            yAxis: {
                type: 'value',
                ...CHART_THEME.yAxis,
                name: '力 (N)'
            },
            series: series,
            dataZoom: [{ type: 'inside' }, { type: 'slider', bottom: 30 }]
        });
    },

    // 单条带剥离力-位移曲线（数据分析钻取用）
    forceVsPositionChart(id, points, stripNumber) {
        const data = (points || []).map(p => [parseFloat(p.position_mm), parseFloat(p.force_value)]);
        return this.init(id, {
            color: ['#00d4ff'],
            title: { text: stripNumber ? `第${stripNumber}条带 剥离力-位移曲线` : '剥离力-位移曲线',
                     left: 'center', textStyle: { fontSize: 13, color: '#e0e8ff' } },
            xAxis: { type: 'value', ...CHART_THEME.xAxis, name: '位置 (mm)' },
            yAxis: { type: 'value', ...CHART_THEME.yAxis, name: '力 (N)' },
            series: [{
                type: 'line', smooth: true, symbol: 'none', data,
                lineStyle: { width: 1.4, color: '#00d4ff' },
                areaStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: 'rgba(0,212,255,0.35)' },
                        { offset: 1, color: 'rgba(0,212,255,0.02)' }])
                },
                markLine: {
                    silent: true, symbol: 'none',
                    data: [{ yAxis: CONFIG.PASS_THRESHOLD, lineStyle: { color: '#ff3366', type: 'dashed' },
                             label: { formatter: '阈值 70N', color: '#ff3366' } },
                           { yAxis: CONFIG.GOOD_BOND_PLATFORM, lineStyle: { color: '#00ff88', type: 'dashed' },
                             label: { formatter: '平台 96N', color: '#00ff88' } }]
                }
            }],
            dataZoom: [{ type: 'inside' }, { type: 'slider', bottom: 8 }]
        });
    },

    // 累积分布曲线
    cumulativeChart(id, cumulative) {
        const data = (cumulative || []).map(c => [c.force, c.cum_pct]);
        return this.init(id, {
            title: { text: '剥离力累积分布', left: 'center', textStyle: { fontSize: 13, color: '#e0e8ff' } },
            xAxis: { type: 'value', ...CHART_THEME.xAxis, name: '力 (N)', max: 120 },
            yAxis: { type: 'value', ...CHART_THEME.yAxis, name: '累积 %', max: 100 },
            series: [{
                type: 'line', smooth: true, symbol: 'none', data,
                lineStyle: { width: 2, color: '#ffaa00' },
                areaStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: 'rgba(255,170,0,0.3)' },
                        { offset: 1, color: 'rgba(255,170,0,0.02)' }])
                }
            }]
        });
    },

    // 跨项目对比柱图（可点击联动）
    comparisonBarChart(id, labels, values, unit = 'N') {
        return this.init(id, {
            title: { text: '各项目剥离力对比', left: 'center', textStyle: { fontSize: 13, color: '#e0e8ff' } },
            tooltip: { ...CHART_THEME.tooltip, trigger: 'axis' },
            xAxis: { type: 'category', data: labels, ...CHART_THEME.xAxis,
                     axisLabel: { ...CHART_THEME.xAxis.axisLabel, rotate: 20, interval: 0 } },
            yAxis: { type: 'value', ...CHART_THEME.yAxis, name: unit },
            series: [{
                type: 'bar', data: values, barWidth: '45%',
                itemStyle: {
                    borderRadius: [6, 6, 0, 0],
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: '#00d4ff' }, { offset: 1, color: 'rgba(0,102,255,0.25)' }])
                }
            }]
        });
    },

    // 时间趋势折线（可点击联动）
    trendChart(id, labels, maxForce, passRate) {
        return this.init(id, {
            color: ['#00d4ff', '#00ff88'],
            title: { text: '剥离力趋势', left: 'center', textStyle: { fontSize: 13, color: '#e0e8ff' } },
            tooltip: { ...CHART_THEME.tooltip, trigger: 'axis' },
            legend: { data: ['峰值力(N)', '合格率(%)'], top: 24, ...CHART_THEME.legend },
            xAxis: { type: 'category', data: labels, ...CHART_THEME.xAxis,
                     axisLabel: { ...CHART_THEME.xAxis.axisLabel, rotate: 20 } },
            yAxis: [
                { type: 'value', ...CHART_THEME.yAxis, name: 'N' },
                { type: 'value', ...CHART_THEME.yAxis, name: '%', max: 100, splitLine: { show: false } }
            ],
            series: [
                { name: '峰值力(N)', type: 'line', smooth: true, data: maxForce,
                  symbolSize: 7, lineStyle: { width: 2 } },
                { name: '合格率(%)', type: 'line', yAxisIndex: 1, smooth: true, data: passRate,
                  symbolSize: 7, lineStyle: { width: 2 } }
            ]
        });
    }
};
