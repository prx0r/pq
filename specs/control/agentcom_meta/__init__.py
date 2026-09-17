"""AgentCom meta-kernel: package resolver, QP Processor ABI, planner, tournament lab."""
from .processor import ProcessorManifest, ProcessorResult, ProcessorStatus
from .registry import ProcessorRegistry
from .planner import ProofNeed, ProcessorPlan, plan_processors
from .experiment import FiveLaneLab
__all__=["ProcessorManifest","ProcessorResult","ProcessorStatus","ProcessorRegistry","ProofNeed","ProcessorPlan","plan_processors","FiveLaneLab"]
__version__="0.7.0"
