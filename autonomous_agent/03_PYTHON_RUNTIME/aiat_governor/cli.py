import argparse,json
from pathlib import Path
from .runtime import run_mission
from .tools import build_default_registry
from .llm import NullLLM
from .audit import InMemoryAuditStore
def main():
 p=argparse.ArgumentParser(); p.add_argument("mission_file"); a=p.parse_args()
 mission=json.loads(Path(a.mission_file).read_text())
 r=run_mission(mission,build_default_registry(),NullLLM(),InMemoryAuditStore())
 print(json.dumps(r.model_dump(),indent=2,default=str))
