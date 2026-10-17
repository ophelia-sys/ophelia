import json
import os
import hashlib
import time
from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict

class PromotionState(str, Enum):
    CANDIDATE = "CANDIDATE"
    LEAKAGE_PASS = "LEAKAGE_PASS"
    DEV_PASS = "DEV_PASS"
    OOS_PASS = "OOS_PASS"
    COST_PASS = "COST_PASS"
    STABILITY_PASS = "STABILITY_PASS"
    MULTIPLE_TESTING_PASS = "MULTIPLE_TESTING_PASS"
    PRODUCTION_CANDIDATE = "PRODUCTION_CANDIDATE"
    REJECTED = "REJECTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    UNTESTED = "UNTESTED"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"

@dataclass
class HypothesisFamily:
    family_id: str
    experiment_id: str
    feature_id: str
    dataset_hash: str
    family_size: int
    hypotheses: List[Dict[str, Any]] = field(default_factory=list)
    correction_method: str = "Benjamini-Hochberg FDR"
    global_fdr_threshold: float = 0.05
    timestamp: float = field(default_factory=time.time)

@dataclass
class FeatureRecord:
    feature_id: str
    name: str
    definition: str
    raw_dependencies: List[str]
    exchange: str
    timeframe: str
    
    # Lineage / History
    experiment_id: Optional[str] = None
    dataset_hash: Optional[str] = None
    
    # Parameters and selection
    parameters: Dict[str, Any] = field(default_factory=dict)
    parameter_selection_method: str = ""
    
    # Performance
    dev_performance: Dict[str, Any] = field(default_factory=dict)
    oos_performance: Dict[str, Any] = field(default_factory=dict)
    transaction_cost_performance: Dict[str, Any] = field(default_factory=dict)
    
    # Statistics
    statistical_methodology: str = ""
    multiple_testing_treatment: str = ""
    stability_results: Dict[str, Any] = field(default_factory=dict)
    
    # Status
    status: PromotionState = PromotionState.CANDIDATE
    rejection_reason: Optional[str] = None
    
    def advance_state(self, new_state: PromotionState):
        if self.status == PromotionState.REJECTED:
            raise ValueError(f"Feature {self.feature_id} is permanently REJECTED.")
        self.status = new_state
        
    def reject(self, reason: str):
        self.status = PromotionState.REJECTED
        self.rejection_reason = reason


class FeatureRegistry:
    def __init__(self, registry_path: str = "research/phase6/feature_registry.json"):
        self.registry_path = registry_path
        self.features: Dict[str, FeatureRecord] = {}
        self.families: Dict[str, HypothesisFamily] = {}
        self.load()
        
    def _ensure_dir(self):
        os.makedirs(os.path.dirname(self.registry_path), exist_ok=True)
        
    def load(self):
        if not os.path.exists(self.registry_path):
            return
            
        with open(self.registry_path, 'r') as f:
            data = json.load(f)
            
        for k, v in data.get("features", {}).items():
            # Convert status string back to Enum
            status_str = v.pop("status", PromotionState.CANDIDATE.value)
            v["status"] = PromotionState(status_str)
            self.features[k] = FeatureRecord(**v)
            
        for k, v in data.get("families", {}).items():
            self.families[k] = HypothesisFamily(**v)
            
    def save(self):
        self._ensure_dir()
        data = {
            "features": {k: asdict(v) for k, v in self.features.items()},
            "families": {k: asdict(v) for k, v in self.families.items()}
        }
        with open(self.registry_path, 'w') as f:
            json.dump(data, f, indent=4)
            
    def register_feature(self, record: FeatureRecord):
        if record.feature_id in self.features and self.features[record.feature_id].status == PromotionState.REJECTED:
            # Prevent silent overwriting of a rejected formulation.
            raise ValueError(f"Feature {record.feature_id} is already registered and REJECTED. Create a new version/feature_id for a different formulation.")
        self.features[record.feature_id] = record
        self.save()
        
    def register_hypothesis_family(self, family: HypothesisFamily):
        if family.family_id in self.families:
            raise ValueError(f"Family {family.family_id} already exists.")
        self.families[family.family_id] = family
        self.save()
        
    def get_feature(self, feature_id: str) -> Optional[FeatureRecord]:
        return self.features.get(feature_id)
