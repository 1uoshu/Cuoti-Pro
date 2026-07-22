# Native Agent Only

We decided to keep only the kernel-owned learning Agent and delete the external `agent_api.json` contract, adapter code, and related configuration. This reduces dual-path complexity, keeps frontend contracts stable, and makes agent scheduling, verification, and error handling a single backend responsibility.
