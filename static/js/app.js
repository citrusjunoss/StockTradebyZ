/**
 * 主应用脚本
 * 处理PWA安装、页面交互和数据展示
 */

class StockApp {
    constructor() {
        this.api = window.stockAPI;
        this.cache = window.stockCache;
        this.isLoading = false;
        this.currentDate = null;
        
        // PWA相关
        this.deferredPrompt = null;
        this.isInstalled = false;
        
        this.init();
    }
    
    /**
     * 初始化应用
     */
    async init() {
        console.log('初始化股票选择系统应用');
        
        // 注册服务工作者
        this.registerServiceWorker();
        
        // 处理PWA安装
        this.handlePWAInstall();
        
        // 设置事件监听器
        this.setupEventListeners();
        
        // 检查网络状态
        this.updateNetworkStatus();
        
        // 如果在选股结果页面，加载数据
        if (window.location.pathname === '/' || window.location.pathname === '') {
            await this.loadStockResults();
        }
    }
    
    /**
     * 注册服务工作者
     */
    async registerServiceWorker() {
        if ('serviceWorker' in navigator) {
            try {
                const registration = await navigator.serviceWorker.register('/sw.js');
                console.log('服务工作者注册成功:', registration);
                
                // 监听服务工作者更新
                registration.addEventListener('updatefound', () => {
                    const newWorker = registration.installing;
                    newWorker.addEventListener('statechange', () => {
                        if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                            // 有新版本可用
                            this.showUpdateNotification();
                        }
                    });
                });
                
            } catch (error) {
                console.error('服务工作者注册失败:', error);
            }
        }
    }
    
    /**
     * 处理PWA安装
     */
    handlePWAInstall() {
        // 监听安装提示事件
        window.addEventListener('beforeinstallprompt', (e) => {
            e.preventDefault();
            this.deferredPrompt = e;
            this.showInstallButton();
        });
        
        // 监听安装完成事件
        window.addEventListener('appinstalled', () => {
            this.isInstalled = true;
            this.hideInstallButton();
            this.showToast('应用已安装到桌面', 'success');
        });
        
        // 检查是否已安装
        window.addEventListener('load', () => {
            if (window.matchMedia('(display-mode: standalone)').matches) {
                this.isInstalled = true;
                this.hideInstallButton();
            }
        });
    }
    
    /**
     * 显示安装按钮
     */
    showInstallButton() {
        const installButton = document.getElementById('install-button');
        if (installButton) {
            installButton.style.display = 'block';
            installButton.addEventListener('click', () => this.installApp());
        }
    }
    
    /**
     * 隐藏安装按钮
     */
    hideInstallButton() {
        const installButton = document.getElementById('install-button');
        if (installButton) {
            installButton.style.display = 'none';
        }
    }
    
    /**
     * 安装应用
     */
    async installApp() {
        if (this.deferredPrompt) {
            this.deferredPrompt.prompt();
            const { outcome } = await this.deferredPrompt.userChoice;
            
            if (outcome === 'accepted') {
                console.log('用户接受了安装提示');
            } else {
                console.log('用户拒绝了安装提示');
            }
            
            this.deferredPrompt = null;
        }
    }
    
    /**
     * 设置事件监听器
     */
    setupEventListeners() {
        // 页面可见性变化
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                // 页面重新可见，检查是否需要刷新数据
                this.handlePageVisible();
            }
        });
        
        // 网络状态变化
        window.addEventListener('online', () => this.updateNetworkStatus());
        window.addEventListener('offline', () => this.updateNetworkStatus());
        
        // 日期选择按钮点击
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('date-btn')) {
                const date = e.target.dataset.date;
                if (date) {
                    this.loadResultsForDate(date);
                }
            }
        });
        
        // 刷新按钮
        const refreshButton = document.getElementById('refresh-button');
        if (refreshButton) {
            refreshButton.addEventListener('click', () => this.forceRefresh());
        }
        
        // 缓存统计按钮
        const cacheStatsButton = document.getElementById('cache-stats-button');
        if (cacheStatsButton) {
            cacheStatsButton.addEventListener('click', () => this.showCacheStats());
        }
    }
    
    /**
     * 页面重新可见时的处理
     */
    async handlePageVisible() {
        // 如果离线超过5分钟，尝试刷新数据
        const lastActivity = localStorage.getItem('lastActivity');
        if (lastActivity) {
            const timeDiff = Date.now() - parseInt(lastActivity);
            if (timeDiff > 5 * 60 * 1000) { // 5分钟
                await this.refreshCurrentData();
            }
        }
        
        localStorage.setItem('lastActivity', Date.now().toString());
    }
    
    /**
     * 加载选股结果
     */
    async loadStockResults() {
        if (this.isLoading) return;
        
        this.isLoading = true;
        this.showLoading();
        
        try {
            // 从URL获取日期参数
            const urlParams = new URLSearchParams(window.location.search);
            const dateParam = urlParams.get('date');
            
            if (dateParam) {
                await this.loadResultsForDate(dateParam);
            } else {
                // 加载最新日期的结果
                await this.loadLatestResults();
            }
            
        } catch (error) {
            console.error('加载选股结果失败:', error);
            this.showError('加载选股结果失败，请稍后重试');
        } finally {
            this.isLoading = false;
            this.hideLoading();
        }
    }
    
    /**
     * 加载最新结果
     */
    async loadLatestResults() {
        const dates = await this.api.getDates();
        if (dates && dates.length > 0) {
            await this.loadResultsForDate(dates[0]);
        } else {
            this.showError('暂无可用的选股结果');
        }
    }
    
    /**
     * 加载指定日期的结果
     */
    async loadResultsForDate(date) {
        this.currentDate = date;
        
        try {
            const results = await this.api.getResults(date);
            
            if (results && results.length > 0) {
                this.renderResults(results, date);
                this.updateURL(date);
            } else {
                this.showEmptyState(date);
            }
            
        } catch (error) {
            console.error(`加载 ${date} 的结果失败:`, error);
            this.showError(`加载 ${date} 的结果失败`);
        }
    }
    
    /**
     * 渲染选股结果
     */
    renderResults(results, date) {
        // 这里可以根据具体的HTML结构来渲染数据
        console.log(`渲染 ${date} 的选股结果:`, results);
        
        // 更新页面标题
        document.title = `${date} 选股结果 - 股票选择系统`;
        
        // 触发自定义事件，让其他组件知道数据已更新
        const event = new CustomEvent('resultsLoaded', {
            detail: { date, results }
        });
        document.dispatchEvent(event);
    }
    
    /**
     * 显示空状态
     */
    showEmptyState(date) {
        console.log(`${date} 无选股结果`);
        this.showToast(`${date} 暂无选股结果`, 'info');
    }
    
    /**
     * 更新URL
     */
    updateURL(date) {
        const url = new URL(window.location);
        url.searchParams.set('date', date);
        window.history.pushState({ date }, '', url);
    }
    
    /**
     * 强制刷新数据
     */
    async forceRefresh() {
        if (this.currentDate) {
            // 清除缓存中的当前日期数据
            await this.cache.deleteCache(this.cache.stores.results, this.currentDate);
            
            // 重新加载
            await this.loadResultsForDate(this.currentDate);
            
            this.showToast('数据已刷新', 'success');
        }
    }
    
    /**
     * 刷新当前数据
     */
    async refreshCurrentData() {
        if (navigator.onLine && this.currentDate) {
            console.log('刷新当前数据...');
            // 静默刷新，不显示加载状态
            const results = await this.api.getResults(this.currentDate);
            if (results) {
                this.renderResults(results, this.currentDate);
            }
        }
    }
    
    /**
     * 显示缓存统计
     */
    async showCacheStats() {
        const stats = await this.cache.getCacheStats();
        const systemStats = await this.api.getStatistics();
        
        let message = '缓存统计信息：\\n\\n';
        for (const [key, count] of Object.entries(stats)) {
            message += `${key}: ${count} 条记录\\n`;
        }
        
        if (systemStats) {
            message += `\\n服务器统计：\\n`;
            message += `总记录数: ${systemStats.system?.total_records || 0}\\n`;
            message += `数据库大小: ${systemStats.system?.database_size_mb || 0}MB`;
        }
        
        alert(message);
    }
    
    /**
     * 更新网络状态显示
     */
    updateNetworkStatus() {
        const statusElement = document.getElementById('network-status');
        if (statusElement) {
            if (navigator.onLine) {
                statusElement.textContent = '';
                statusElement.style.display = 'none';
            } else {
                statusElement.textContent = '离线模式 - 仅显示缓存数据';
                statusElement.className = 'alert alert-warning';
                statusElement.style.display = 'block';
            }
        }
    }
    
    /**
     * 显示加载状态
     */
    showLoading() {
        const loadingElement = document.getElementById('loading');
        if (loadingElement) {
            loadingElement.style.display = 'block';
        }
    }
    
    /**
     * 隐藏加载状态
     */
    hideLoading() {
        const loadingElement = document.getElementById('loading');
        if (loadingElement) {
            loadingElement.style.display = 'none';
        }
    }
    
    /**
     * 显示错误消息
     */
    showError(message) {
        this.showToast(message, 'error');
    }
    
    /**
     * 显示提示消息
     */
    showToast(message, type = 'info') {
        // 简单的toast实现
        const toast = document.createElement('div');
        toast.className = `alert alert-${type} position-fixed`;
        toast.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        toast.textContent = message;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.remove();
        }, 3000);
    }
    
    /**
     * 显示更新通知
     */
    showUpdateNotification() {
        const message = '有新版本可用，是否立即更新？';
        if (confirm(message)) {
            if ('serviceWorker' in navigator) {
                navigator.serviceWorker.controller.postMessage({ type: 'SKIP_WAITING' });
                window.location.reload();
            }
        }
    }
}

// 创建应用实例
let stockApp;

// 页面加载完成后初始化应用
document.addEventListener('DOMContentLoaded', () => {
    stockApp = new StockApp();
});

// 导出到全局作用域
window.stockApp = stockApp;