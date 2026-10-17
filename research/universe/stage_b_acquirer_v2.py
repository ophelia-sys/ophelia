import asyncio
import aiohttp
import sqlite3
import pandas as pd
import zipfile
import io
import os
import time
import hashlib
import calendar
import shutil
import logging
from datetime import datetime
from aiohttp import ClientTimeout

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('StageBAcquirer')

DB_PATH = 'data/processed/stage_b_jobs.sqlite'
MANIFEST_PATH = 'research/phase7/stage_b_acquisition_manifest.parquet'
OUT_BASE = 'data/processed'

class AcquisitionEngine:
    def __init__(self):
        self.concurrency = 20
        self.max_concurrency = 200
        self.active_requests = 0
        self.semaphore = asyncio.Semaphore(self.concurrency)
        
        self.success_count = 0
        self.error_count = 0
        self.retry_count = 0
        self.consecutive_errors = 0
        self.bytes_downloaded = 0
        self.start_time = time.time()
        
        self._init_db()

    def _init_db(self):
        os.makedirs(OUT_BASE, exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS jobs (
                        job_id TEXT PRIMARY KEY,
                        symbol TEXT,
                        dataset_type TEXT,
                        period TEXT,
                        url TEXT,
                        status TEXT,
                        attempt_count INTEGER,
                        last_error TEXT,
                        http_status INTEGER,
                        bytes_downloaded INTEGER,
                        output_path TEXT,
                        output_sha256 TEXT,
                        source_checksum_status TEXT,
                        started_at TEXT,
                        completed_at TEXT
                    )''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_status ON jobs(status)')
        conn.commit()
        
        # Populate if empty
        c.execute("SELECT COUNT(*) FROM jobs")
        if c.fetchone()[0] == 0:
            self._populate_jobs(conn)
        conn.close()

    def _populate_jobs(self, conn):
        logger.info("Populating jobs from manifest...")
        manifest = pd.read_parquet(MANIFEST_PATH)
        jobs = []
        for _, row in manifest.iterrows():
            sym = row['symbol']
            ym = row['year_month']
            y, m = ym.split('-')
            
            # Kline (monthly)
            k_id = f"kline_{sym}_{ym}"
            k_url = f"https://data.binance.vision/data/futures/um/monthly/klines/{sym}/1m/{sym}-1m-{ym}.zip"
            jobs.append((k_id, sym, 'kline', ym, k_url, 'PENDING', 0, '', 0, 0, '', '', 'SOURCE_CHECKSUM_NOT_AVAILABLE', '', ''))
            
            # Funding (monthly)
            f_id = f"funding_{sym}_{ym}"
            f_url = f"https://data.binance.vision/data/futures/um/monthly/fundingRate/{sym}/{sym}-fundingRate-{ym}.zip"
            jobs.append((f_id, sym, 'funding', ym, f_url, 'PENDING', 0, '', 0, 0, '', '', 'SOURCE_CHECKSUM_NOT_AVAILABLE', '', ''))
            
            # OI (daily)
            days = calendar.monthrange(int(y), int(m))[1]
            for d in range(1, days + 1):
                ymd = f"{ym}-{d:02d}"
                o_id = f"oi_{sym}_{ymd}"
                o_url = f"https://data.binance.vision/data/futures/um/daily/metrics/{sym}/{sym}-metrics-{ymd}.zip"
                jobs.append((o_id, sym, 'oi', ymd, o_url, 'PENDING', 0, '', 0, 0, '', '', 'SOURCE_CHECKSUM_NOT_AVAILABLE', '', ''))
                
        c = conn.cursor()
        c.executemany("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", jobs)
        conn.commit()
        logger.info(f"Inserted {len(jobs)} jobs.")

    def update_job(self, job_id, status, attempt_count, last_error, http_status, bytes_dl, out_path, sha, started, completed):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""UPDATE jobs SET 
                     status=?, attempt_count=?, last_error=?, http_status=?, bytes_downloaded=?, 
                     output_path=?, output_sha256=?, started_at=?, completed_at=? 
                     WHERE job_id=?""",
                  (status, attempt_count, last_error, http_status, bytes_dl, out_path, sha, started, completed, job_id))
        conn.commit()
        conn.close()

    def get_pending_jobs(self, limit=10000):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT * FROM jobs WHERE status IN ('PENDING', 'RETRY') LIMIT ?", (limit,))
        rows = c.fetchall()
        
        # Mark as DOWNLOADING
        ids = [r[0] for r in rows]
        if ids:
            c.execute(f"UPDATE jobs SET status='DOWNLOADING' WHERE job_id IN ({','.join(['?']*len(ids))})", ids)
            conn.commit()
        conn.close()
        
        columns = ['job_id', 'symbol', 'dataset_type', 'period', 'url', 'status', 'attempt_count', 
                   'last_error', 'http_status', 'bytes_downloaded', 'output_path', 'output_sha256', 
                   'source_checksum_status', 'started_at', 'completed_at']
        return [dict(zip(columns, r)) for r in rows]

    def adjust_concurrency(self, is_success, http_status=200):
        if not is_success:
            self.consecutive_errors += 1
            if http_status == 429 or self.consecutive_errors > 5:
                # Halve concurrency on 429 or continuous errors
                new_c = max(10, self.concurrency // 2)
                if new_c != self.concurrency:
                    logger.warning(f"Downgrading concurrency: {self.concurrency} -> {new_c}")
                    self.concurrency = new_c
                    self.semaphore = asyncio.Semaphore(self.concurrency)
        else:
            self.consecutive_errors = 0
            if self.success_count % 100 == 0 and self.concurrency < self.max_concurrency:
                new_c = min(self.max_concurrency, self.concurrency + 20)
                if new_c != self.concurrency:
                    logger.info(f"Ramping up concurrency: {self.concurrency} -> {new_c}")
                    self.concurrency = new_c
                    self.semaphore = asyncio.Semaphore(self.concurrency)

    async def worker(self, session, job):
        job_id = job['job_id']
        attempt = job['attempt_count'] + 1
        started = datetime.utcnow().isoformat()
        
        async with self.semaphore:
            self.active_requests += 1
            try:
                async with session.get(job['url'], timeout=ClientTimeout(total=45)) as resp:
                    http_status = resp.status
                    if http_status == 200:
                        data = await resp.read()
                        self.bytes_downloaded += len(data)
                        
                        # Parse
                        df = None
                        with zipfile.ZipFile(io.BytesIO(data)) as z:
                            for name in z.namelist():
                                if name.endswith('.csv'):
                                    h = None if job['dataset_type'] == 'kline' else 0
                                    df = pd.read_csv(z.open(name), header=h)
                                    break
                                    
                        if df is not None and not df.empty:
                            # Validation and processing logic...
                            if job['dataset_type'] == 'kline':
                                if str(df.iloc[0, 0]).isalpha() or 'open_time' in str(df.iloc[0, 0]):
                                    df = df.iloc[1:].reset_index(drop=True)
                                df.columns = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume", "count", "taker_buy_volume", "taker_buy_quote_volume", "ignore"]
                                df['open_time'] = pd.to_numeric(df['open_time'])
                                df['timestamp'] = pd.to_datetime(df['open_time'], unit='ms')
                                df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume', 'quote_volume', 'taker_buy_quote_volume']]
                                df['open'] = pd.to_numeric(df['open'])
                                out_dir = f"research_universe_1m.parquet/symbol={job['symbol']}/year_month={job['period']}"
                            
                            elif job['dataset_type'] == 'funding':
                                if 'calc_time' in df.columns:
                                    df['timestamp'] = pd.to_datetime(df['calc_time'], unit='ms')
                                    if 'last_funding_rate' in df.columns:
                                        df.rename(columns={'last_funding_rate': 'funding_rate'}, inplace=True)
                                    df = df[['timestamp', 'funding_rate']]
                                    df['funding_rate'] = pd.to_numeric(df['funding_rate'])
                                    out_dir = f"research_funding.parquet/symbol={job['symbol']}/year_month={job['period']}"
                                else:
                                    raise ValueError("Missing calc_time")
                                    
                            elif job['dataset_type'] == 'oi':
                                df['timestamp'] = pd.to_datetime(df['create_time'])
                                df = df[['timestamp', 'sum_open_interest', 'sum_open_interest_value']]
                                ym = job['period'][:7]
                                out_dir = f"research_oi_5m.parquet/symbol={job['symbol']}/year_month={ym}"
                            
                            # Write Parquet safely
                            out_base_dir = os.path.join(OUT_BASE, out_dir)
                            os.makedirs(out_base_dir, exist_ok=True)
                            
                            # For daily files (OI), append to month or write daily part
                            # We will write daily parts to avoid loading whole month
                            out_file = os.path.join(out_base_dir, f"part_{job['period']}.parquet")
                            df.to_parquet(out_file, index=False)
                            
                            # Hash
                            with open(out_file, 'rb') as f:
                                file_hash = hashlib.sha256(f.read()).hexdigest()
                                
                            self.success_count += 1
                            self.adjust_concurrency(True)
                            self.update_job(job_id, 'VALIDATED', attempt, '', 200, len(data), out_file, file_hash, started, datetime.utcnow().isoformat())
                            
                        else:
                            self.update_job(job_id, 'FAILED', attempt, 'EMPTY_CSV', 200, len(data), '', '', started, datetime.utcnow().isoformat())
                            
                    elif http_status == 404:
                        self.update_job(job_id, 'MASKED', attempt, '404_NOT_FOUND', 404, 0, '', '', started, datetime.utcnow().isoformat())
                    else:
                        raise Exception(f"HTTP {http_status}")
            
            except Exception as e:
                self.error_count += 1
                status = 'RETRY' if attempt < 3 else 'FAILED'
                self.adjust_concurrency(False, getattr(e, 'status', 500))
                self.update_job(job_id, status, attempt, str(e), getattr(e, 'status', 0), 0, '', '', started, datetime.utcnow().isoformat())
                
                if status == 'RETRY':
                    await asyncio.sleep(2 ** attempt) # Jitter/backoff
            
            finally:
                self.active_requests -= 1

    async def run(self):
        disk_total, _, disk_free = shutil.disk_usage("/")
        if disk_free < 5 * 1024**3:
            logger.error("Less than 5GB disk free. Aborting.")
            return

        connector = aiohttp.TCPConnector(limit=0) # We manage limit via Semaphore
        async with aiohttp.ClientSession(connector=connector) as session:
            while True:
                jobs = self.get_pending_jobs(limit=5000)
                if not jobs:
                    break
                    
                logger.info(f"Loaded {len(jobs)} pending jobs. Current concurrency: {self.concurrency}")
                
                tasks = []
                for job in jobs:
                    tasks.append(asyncio.create_task(self.worker(session, job)))
                
                # We can't await all 5000 directly because we want telemetry
                # So we gather them and print telemetry occasionally
                done_count = 0
                for f in asyncio.as_completed(tasks):
                    await f
                    done_count += 1
                    if done_count % 500 == 0:
                        elapsed = time.time() - self.start_time
                        rps = (self.success_count + self.error_count) / elapsed
                        mb_dl = self.bytes_downloaded / (1024**2)
                        logger.info(f"Progress: {done_count}/{len(jobs)} | Concurrency: {self.concurrency} | RPS: {rps:.1f} | Success: {self.success_count} | DL: {mb_dl:.1f} MB")

        logger.info("Acquisition Complete.")

if __name__ == "__main__":
    engine = AcquisitionEngine()
    asyncio.run(engine.run())
