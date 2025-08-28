/**
 * 前端缓存系统 - 基于IndexedDB
 * 支持数据缓存、过期清理和离线访问
 */

class StockCacheManager {
    constructor() {
        this.dbName = 'StockTraderCache';
        this.dbVersion = 1;
        this.db = null;
        this.maxCacheDays = 30;
        
        // 存储对象名称
        this.stores = {
            results: 'stock_results',      // 选股结果
            dates: 'available_dates',      // 可用日期
            statistics: 'statistics',      // 统计信息
            searches: 'search_results'     // 搜索结果
        };
        
        this.init();
    }
    
    /**
     * 初始化IndexedDB
     */
    async init() {
        try {
            this.db = await this.openDB();
            console.log('缓存数据库初始化成功');
            
            // 启动时清理过期数据
            this.cleanupExpiredData();
            
        } catch (error) {
            console.error('缓存数据库初始化失败:', error);
        }
    }
    
    /**
     * 打开IndexedDB连接
     */
    openDB() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(this.dbName, this.dbVersion);
            
            request.onerror = () => reject(request.error);
            request.onsuccess = () => resolve(request.result);
            
            request.onupgradeneeded = (event) => {
                const db = event.target.result;
                
                // 创建存储对象
                Object.values(this.stores).forEach(storeName => {
                    if (!db.objectStoreNames.contains(storeName)) {
                        const store = db.createObjectStore(storeName, { keyPath: 'key' });
                        store.createIndex('timestamp', 'timestamp', { unique: false });
                        store.createIndex('date', 'date', { unique: false });
                    }
                });
            };
        });
    }
    
    /**
     * 存储数据到缓存
     */
    async setCache(storeName, key, data, date = null) {
        if (!this.db) {
            console.warn('缓存数据库未初始化');
            return false;
        }
        
        try {
            const transaction = this.db.transaction([storeName], 'readwrite');
            const store = transaction.objectStore(storeName);
            
            const cacheData = {
                key: key,
                data: data,
                timestamp: Date.now(),
                date: date || new Date().toISOString().split('T')[0],
                expires: Date.now() + (this.maxCacheDays * 24 * 60 * 60 * 1000)
            };
            
            await new Promise((resolve, reject) => {
                const request = store.put(cacheData);
                request.onsuccess = () => resolve(request.result);
                request.onerror = () => reject(request.error);
            });
            
            console.log(`数据已缓存: ${storeName}/${key}`);
            return true;
            
        } catch (error) {
            console.error('缓存数据失败:', error);
            return false;
        }
    }
    
    /**
     * 从缓存获取数据
     */
    async getCache(storeName, key) {
        if (!this.db) {
            console.warn('缓存数据库未初始化');
            return null;
        }
        
        try {
            const transaction = this.db.transaction([storeName], 'readonly');
            const store = transaction.objectStore(storeName);
            
            const cacheData = await new Promise((resolve, reject) => {
                const request = store.get(key);
                request.onsuccess = () => resolve(request.result);
                request.onerror = () => reject(request.error);
            });
            
            if (!cacheData) {
                return null;
            }
            
            // 检查是否过期
            if (Date.now() > cacheData.expires) {
                console.log(`缓存已过期: ${storeName}/${key}`);
                this.deleteCache(storeName, key);
                return null;
            }
            
            console.log(`从缓存获取数据: ${storeName}/${key}`);
            return cacheData.data;
            
        } catch (error) {
            console.error('获取缓存数据失败:', error);
            return null;
        }
    }
    
    /**
     * 删除缓存数据
     */
    async deleteCache(storeName, key) {
        if (!this.db) return false;
        
        try {
            const transaction = this.db.transaction([storeName], 'readwrite');
            const store = transaction.objectStore(storeName);
            
            await new Promise((resolve, reject) => {
                const request = store.delete(key);
                request.onsuccess = () => resolve(request.result);
                request.onerror = () => reject(request.error);
            });
            
            console.log(`缓存已删除: ${storeName}/${key}`);
            return true;
            
        } catch (error) {
            console.error('删除缓存失败:', error);
            return false;
        }
    }
    
    /**
     * 清理过期数据
     */
    async cleanupExpiredData() {
        if (!this.db) return;
        
        console.log('开始清理过期缓存数据...');
        const now = Date.now();
        const cutoffDate = new Date(now - (this.maxCacheDays * 24 * 60 * 60 * 1000))
            .toISOString().split('T')[0];
        
        for (const storeName of Object.values(this.stores)) {
            try {
                const transaction = this.db.transaction([storeName], 'readwrite');
                const store = transaction.objectStore(storeName);
                const index = store.index('timestamp');
                
                const request = index.openCursor();
                let deletedCount = 0;
                
                await new Promise((resolve) => {
                    request.onsuccess = (event) => {
                        const cursor = event.target.result;
                        if (cursor) {
                            const record = cursor.value;
                            
                            // 删除过期或超过30天的数据
                            if (now > record.expires || record.date < cutoffDate) {
                                cursor.delete();
                                deletedCount++;
                            }
                            cursor.continue();
                        } else {
                            resolve();
                        }
                    };
                });
                
                if (deletedCount > 0) {
                    console.log(`${storeName}: 清理了 ${deletedCount} 条过期数据`);
                }
                
            } catch (error) {
                console.error(`清理 ${storeName} 失败:`, error);
            }
        }
    }
    
    /**
     * 获取缓存统计信息
     */
    async getCacheStats() {
        if (!this.db) return null;
        
        const stats = {};
        
        for (const [key, storeName] of Object.entries(this.stores)) {
            try {
                const transaction = this.db.transaction([storeName], 'readonly');
                const store = transaction.objectStore(storeName);
                
                const count = await new Promise((resolve, reject) => {
                    const request = store.count();
                    request.onsuccess = () => resolve(request.result);
                    request.onerror = () => reject(request.error);
                });
                
                stats[key] = count;
                
            } catch (error) {
                console.error(`获取 ${storeName} 统计失败:`, error);
                stats[key] = 0;
            }
        }
        
        return stats;
    }
    
    /**
     * 清空所有缓存
     */
    async clearAllCache() {
        if (!this.db) return false;
        
        try {
            for (const storeName of Object.values(this.stores)) {
                const transaction = this.db.transaction([storeName], 'readwrite');
                const store = transaction.objectStore(storeName);
                await new Promise((resolve, reject) => {
                    const request = store.clear();
                    request.onsuccess = () => resolve(request.result);
                    request.onerror = () => reject(request.error);
                });
            }
            
            console.log('所有缓存已清空');
            return true;
            
        } catch (error) {
            console.error('清空缓存失败:', error);
            return false;
        }
    }
    
    /**
     * 检查日期是否在缓存范围内（30天内）
     */
    isDateInCacheRange(dateStr) {
        const targetDate = new Date(dateStr);
        const today = new Date();
        const thirtyDaysAgo = new Date(today.getTime() - (this.maxCacheDays * 24 * 60 * 60 * 1000));
        
        return targetDate >= thirtyDaysAgo && targetDate <= today;
    }
    
    // 便捷方法：选股结果缓存
    async cacheResults(date, results) {
        return this.setCache(this.stores.results, date, results, date);
    }
    
    async getResults(date) {
        if (!this.isDateInCacheRange(date)) {
            console.log(`日期 ${date} 超出缓存范围（30天）`);
            return null;
        }
        return this.getCache(this.stores.results, date);
    }
    
    // 便捷方法：可用日期缓存
    async cacheDates(dates) {
        return this.setCache(this.stores.dates, 'available_dates', dates);
    }
    
    async getDates() {
        return this.getCache(this.stores.dates, 'available_dates');
    }
    
    // 便捷方法：统计信息缓存
    async cacheStatistics(stats) {
        return this.setCache(this.stores.statistics, 'system_stats', stats);
    }
    
    async getStatistics() {
        return this.getCache(this.stores.statistics, 'system_stats');
    }
    
    // 便捷方法：搜索结果缓存
    async cacheSearch(searchKey, results) {
        return this.setCache(this.stores.searches, searchKey, results);
    }
    
    async getSearch(searchKey) {
        return this.getCache(this.stores.searches, searchKey);
    }
}

// 创建全局缓存管理器实例
window.stockCache = new StockCacheManager();