# Agent Specification

Agent = Constitutional Prompt + State Machine + Typed Artifacts + Tool Registry + Deterministic Validators + Bounded LLM + Evidence Store + Audit Closure

## State outputs
S0 -> MissionSpec
S1 -> GovernanceEnvelope
S2 -> DataManifest
S3 -> FeatureSpec + LabelSpec + PartitionSpec
S4 -> ExperimentRecord[]
S5 -> StrategySpec[]
S6 -> PortfolioSpec[]
S7 -> BacktestEvidence[]
S8 -> IndependentRiskReport
S9 -> CriticReport / Replan
S10 -> LEANPackage
S11 -> ReconciliationReport + AuditBundle

Allowed LLM behavior:
- interpret objectives
- choose registered tools
- critique and replan
- summarize evidence

Forbidden:
- invent empirical values
- bypass gates
- override risk
- authorize live trading
