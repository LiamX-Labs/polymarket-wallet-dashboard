import { SyncService } from './src/sync';
import path from 'path';

const TRACKER_DB = path.join(__dirname, '../data/tracker.sqlite3');
const DASHBOARD_DB = path.join(__dirname, '../data/dashboard.db');

console.log('Testing sync service...\n');
console.log('Tracker DB:', TRACKER_DB);
console.log('Dashboard DB:', DASHBOARD_DB);
console.log('');

const sync = new SyncService(TRACKER_DB, DASHBOARD_DB);
sync.sync();
sync.close();

console.log('\nSync test complete!');
