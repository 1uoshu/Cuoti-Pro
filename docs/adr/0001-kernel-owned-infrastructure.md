# Kernel-Owned Infrastructure

We will build the backend around a dynamic plugin architecture, but shared infrastructure belongs to the kernel: model access, persistence, retrieval, RAG, and the future knowledge graph are exposed through kernel interfaces. Plugins are loaded by the kernel and contribute bounded capabilities, which keeps later graph and RAG changes centralized instead of duplicating integrations across feature modules.
