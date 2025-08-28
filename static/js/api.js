/**
 * API 接口封装
 * 支持缓存优先、错误处理和离线模式
 */

class StockAPI {
    constructor() {
        this.baseURL = window.location.origin;
        this.cache = window.stockCache;
        this.offlineMode = false;
        
        // 检测网络状态
        this.setupNetworkDetection();
    }
    
    /**
     * 设置网络状态检测
     */
    setupNetworkDetection() {
        window.addEventListener('online', () => {
            this.offlineMode = false;
            this.showNetworkStatus('已连接到网络', 'success');
        });
        
        window.addEventListener('offline', () => {
            this.offlineMode = true;
            this.showNetworkStatus('离线模式 - 仅显示缓存数据', 'warning');
        });
        
        // 初始状态
        this.offlineMode = !navigator.onLine;
    }
    
    /**
     * 显示网络状态
     */
    showNetworkStatus(message, type = 'info') {
        // 可以集成到现有的通知系统
        console.log(`网络状态: ${message}`);
        
        // 显示简单的状态提示
        const statusDiv = document.getElementById('network-status');
        if (statusDiv) {
            statusDiv.textContent = message;
            statusDiv.className = `alert alert-${type}`;
            statusDiv.style.display = 'block';
            
            setTimeout(() => {
                statusDiv.style.display = 'none';
            }, 3000);
        }
    }
    
    /**
     * 通用请求方法
     */
    async request(url, options = {}) {
        // 离线模式直接返回null，让调用者使用缓存
        if (this.offlineMode) {
            console.log('离线模式，跳过网络请求:', url);
            return null;
        }
        
        try {
            const response = await fetch(url, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            if (data.status === 'error') {
                throw new Error(data.message);
            }
            
            return data.data || data;
            
        } catch (error) {
            console.error('API请求失败:', error);
            
            // 网络错误，临时切换到离线模式
            if (error.name === 'TypeError' || error.message.includes('fetch')) {
                this.offlineMode = true;
                this.showNetworkStatus('网络连接失败，切换到离线模式', 'warning');
            }
            
            return null;
        }
    }
    
    /**
     * 获取可用日期列表
     */
    async getDates() {
        const cacheKey = 'available_dates';
        
        // 先尝试从缓存获取
        let cachedDates = await this.cache.getDates();
        
        // 如果离线或有缓存且缓存时间不超过1小时
        if (this.offlineMode && cachedDates) {
            console.log('离线模式：使用缓存的日期列表');
            return cachedDates;
        }
        
        // 尝试从服务器获取最新数据
        const serverDates = await this.request('/api/dates');
        
        if (serverDates) {
            // 更新缓存
            await this.cache.cacheDates(serverDates);
            return serverDates;
        } else if (cachedDates) {
            // 服务器失败，使用缓存
            console.log('服务器请求失败，使用缓存的日期列表');
            return cachedDates;
        }
        
        return [];
    }
    
    /**
     * 获取指定日期的选股结果
     */
    async getResults(date) {
        // 检查日期是否在缓存范围内
        if (!this.cache.isDateInCacheRange(date)) {
            this.showNetworkStatus(`日期 ${date} 超出30天范围，无法显示`, 'error');
            return null;
        }
        
        // 先尝试从缓存获取
        let cachedResults = await this.cache.getResults(date);
        
        // 离线模式：直接返回缓存
        if (this.offlineMode && cachedResults) {
            console.log(`离线模式：使用缓存的选股结果 - ${date}`);
            return cachedResults;
        }
        
        // 缓存优先策略：如果是当天数据且缓存中已存在，优先使用缓存
        const today = new Date().toISOString().split('T')[0];
        if (date === today && cachedResults && cachedResults.length > 0) {
            console.log(`当天数据缓存命中，优先使用缓存 - ${date}`);
            return cachedResults;
        }
        
        // 尝试从服务器获取
        const serverResults = await this.request(`/api/results/${date}`);
        
        if (serverResults) {
            // 更新缓存
            await this.cache.cacheResults(date, serverResults);
            console.log(`从服务器获取并缓存数据 - ${date}`);
            return serverResults;
        } else if (cachedResults) {
            // 服务器失败，使用缓存
            console.log(`服务器请求失败，使用缓存的选股结果 - ${date}`);
            return cachedResults;
        }
        
        return [];
    }
    
    /**
     * 获取统计信息
     */
    async getStatistics() {
        const cacheKey = 'system_stats';
        
        // 先尝试从缓存获取（缓存时间较短，10分钟）
        let cachedStats = await this.cache.getStatistics();
        
        // 检查缓存是否新鲜（10分钟内）
        const isCacheFresh = cachedStats && 
            (Date.now() - cachedStats._cached_at) < 10 * 60 * 1000;
        
        if (this.offlineMode && cachedStats) {
            console.log('离线模式：使用缓存的统计信息');
            return cachedStats;
        }
        
        // 如果在线且缓存不新鲜，尝试获取最新数据
        if (!isCacheFresh) {
            const serverStats = await this.request('/api/statistics');
            
            if (serverStats) {
                // 添加缓存时间戳
                serverStats._cached_at = Date.now();
                await this.cache.cacheStatistics(serverStats);
                return serverStats;
            }
        }
        
        // 返回缓存数据（如果有）
        if (cachedStats) {
            console.log('服务器请求失败或缓存新鲜，使用缓存的统计信息');
            return cachedStats;
        }
        
        return null;
    }
    
    /**
     * 搜索股票
     */
    async searchStocks(stocks, days = 7) {
        const searchKey = `${stocks}_${days}`;
        
        // 先尝试从缓存获取（缓存时间较短，5分钟）
        let cachedSearch = await this.cache.getSearch(searchKey);
        
        const isCacheFresh = cachedSearch && 
            (Date.now() - cachedSearch._cached_at) < 5 * 60 * 1000;
        
        if (this.offlineMode && cachedSearch) {
            console.log('离线模式：使用缓存的搜索结果');
            return cachedSearch.results;
        }
        
        // 如果在线且缓存不新鲜，尝试获取最新数据
        if (!isCacheFresh) {
            const params = new URLSearchParams({
                stocks: stocks,
                days: days.toString()
            });
            
            const serverResults = await this.request(`/api/search?${params}`);
            
            if (serverResults) {
                // 缓存搜索结果
                const cacheData = {
                    results: serverResults,
                    _cached_at: Date.now()
                };
                await this.cache.cacheSearch(searchKey, cacheData);
                return serverResults;
            }
        }
        
        // 返回缓存结果
        if (cachedSearch) {
            console.log('服务器请求失败或缓存新鲜，使用缓存的搜索结果');
            return cachedSearch.results;
        }
        
        return [];
    }
    
    /**
     * 触发缓存清理
     */
    async cleanupCache() {
        return this.request('/api/cleanup', { method: 'POST' });
    }
    
    /**
     * 预加载最近几天的数据
     */
    async preloadRecentData() {
        console.log('开始预加载最近数据...');
        
        try {
            // 获取可用日期
            const dates = await this.getDates();
            
            if (dates && dates.length > 0) {
                // 预加载最近5天的数据
                const recentDates = dates.slice(0, 5);
                
                for (const date of recentDates) {
                    await this.getResults(date);
                    // 避免并发过多，添加小延迟
                    await new Promise(resolve => setTimeout(resolve, 100));
                }
                
                console.log(`预加载完成: ${recentDates.length} 天的数据`);
            }
            
        } catch (error) {
            console.error('预加载数据失败:', error);
        }
    }
}

// 创建全局API实例
window.stockAPI = new StockAPI();

// 页面加载完成后预加载数据
document.addEventListener('DOMContentLoaded', () => {
    // 延迟预加载，避免阻塞页面渲染
    setTimeout(() => {
        window.stockAPI.preloadRecentData();
    }, 1000);
});