import json
import sys
sys.path.append('c:/Users/dopa.mine/Desktop/ophelia')
from research.data_pipeline.cvd_bulk_pipeline import process_month, load_json, save_json, MANIFEST_PATH

manifest = load_json(MANIFEST_PATH)
for month in range(1, 9):
    mk = f"XRPUSDT-2022-{month:02d}"
    if mk in manifest and manifest[mk].get('final_status') == 'QUARANTINED':
        # Remove from manifest to force reprocessing
        del manifest[mk]
        save_json(manifest, MANIFEST_PATH)
    
    print(f"Processing {mk}...")
    res = process_month("XRPUSDT", 2022, month, manifest)
    print(res)
