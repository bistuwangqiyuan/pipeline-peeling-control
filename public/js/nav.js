const Nav = {
    init() {
        this.renderSidebar();
        this.highlightCurrent();
        this.bindEvents();
    },

    renderSidebar() {
        const sidebar = document.getElementById('sidebar');
        if (!sidebar) return;

        const user = Auth.getUser();
        const isAdmin = user && user.role === 'admin';
        const initial = user ? user.username.charAt(0).toUpperCase() : '?';

        sidebar.innerHTML = `
            <div class="sidebar-brand">
                <div class="brand-icon">⚙</div>
                <div>
                    <div class="brand-text">管道剥离控制系统</div>
                    <div class="brand-sub">Pipeline Peeling Control</div>
                </div>
            </div>
            <nav class="sidebar-nav">
                <div class="nav-section">监控中心</div>
                <a href="/dashboard.html" class="nav-item" data-page="dashboard">
                    <span class="nav-icon">📊</span>
                    <span>实时监控大屏</span>
                </a>
                <a href="/control.html" class="nav-item" data-page="control">
                    <span class="nav-icon">🎛</span>
                    <span>试验控制</span>
                </a>
                <div class="nav-section">数据管理</div>
                <a href="/projects.html" class="nav-item" data-page="projects">
                    <span class="nav-icon">📁</span>
                    <span>项目管理</span>
                </a>
                <a href="/analysis.html" class="nav-item" data-page="analysis">
                    <span class="nav-icon">📈</span>
                    <span>数据分析</span>
                </a>
                <a href="/reports.html" class="nav-item" data-page="reports">
                    <span class="nav-icon">📋</span>
                    <span>试验报告</span>
                </a>
                ${isAdmin ? `
                <div class="nav-section">系统管理</div>
                <a href="/users.html" class="nav-item" data-page="users">
                    <span class="nav-icon">👥</span>
                    <span>用户管理</span>
                </a>
                ` : ''}
                <a href="/settings.html" class="nav-item" data-page="settings">
                    <span class="nav-icon">⚙</span>
                    <span>系统设置</span>
                </a>
            </nav>
            <div class="sidebar-footer">
                <div class="user-info" onclick="Auth.logout()">
                    <div class="user-avatar">${initial}</div>
                    <div>
                        <div class="user-name">${user ? user.username : '未登录'}</div>
                        <div class="user-role">${user ? (ROLE_LABELS[user.role] || user.role) : ''} · 点击退出</div>
                    </div>
                </div>
            </div>
        `;
    },

    highlightCurrent() {
        const path = window.location.pathname;
        document.querySelectorAll('.nav-item').forEach(item => {
            const href = item.getAttribute('href');
            if (href && path.includes(href.replace('.html', ''))) {
                item.classList.add('active');
            }
        });
    },

    bindEvents() {
        const menuBtn = document.getElementById('menu-toggle');
        const sidebar = document.getElementById('sidebar');
        if (menuBtn && sidebar) {
            menuBtn.addEventListener('click', () => {
                sidebar.classList.toggle('open');
            });
        }
    }
};
