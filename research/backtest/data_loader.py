import os
import os
import json
from typing import Dict, Any

class ParquetDataLoader:
    """
    DuckDB-backed data loader for canonical Ophelia Parquet datasets.
    Provides lazy/chunked chronological access without OOMing.
    """
    def __init__(self, manifest_dir: str = "data/manifests", data_dir: str = "data/normalized/v1"):
        self.manifest_dir = manifest_dir
        self.data_dir = data_dir
        
        try:
            import duckdb
            self.con = duckdb.connect(database=':memory:')
        except ImportError:
            self.con = None
            # We don't raise immediately, so that pytest can collect and we can mock it if needed.
            # raise ImportError("DuckDB is required for historical backtesting. Please install duckdb.")

    def load_dataset(self, dataset_id: str) -> Dict[str, Any]:
        """
        Hard-fails if the dataset_id is missing locally.
        NEVER silently downloads.
        """
        manifest_path = os.path.join(self.manifest_dir, f"{dataset_id}.json")
        if not os.path.exists(manifest_path):
            raise FileNotFoundError(f"Manifest for {dataset_id} not found at {manifest_path}. Dataset must be downloaded manually first.")
            
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
            
        parquet_file = os.path.join(self.data_dir, f"{dataset_id}.parquet")
        if not os.path.exists(parquet_file):
            raise FileNotFoundError(f"Parquet data for {dataset_id} not found at {parquet_file}.")
            
        if self.con is None:
            raise ImportError("DuckDB is required to query parquet files. Please install duckdb.")
            
        # Register view in DuckDB
        self.con.execute(f"CREATE OR REPLACE VIEW '{dataset_id}' AS SELECT * FROM read_parquet('{parquet_file}') ORDER BY timestamp ASC")
        
        return manifest

    def get_chronological_iterator(self, dataset_id: str, start_ts: int = None, end_ts: int = None, chunk_size: int = 100000):
        """
        Returns a lazy iterator over chronological chunks.
        """
        query = f"SELECT * FROM '{dataset_id}'"
        filters = []
        if start_ts is not None:
            filters.append(f"timestamp >= {start_ts}")
        if end_ts is not None:
            filters.append(f"timestamp <= {end_ts}")
            
        if filters:
            query += " WHERE " + " AND ".join(filters)
            
        query += " ORDER BY timestamp ASC"
        
        if self.con is None:
            raise ImportError("DuckDB is required to fetch chunks. Please install duckdb.")
        
        # duckdb fetch_arrow_table or fetchdf iteratively
        # In a real environment we can yield chunked arrows.
        # For this simulation wrapper we'll return a duckdb relation that can be fetched in chunks.
        rel = self.con.sql(query)
        return rel
