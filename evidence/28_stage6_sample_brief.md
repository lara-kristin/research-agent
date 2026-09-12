# Research brief: What are the failure modes of LLM-based multi-agent systems?

## Sub-questions searched

1. What are the common communication bottlenecks and coordination failures in LLM-based multi-agent systems?
   - search query: `llm multi-agent communication coordination failure breakdown`
2. How do cascading errors and hallucination propagation affect the reliability of collaborative LLM frameworks?
   - search query: `llm multi-agent hallucination cascading error propagation reliability`
3. What security vulnerabilities and adversarial failure modes emerge in decentralized LLM agent interactions?
   - search query: `llm multi-agent security vulnerability adversarial attack failure`

## Themes across the evidence

- Vulnerability of inter-agent communication and message passing to adversarial attacks and manipulation.
- Propagation, amplification, and mitigation of hallucinations and errors across sequential multi-agent interactions.
- The role of system topology and decentralized structures in influencing coordination resilience, scalability, and security.
- Language bias, strategic framing effects, and behavioral variations driven by communication in collaborative frameworks.

## Gaps this evidence does not address

- The long-term evolutionary drift of agent behaviors and alignment over extended, multi-session autonomous operations.
- The impact of heterogeneous agent mixtures involving diverse proprietary architectures and competing objective functions on system-wide failure modes.

## Selected papers (7)

### [1.00] Hallucination Cascade: Analyzing Error Propagation in Multi-Agent LLM Systems

**Authors:** Saeid Jamshidi, Arghavan Moradi Dakhel, Kawser Wazed Nafi, F. Khomh
**Year:** 2026
**DOI:** 10.48550/arxiv.2606.07937
**Verification:** not verified (arXiv preprint, registered with DataCite not Crossref)
**Addresses sub-question(s):** 2

**Summary (generated from the abstract):** This paper analyzes hallucination dynamics in multi-agent cascades by tracking claim-level factual inconsistencies across sequential interactions. Results across 500 cascade experiments show that deeper cascades can reduce hallucination scores while revealing a trade-off between hallucination suppression and factual preservation. It also evaluates reliability-efficiency trade-offs across different LLM backbones and domain complexities.

### [0.90] Red-Teaming LLM Multi-Agent Systems via Communication Attacks

**Authors:** Pengfei He, Yuping Lin, Shen Dong, Han Xu, Yue Xing, Hui Liu
**Year:** 2025
**DOI:** 10.48550/arxiv.2502.14847
**Verification:** not verified (arXiv preprint, registered with DataCite not Crossref)
**Addresses sub-question(s):** 3

**Summary (generated from the abstract):** This paper introduces the Agent-in-the-Middle attack, which exploits communication mechanisms in LLM multi-agent systems by intercepting and manipulating messages. It demonstrates that adversaries can compromise entire systems through message manipulation rather than compromising individual agents. The study highlights communication-based vulnerabilities across various frameworks and communication structures.

### [0.90] AgentNet: Decentralized Evolutionary Coordination for LLM-based Multi-Agent Systems

**Authors:** Yingxuan Yang, Huacan Chai, Shuai Shao, Yuanyi Song, Siyuan Qi, Renting Rui, Weinan Zhang
**Year:** 2025
**DOI:** 10.48550/arxiv.2504.00587
**Verification:** not verified (arXiv preprint, registered with DataCite not Crossref)
**Addresses sub-question(s):** 1

**Summary (generated from the abstract):** This paper proposes AgentNet, a decentralized RAG-based framework addressing centralized coordination limitations such as scalability bottlenecks and single points of failure. The framework allows agents to adjust connectivity and route tasks dynamically in a Directed Acyclic Graph based on local expertise. It demonstrates higher task accuracy and fault-tolerant collaboration without relying on a central orchestrator.

### [0.90] GUARDIAN: Safeguarding LLM Multi-Agent Collaborations with Temporal Graph Modeling

**Authors:** Jialong Zhou, Lichao Wang, Xiao Yang
**Year:** 2025
**DOI:** 10.48550/arxiv.2505.19234
**Verification:** not verified (arXiv preprint, registered with DataCite not Crossref)
**Addresses sub-question(s):** 2

**Summary (generated from the abstract):** This paper presents GUARDIAN, a unified method for detecting and mitigating safety concerns like hallucination amplification and error propagation in multi-agent collaborations. By modeling collaboration as a discrete-time temporal attributed graph, the method captures error propagation dynamics to identify anomalous nodes and edges. It uses an encoder-decoder architecture and graph abstraction to safeguard interactions effectively.

### [0.90] G-Safeguard: A Topology-Guided Security Lens and Treatment on LLM-based Multi-agent Systems

**Authors:** Shilong Wang, Gui-Min Zhang, Miao Yu, Guancheng Wan, Fanci Meng, Chongye Guo, Kun Wang, Yang Wang
**Year:** 2025
**DOI:** 10.48550/arxiv.2502.11127
**Verification:** not verified (arXiv preprint, registered with DataCite not Crossref)
**Addresses sub-question(s):** 3

**Summary (generated from the abstract):** This paper introduces G-Safeguard, a topology-guided security lens and treatment that uses graph neural networks to detect anomalies on multi-agent utterance graphs. It employs topological intervention to remediate vulnerabilities such as adversarial attacks, misinformation propagation, and unintended behaviors. Experiments show the method recovers significant performance under prompt injection across diverse LLM backbones.

### [0.90] MedSentry: Understanding and Mitigating Safety Risks in Medical LLM Multi-Agent Systems

**Authors:** Kai Chen, Taihang Zhen, He-Wei Wang, Kai Liu, Xinfeng Li, Jing Huo, Tianpei Yang, Jinfeng Xu, Wei Dong, Yang Gao
**Year:** 2025
**DOI:** 10.48550/arxiv.2505.20824
**Verification:** not verified (arXiv preprint, registered with DataCite not Crossref)
**Addresses sub-question(s):** 3

**Summary (generated from the abstract):** This paper introduces MedSentry to analyze how different multi-agent topologies handle information contamination and robust decision-making against adversarial prompts and dark-personality agents. The findings reveal that architectures like SharedPool are highly susceptible, whereas decentralized topologies exhibit greater resilience due to redundancy and isolation. It proposes a personality-scale detection and correction mechanism to restore system safety.

### [0.80] Strategic Communication and Language Bias in Multi-Agent LLM Coordination

**Authors:** Alessio Buscemi, Daniele Proverbio, A. D. Stefano, H. Anh, German Castignani, Pietro Liò
**Year:** 2025
**DOI:** 10.48550/arxiv.2508.00032
**Verification:** not verified (arXiv preprint, registered with DataCite not Crossref)
**Addresses sub-question(s):** 1

**Summary (generated from the abstract):** This paper investigates how linguistic framing and strategic communication affect agent behavior and cooperation in multi-agent LLM coordination. Using one-shot and repeated games, the authors find that communication significantly influences agent behavior, though its impact varies by language, personality, and game structure. The findings highlight the dual role of communication in fostering coordination while reinforcing biases.

## Limitations of this search

- Summaries derive from abstracts alone. Full texts were not retrieved, so methods, results and limitations reported only in the body of a paper are not represented here.
- One literature source was searched. Records held only by other indexes will not appear.
- 7 of 7 selected papers could not be independently verified against Crossref. Most are preprints registered with a different agency rather than doubtful records; each paper states its own reason.
