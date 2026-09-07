from datetime import datetime,timezone
class InMemoryAuditStore:
 def __init__(self): self.events=[]
 def record(self,mission_id,state,event,payload=None):
  self.events.append({"ts":datetime.now(timezone.utc).isoformat(),"mission_id":mission_id,"state":state,"event":event,"payload":payload})
 def export(self): return list(self.events)
