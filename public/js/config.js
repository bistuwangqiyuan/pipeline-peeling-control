const CONFIG = {
    API_BASE: '/api',
    POLLING_INTERVAL: 1500,
    STRIP_COUNT: 30,
    PIPE_DIAMETER: 1000,
    LAYER_WIDTH: 600,
    STRIP_WIDTH: 20,
    ESTIMATED_FORCE: 30000,
    FORCE_ALARM_HIGH: 35000,
    FORCE_ALARM_LOW: 100,
    TOKEN_KEY: 'peeling_token',
    USER_KEY: 'peeling_user',
};

const PAGES = {
    LOGIN: '/index.html',
    REGISTER: '/register.html',
    DASHBOARD: '/dashboard.html',
    CONTROL: '/control.html',
    PROJECTS: '/projects.html',
    ANALYSIS: '/analysis.html',
    REPORTS: '/reports.html',
    USERS: '/users.html',
    SETTINGS: '/settings.html',
};

const STATUS_LABELS = {
    created: '已创建',
    pending: '待执行',
    running: '运行中',
    completed: '已完成',
    aborted: '已中止',
    in_progress: '进行中',
};

const ROLE_LABELS = {
    admin: '管理员',
    user: '普通用户',
    test: '测试用户',
};
